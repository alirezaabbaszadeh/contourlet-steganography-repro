"""Calibration-only estimation of fixed per-band attack stability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike

from .attacks import calibration_attacks
from .config import DigitalADConfig
from .preprocessing import require_uint8_grayscale
from .transform_adapter import make_transform_adapter


@dataclass(frozen=True)
class StabilityProfile:
    values: Mapping[str, float]
    artifact: Mapping[str, Any]


def calibrate_stability(
    covers: Iterable[ArrayLike],
    *,
    config: DigitalADConfig,
) -> StabilityProfile:
    cfg = config.validate()
    adapter = make_transform_adapter(cfg)
    accumulated: dict[str, list[float]] = {}
    image_count = 0
    for image_index, cover in enumerate(covers):
        source = require_uint8_grayscale(
            cover,
            shape=(cfg.cover_size, cfg.cover_size),
            name=f"calibration cover {image_index}",
        )
        original_coefficients = adapter.analyze(source)
        original_bands = adapter.eligible_bands(original_coefficients)
        descriptors = adapter.descriptors(
            original_coefficients,
            eligible_only=True,
        )
        for attack in calibration_attacks(cfg.master_seed + image_index):
            attacked = attack.apply(source)
            attacked_bands = adapter.eligible_bands(adapter.analyze(attacked))
            for descriptor, original, changed in zip(
                descriptors,
                original_bands,
                attacked_bands,
                strict=True,
            ):
                scale = float(np.mean(np.abs(original))) + cfg.allocation_epsilon
                sensitivity = float(np.mean(np.abs(changed - original)) / scale)
                accumulated.setdefault(descriptor.band_id, []).append(sensitivity)
        image_count += 1
    if image_count == 0:
        raise ValueError("calibration requires at least one cover")
    sensitivity_by_band = {
        band_id: float(np.mean(values))
        for band_id, values in accumulated.items()
    }
    stability = {
        band_id: 1.0 / (cfg.allocation_epsilon + sensitivity)
        for band_id, sensitivity in sensitivity_by_band.items()
    }
    artifact = {
        "schema": 1,
        "calibration_only": True,
        "image_count": image_count,
        "transform_profile": cfg.transform_profile,
        "transform_fingerprint": adapter.fingerprint(),
        "attacks": [
            {"name": attack.name, "parameter": attack.parameter, "value": attack.value}
            for attack in calibration_attacks(cfg.master_seed)
        ],
        "distance": "mean_abs_delta / (mean_abs_original + epsilon)",
        "aggregation": "inverse mean sensitivity",
        "stability": stability,
        "sensitivity": sensitivity_by_band,
    }
    return StabilityProfile(values=stability, artifact=artifact)


def write_stability_profile(
    output: str | Path,
    profile: StabilityProfile,
) -> None:
    destination = Path(output)
    if destination.exists() and destination.stat().st_size:
        raise FileExistsError(
            f"refusing to replace non-empty stability profile: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(
            dict(profile.artifact),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def load_stability_profile(
    path: str | Path,
    *,
    config: DigitalADConfig,
) -> StabilityProfile:
    with Path(path).open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("calibration_only") is not True:
        raise ValueError("stability artifact is not marked calibration-only")
    adapter = make_transform_adapter(config)
    if payload.get("transform_fingerprint") != adapter.fingerprint():
        raise ValueError("stability profile transform fingerprint mismatch")
    values = payload.get("stability")
    if not isinstance(values, dict) or not values:
        raise ValueError("stability profile contains no band values")
    return StabilityProfile(
        values={str(key): float(value) for key, value in values.items()},
        artifact=payload,
    )
