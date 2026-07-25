"""Experiment orchestration and artifact generation."""

from __future__ import annotations

import csv
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "ctsteg-matplotlib"),
)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

from . import attacks
from .config import ExperimentConfig
from .image_io import save_grayscale
from .metrics import metric_bundle
from .pipeline import embed_secret, extract_secret


FloatImage = NDArray[np.float64]
Attack = tuple[str, str, float, Callable[[FloatImage], FloatImage]]


def synthetic_pair(size: int = 128, seed: int = 2026) -> tuple[FloatImage, FloatImage]:
    """Generate a deterministic, dependency-free smoke-test pair."""

    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size]
    gradient = 70 + 95 * x / max(1, size - 1) + 35 * y / max(1, size - 1)
    texture = 16 * np.sin(x / 4.5) + 12 * np.cos((x + y) / 7.0)
    cover = gradient + texture + rng.normal(0, 2.0, size=(size, size))

    center = (size - 1) / 2
    radius = np.sqrt((x - center) ** 2 + (y - center) ** 2)
    rings = 90 + 65 * np.sin(radius / 3.2)
    checker = 45 * (((x // 12 + y // 12) % 2) == 0)
    secret = rings + checker
    return (
        np.rint(np.clip(cover, 0, 255)).astype(np.float64),
        np.rint(np.clip(secret, 0, 255)).astype(np.float64),
    )


def attack_suite(config: ExperimentConfig) -> list[Attack]:
    seed = config.random_seed
    cases: list[Attack] = []
    for variance in (5.0, 10.0, 15.0):
        cases.append(
            (
                f"gaussian_var_{variance:g}",
                "gaussian_variance",
                variance,
                lambda image, value=variance: attacks.gaussian_noise(
                    image, variance=value, seed=seed
                ),
            )
        )
    for density in (0.01, 0.03, 0.05):
        cases.append(
            (
                f"salt_pepper_{density:g}",
                "salt_pepper_density",
                density,
                lambda image, value=density: attacks.salt_and_pepper_noise(
                    image, density=value, seed=seed
                ),
            )
        )
    for quality in (90, 70, 50):
        cases.append(
            (
                f"jpeg_q_{quality}",
                "jpeg_quality",
                float(quality),
                lambda image, value=quality: attacks.jpeg_compression(
                    image, quality=value
                ),
            )
        )
    for angle in (15.0, 30.0, 45.0):
        cases.append(
            (
                f"rotate_{angle:g}",
                "rotation_degrees",
                angle,
                lambda image, value=angle: attacks.rotate(
                    image, angle_degrees=value
                ),
            )
        )
    for keep_fraction in (0.90, 0.75, 0.60):
        cases.append(
            (
                f"crop_keep_{keep_fraction:g}",
                "crop_keep_fraction",
                keep_fraction,
                lambda image, value=keep_fraction: attacks.central_crop_with_zero_fill(
                    image, keep_fraction=value
                ),
            )
        )
    return cases


def _json_safe(value: float) -> float | str:
    if math.isfinite(value):
        return value
    return "inf" if value > 0 else "-inf"


def _save_panel(
    path: Path,
    cover: FloatImage,
    secret: FloatImage,
    encrypted: FloatImage,
    stego: FloatImage,
    recovered: FloatImage,
) -> None:
    images = [cover, secret, encrypted, stego, recovered]
    titles = ["Cover", "Secret", "Encrypted", "Stego", "Recovered"]
    fig, axes = plt.subplots(1, 5, figsize=(15, 3.2), constrained_layout=True)
    for axis, image, title in zip(axes, images, titles, strict=True):
        axis.imshow(image, cmap="gray", vmin=0, vmax=255)
        axis.set_title(title)
        axis.axis("off")
    fig.savefig(path, dpi=180)
    plt.close(fig)


def run_experiment(
    cover: FloatImage,
    secret: FloatImage,
    config: ExperimentConfig,
    output_dir: str | Path,
    *,
    include_attacks: bool = True,
) -> dict[str, object]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    cfg = config.validate()

    embedded = embed_secret(cover, secret, cfg)
    extracted = extract_secret(embedded.stego, embedded.cover, cfg)

    save_grayscale(destination / "cover.png", embedded.cover)
    save_grayscale(destination / "secret.png", embedded.secret)
    save_grayscale(destination / "encrypted_secret.png", embedded.encrypted_secret)
    save_grayscale(destination / "stego.png", embedded.stego)
    save_grayscale(destination / "recovered_secret.png", extracted.recovered_secret)
    difference = np.abs(embedded.stego - embedded.cover)
    save_grayscale(destination / "absolute_difference.png", difference)
    _save_panel(
        destination / "overview.png",
        embedded.cover,
        embedded.secret,
        embedded.encrypted_secret,
        embedded.stego,
        extracted.recovered_secret,
    )

    summary: dict[str, object] = {
        "config": cfg.to_dict(),
        "transform": {
            "backend": "directional_laplacian_proxy",
            "redundancy_ratio": embedded.transform_redundancy,
        },
        "imperceptibility": {
            key: _json_safe(value)
            for key, value in metric_bundle(embedded.cover, embedded.stego).items()
        },
        "recovery": {
            key: _json_safe(value)
            for key, value in metric_bundle(
                embedded.secret, extracted.recovered_secret
            ).items()
        },
    }

    attack_rows: list[dict[str, object]] = []
    if include_attacks:
        attack_dir = destination / "attacks"
        attack_dir.mkdir(exist_ok=True)
        for name, parameter, value, attack in attack_suite(cfg):
            attacked_stego = attack(embedded.stego)
            attacked_result = extract_secret(attacked_stego, embedded.cover, cfg)
            save_grayscale(attack_dir / f"{name}.png", attacked_result.recovered_secret)
            metrics = metric_bundle(embedded.secret, attacked_result.recovered_secret)
            attack_rows.append(
                {
                    "attack": name,
                    "parameter": parameter,
                    "value": value,
                    **{key: _json_safe(metric) for key, metric in metrics.items()},
                }
            )
        if attack_rows:
            with (destination / "attack_metrics.csv").open(
                "w", newline="", encoding="utf-8"
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=list(attack_rows[0]))
                writer.writeheader()
                writer.writerows(attack_rows)
    summary["attacks"] = attack_rows

    with (destination / "metrics.json").open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return summary


def demo_config(
    *,
    size: int = 128,
    quantize_stego: bool = True,
) -> ExperimentConfig:
    levels = min(4, int(math.log2(size)) - 2)
    return replace(
        ExperimentConfig(),
        image_size=size,
        levels=levels,
        band_policy="all_details",
        embed_lowpass=True,
        quantize_stego=quantize_stego,
    ).validate()
