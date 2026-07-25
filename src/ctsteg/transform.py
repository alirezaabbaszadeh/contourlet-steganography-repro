"""A transparent multiscale, multidirectional Laplacian-pyramid backend.

The paper does not state its CT filters, boundary mode, or directional-level
schedule.  This backend is therefore an explicit *contourlet-style proxy*, not
an assertion that the authors used these exact filters.  It provides exact
analysis/synthesis on analyzed images and makes every choice inspectable.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.ndimage import gaussian_filter, zoom


FloatImage = NDArray[np.float64]


@dataclass
class PyramidCoefficients:
    """Finest-to-coarsest directional details plus the final low-pass image."""

    lowpass: FloatImage
    details: list[list[FloatImage]]

    def copy(self) -> "PyramidCoefficients":
        return PyramidCoefficients(
            lowpass=self.lowpass.copy(),
            details=[[band.copy() for band in level] for level in self.details],
        )

    @property
    def coefficient_count(self) -> int:
        return int(
            self.lowpass.size
            + sum(band.size for level in self.details for band in level)
        )


def _resize(array: FloatImage, shape: tuple[int, int]) -> FloatImage:
    if array.shape == shape:
        return array.copy()
    factors = (shape[0] / array.shape[0], shape[1] / array.shape[1])
    resized = zoom(array, factors, order=1, mode="reflect", prefilter=False)
    # scipy.ndimage.zoom can differ by one sample for unusual shapes.
    output = np.empty(shape, dtype=np.float64)
    rows = min(shape[0], resized.shape[0])
    cols = min(shape[1], resized.shape[1])
    output[:rows, :cols] = resized[:rows, :cols]
    if rows < shape[0]:
        output[rows:, :cols] = output[rows - 1 : rows, :cols]
    if cols < shape[1]:
        output[:, cols:] = output[:, cols - 1 : cols]
    return output


@lru_cache(maxsize=32)
def _angular_masks(
    height: int,
    width: int,
    directions: int,
    concentration: float,
) -> tuple[FloatImage, ...]:
    fy = np.fft.fftfreq(height)[:, None]
    fx = np.fft.fftfreq(width)[None, :]
    angle = np.arctan2(fy, fx)
    centers = np.arange(directions, dtype=np.float64) * np.pi / directions
    weights = np.stack(
        [
            np.exp(concentration * np.cos(2.0 * (angle - center)))
            for center in centers
        ],
        axis=0,
    )
    weights /= np.sum(weights, axis=0, keepdims=True)
    return tuple(np.asarray(mask, dtype=np.float64) for mask in weights)


class DirectionalLaplacianPyramid:
    """Linear Laplacian pyramid with a partition-of-unity angular filter bank."""

    def __init__(
        self,
        *,
        levels: int = 4,
        directions: int = 4,
        angular_concentration: float = 8.0,
        gaussian_sigma: float = 1.0,
    ) -> None:
        if levels < 1:
            raise ValueError("levels must be positive")
        if directions < 2:
            raise ValueError("directions must be at least 2")
        if angular_concentration <= 0 or gaussian_sigma <= 0:
            raise ValueError("filter parameters must be positive")
        self.levels = levels
        self.directions = directions
        self.angular_concentration = float(angular_concentration)
        self.gaussian_sigma = float(gaussian_sigma)

    def analyze(self, image: ArrayLike) -> PyramidCoefficients:
        current = np.asarray(image, dtype=np.float64)
        if current.ndim != 2:
            raise ValueError("expected a two-dimensional image")
        if min(current.shape) < 2**self.levels:
            raise ValueError("image is too small for the requested levels")

        details: list[list[FloatImage]] = []
        for _ in range(self.levels):
            smoothed = gaussian_filter(
                current, sigma=self.gaussian_sigma, mode="reflect"
            )
            lowpass = smoothed[::2, ::2]
            prediction = _resize(lowpass, current.shape)
            residual = current - prediction
            spectrum = np.fft.fft2(residual)
            masks = _angular_masks(
                current.shape[0],
                current.shape[1],
                self.directions,
                self.angular_concentration,
            )
            bands = [
                np.fft.ifft2(spectrum * mask).real.astype(np.float64)
                for mask in masks
            ]
            details.append(bands)
            current = lowpass
        return PyramidCoefficients(lowpass=current, details=details)

    def synthesize(self, coefficients: PyramidCoefficients) -> FloatImage:
        if len(coefficients.details) != self.levels:
            raise ValueError("coefficient level count does not match transform")
        current = np.asarray(coefficients.lowpass, dtype=np.float64)
        for bands in reversed(coefficients.details):
            if len(bands) != self.directions:
                raise ValueError("direction count does not match transform")
            shape = bands[0].shape
            if any(band.shape != shape for band in bands):
                raise ValueError("all directional bands at a level must align")
            current = _resize(current, shape) + np.sum(bands, axis=0)
        return np.asarray(current, dtype=np.float64)

    def redundancy_ratio(self, image_shape: tuple[int, int]) -> float:
        dummy = np.zeros(image_shape, dtype=np.float64)
        coeffs = self.analyze(dummy)
        return coeffs.coefficient_count / dummy.size

