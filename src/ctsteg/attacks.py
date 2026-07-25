"""Deterministic implementations of the attacks listed in Tables 7-10."""

from __future__ import annotations

from io import BytesIO

import numpy as np
from numpy.typing import ArrayLike, NDArray
from PIL import Image
from scipy.ndimage import rotate as scipy_rotate


FloatImage = NDArray[np.float64]


def _image(values: ArrayLike) -> FloatImage:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("attack input must be a grayscale image")
    if not np.isfinite(array).all():
        raise ValueError("attack input contains NaN or infinity")
    return array


def gaussian_noise(
    image: ArrayLike,
    *,
    variance: float,
    seed: int = 2026,
) -> FloatImage:
    if variance < 0:
        raise ValueError("variance must be non-negative")
    source = _image(image)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, np.sqrt(variance), size=source.shape)
    return np.clip(source + noise, 0.0, 255.0)


def salt_and_pepper_noise(
    image: ArrayLike,
    *,
    density: float,
    seed: int = 2026,
) -> FloatImage:
    if not 0 <= density <= 1:
        raise ValueError("density must be within [0, 1]")
    source = _image(image).copy()
    rng = np.random.default_rng(seed)
    draws = rng.random(source.shape)
    source[draws < density / 2] = 0.0
    source[(draws >= density / 2) & (draws < density)] = 255.0
    return source


def jpeg_compression(image: ArrayLike, *, quality: int) -> FloatImage:
    if not 1 <= quality <= 100:
        raise ValueError("quality must be within [1, 100]")
    source = np.rint(np.clip(_image(image), 0, 255)).astype(np.uint8)
    buffer = BytesIO()
    Image.fromarray(source, mode="L").save(
        buffer,
        format="JPEG",
        quality=quality,
        subsampling=0,
        optimize=False,
    )
    buffer.seek(0)
    return np.asarray(Image.open(buffer).convert("L"), dtype=np.float64)


def rotate(image: ArrayLike, *, angle_degrees: float) -> FloatImage:
    source = _image(image)
    return scipy_rotate(
        source,
        angle=angle_degrees,
        reshape=False,
        order=1,
        mode="constant",
        cval=0.0,
        prefilter=False,
    )


def central_crop_with_zero_fill(
    image: ArrayLike,
    *,
    keep_fraction: float,
) -> FloatImage:
    """Keep the central area and zero the removed border.

    The paper does not state whether its crop is padded, resized, or registered
    before extraction.  Zero fill is explicit and preserves the required input
    dimensions for semi-blind coefficient subtraction.
    """

    if not 0 < keep_fraction <= 1:
        raise ValueError("keep_fraction must be within (0, 1]")
    source = _image(image)
    height, width = source.shape
    side_fraction = np.sqrt(keep_fraction)
    kept_height = max(1, int(round(height * side_fraction)))
    kept_width = max(1, int(round(width * side_fraction)))
    row_start = (height - kept_height) // 2
    col_start = (width - kept_width) // 2
    output = np.zeros_like(source)
    output[
        row_start : row_start + kept_height,
        col_start : col_start + kept_width,
    ] = source[
        row_start : row_start + kept_height,
        col_start : col_start + kept_width,
    ]
    return output

