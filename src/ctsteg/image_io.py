"""Image loading, normalization, and lossless output helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray
from PIL import Image


FloatImage = NDArray[np.float64]


def load_grayscale(path: str | Path, *, size: int = 512) -> FloatImage:
    with Image.open(path) as image:
        gray = image.convert("L")
        if gray.size != (size, size):
            gray = gray.resize((size, size), Image.Resampling.BICUBIC)
        return np.asarray(gray, dtype=np.float64)


def save_grayscale(path: str | Path, image: ArrayLike) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    values = np.asarray(image, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("output must be a grayscale image")
    pixels = np.rint(np.clip(values, 0.0, 255.0)).astype(np.uint8)
    Image.fromarray(pixels, mode="L").save(destination)

