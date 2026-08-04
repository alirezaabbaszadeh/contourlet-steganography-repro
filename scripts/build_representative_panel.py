#!/usr/bin/env python3
"""Create a deterministic, publication-ready representative image panel."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_gray(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("L"), dtype=np.uint8)


def psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    if reference.shape != candidate.shape:
        raise ValueError("PSNR inputs must have identical shapes")
    error = reference.astype(np.float64) - candidate.astype(np.float64)
    mse = float(np.mean(error * error))
    if mse == 0.0:
        return math.inf
    return 10.0 * math.log10((255.0 * 255.0) / mse)


def metric_text(value: float) -> str:
    return "exact" if math.isinf(value) else f"PSNR {value:.2f} dB"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--cover", required=True, type=Path)
    parser.add_argument("--secret", required=True, type=Path)
    parser.add_argument("--stego-c0", required=True, type=Path)
    parser.add_argument("--stego-c3", required=True, type=Path)
    parser.add_argument("--clean-recovered", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--difference-gain", type=float, default=20.0)
    args = parser.parse_args()

    if args.difference_gain <= 0:
        parser.error("--difference-gain must be positive")

    required = [args.cover, args.secret, args.stego_c0, args.stego_c3]
    for path in required:
        if not path.is_file():
            parser.error(f"Missing image: {path}")

    cover = load_gray(args.cover)
    secret = load_gray(args.secret)
    c0 = load_gray(args.stego_c0)
    c3 = load_gray(args.stego_c3)
    if cover.shape != c0.shape or cover.shape != c3.shape:
        raise SystemExit("Cover and stego images must have identical shapes")

    c0_psnr = psnr(cover, c0)
    c3_psnr = psnr(cover, c3)
    diff0 = np.clip(
        np.abs(c0.astype(np.int16) - cover.astype(np.int16)) * args.difference_gain,
        0,
        255,
    ).astype(np.uint8)
    diff3 = np.clip(
        np.abs(c3.astype(np.int16) - cover.astype(np.int16)) * args.difference_gain,
        0,
        255,
    ).astype(np.uint8)

    panels: list[tuple[np.ndarray, str]] = [
        (cover, "Cover"),
        (secret, "Secret"),
        (c0, f"C0 stego\n{metric_text(c0_psnr)}"),
        (c3, f"C3 stego\n{metric_text(c3_psnr)}"),
        (diff0, f"|C0 - cover| × {args.difference_gain:g}"),
        (diff3, f"|C3 - cover| × {args.difference_gain:g}"),
    ]

    recovered_psnr: float | None = None
    recovered_exact: bool | None = None
    source_paths = list(required)
    if args.clean_recovered:
        if not args.clean_recovered.is_file():
            parser.error(f"Missing recovered image: {args.clean_recovered}")
        recovered = load_gray(args.clean_recovered)
        if recovered.shape != secret.shape:
            raise SystemExit("Secret and clean recovered images must have identical shapes")
        recovered_psnr = psnr(secret, recovered)
        recovered_exact = bool(np.array_equal(secret, recovered))
        panels.append((recovered, f"Clean recovery\n{metric_text(recovered_psnr)}"))
        source_paths.append(args.clean_recovered)

    cols = 4
    rows = 2
    fig, axes = plt.subplots(rows, cols, figsize=(11.6, 6.1), constrained_layout=True)
    axes_arr = np.asarray(axes).ravel()
    panel_letters = "abcdefgh"
    for index, (ax, (image, title)) in enumerate(zip(axes_arr, panels)):
        ax.imshow(image, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
        ax.set_title(title, fontsize=10)
        ax.text(
            0.02,
            0.98,
            f"({panel_letters[index]})",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10,
            fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.5},
        )
        ax.axis("off")
    for ax in axes_arr[len(panels) :]:
        ax.axis("off")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    stem = args.output.with_suffix("")
    png_path = stem.with_suffix(".png")
    pdf_path = stem.with_suffix(".pdf")
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    metadata = {
        "pair_id": args.pair_id,
        "selection_rule": "Pair identifier fixed before visual inspection; use the first pair in the locked manifest.",
        "difference_gain": args.difference_gain,
        "cover_shape": list(cover.shape),
        "secret_shape": list(secret.shape),
        "metrics": {
            "cover_stego_c0_psnr_db": c0_psnr,
            "cover_stego_c3_psnr_db": c3_psnr,
            "clean_recovered_secret_psnr_db": recovered_psnr,
            "clean_recovered_exact": recovered_exact,
        },
        "outputs": {
            str(png_path): digest(png_path),
            str(pdf_path): digest(pdf_path),
        },
        "sources": {str(path): digest(path) for path in source_paths},
    }
    stem.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
