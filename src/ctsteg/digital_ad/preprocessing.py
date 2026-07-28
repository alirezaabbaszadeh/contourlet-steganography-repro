"""Bit-exact image preprocessing rules for the digital path."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike
from PIL import Image

from .types import UInt8Image


def half_up_uint8(values: ArrayLike) -> UInt8Image:
    """Clip to [0,255], apply floor(x+0.5), and cast to uint8."""

    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError("image contains NaN or infinity")
    return np.floor(np.clip(array, 0.0, 255.0) + 0.5).astype(np.uint8)


def require_uint8_grayscale(
    values: ArrayLike,
    *,
    shape: tuple[int, int],
    name: str,
) -> UInt8Image:
    array = np.asarray(values)
    if array.shape != shape or array.ndim != 2:
        raise ValueError(f"{name} must have shape {shape}")
    if array.dtype != np.uint8:
        raise ValueError(f"{name} must have dtype uint8")
    return np.asarray(array, dtype=np.uint8)


def load_uint8_grayscale(path: str | Path, *, size: int) -> UInt8Image:
    with Image.open(path) as image:
        gray = image.convert("L")
        if gray.size != (size, size):
            gray = gray.resize((size, size), Image.Resampling.BICUBIC)
        return np.asarray(gray, dtype=np.uint8)


def save_uint8_grayscale(path: str | Path, image: ArrayLike) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    values = np.asarray(image)
    if values.ndim != 2:
        raise ValueError("output must be a grayscale image")
    pixels = values if values.dtype == np.uint8 else half_up_uint8(values)
    Image.fromarray(pixels, mode="L").save(destination)
