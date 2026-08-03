#!/usr/bin/env python3
"""Create a deterministic cover/secret/stego/difference manuscript panel."""
from __future__ import annotations

import argparse
import hashlib
import json
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

    diff0 = np.clip(np.abs(c0.astype(np.int16) - cover.astype(np.int16)) * args.difference_gain, 0, 255)
    diff3 = np.clip(np.abs(c3.astype(np.int16) - cover.astype(np.int16)) * args.difference_gain, 0, 255)
    panels = [
        (cover, "Cover"),
        (secret, "Secret"),
        (c0, "C0 stego"),
        (c3, "C3 stego"),
        (diff0, f"C0 difference x{args.difference_gain:g}"),
        (diff3, f"C3 difference x{args.difference_gain:g}"),
    ]
    if args.clean_recovered:
        if not args.clean_recovered.is_file():
            parser.error(f"Missing recovered image: {args.clean_recovered}")
        panels.append((load_gray(args.clean_recovered), "Clean recovered secret"))

    cols = 4 if len(panels) > 6 else 3
    rows = (len(panels) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 3.0 * rows))
    axes_arr = np.atleast_1d(axes).ravel()
    for ax, (image, title) in zip(axes_arr, panels):
        ax.imshow(image, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title)
        ax.axis("off")
    for ax in axes_arr[len(panels):]:
        ax.axis("off")
    fig.suptitle(f"Pre-specified representative pair: {args.pair_id}")
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300, bbox_inches="tight")
    if args.output.suffix.lower() != ".pdf":
        fig.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)

    metadata = {
        "pair_id": args.pair_id,
        "difference_gain": args.difference_gain,
        "files": {
            str(path): digest(path)
            for path in required + ([args.clean_recovered] if args.clean_recovered else [])
        },
        "selection_rule": "Pair identifier must be fixed before visual inspection (recommended: first pair in locked manifest).",
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
