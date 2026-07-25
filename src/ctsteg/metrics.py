"""Image-quality and extraction metrics used in the article."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.ndimage import gaussian_filter


FloatImage = NDArray[np.float64]


def _pair(reference: ArrayLike, candidate: ArrayLike) -> tuple[FloatImage, FloatImage]:
    first = np.asarray(reference, dtype=np.float64)
    second = np.asarray(candidate, dtype=np.float64)
    if first.shape != second.shape:
        raise ValueError("metric inputs must have the same shape")
    if first.ndim != 2:
        raise ValueError("metrics expect grayscale images")
    if not np.isfinite(first).all() or not np.isfinite(second).all():
        raise ValueError("metric inputs contain NaN or infinity")
    return first, second


def mse(reference: ArrayLike, candidate: ArrayLike) -> float:
    first, second = _pair(reference, candidate)
    return float(np.mean(np.square(first - second)))


def psnr(
    reference: ArrayLike,
    candidate: ArrayLike,
    *,
    data_range: float = 255.0,
) -> float:
    error = mse(reference, candidate)
    if error == 0:
        return math.inf
    return float(10.0 * math.log10((data_range**2) / error))


def ssim_global(
    reference: ArrayLike,
    candidate: ArrayLike,
    *,
    data_range: float = 255.0,
) -> float:
    """Global SSIM matching the article's single mean/variance equation."""

    first, second = _pair(reference, candidate)
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    mean_first = float(np.mean(first))
    mean_second = float(np.mean(second))
    variance_first = float(np.var(first))
    variance_second = float(np.var(second))
    covariance = float(np.mean((first - mean_first) * (second - mean_second)))
    numerator = (2 * mean_first * mean_second + c1) * (2 * covariance + c2)
    denominator = (
        (mean_first**2 + mean_second**2 + c1)
        * (variance_first + variance_second + c2)
    )
    return float(numerator / denominator)


def ssim_windowed(
    reference: ArrayLike,
    candidate: ArrayLike,
    *,
    data_range: float = 255.0,
    sigma: float = 1.5,
) -> float:
    """Standard local-window SSIM, reported separately from article-style SSIM."""

    first, second = _pair(reference, candidate)
    c1 = (0.01 * data_range) ** 2
    c2 = (0.03 * data_range) ** 2
    mu_first = gaussian_filter(first, sigma=sigma, mode="reflect")
    mu_second = gaussian_filter(second, sigma=sigma, mode="reflect")
    mu_first_sq = np.square(mu_first)
    mu_second_sq = np.square(mu_second)
    mu_product = mu_first * mu_second
    var_first = gaussian_filter(np.square(first), sigma=sigma, mode="reflect")
    var_first -= mu_first_sq
    var_second = gaussian_filter(np.square(second), sigma=sigma, mode="reflect")
    var_second -= mu_second_sq
    covariance = gaussian_filter(first * second, sigma=sigma, mode="reflect")
    covariance -= mu_product
    numerator = (2 * mu_product + c1) * (2 * covariance + c2)
    denominator = (mu_first_sq + mu_second_sq + c1) * (
        var_first + var_second + c2
    )
    return float(np.mean(numerator / denominator))


def normalized_correlation(reference: ArrayLike, candidate: ArrayLike) -> float:
    first, second = _pair(reference, candidate)
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator == 0:
        return 1.0 if np.array_equal(first, second) else 0.0
    return float(np.sum(first * second) / denominator)


def ncc_paper(reference: ArrayLike, candidate: ArrayLike) -> float:
    """The asymmetric NCC formula printed as Equation 4 in the article."""

    first, second = _pair(reference, candidate)
    denominator = float(np.sum(np.square(first)))
    if denominator == 0:
        return 1.0 if np.array_equal(first, second) else 0.0
    return float(np.sum(first * second) / denominator)


def bit_error_rate(reference: ArrayLike, candidate: ArrayLike) -> float:
    first, second = _pair(reference, candidate)
    first_bytes = np.rint(np.clip(first, 0, 255)).astype(np.uint8)
    second_bytes = np.rint(np.clip(second, 0, 255)).astype(np.uint8)
    xor = np.bitwise_xor(first_bytes, second_bytes)
    differing_bits = np.unpackbits(xor.reshape(-1)).sum()
    return float(differing_bits / (first_bytes.size * 8))


def metric_bundle(reference: ArrayLike, candidate: ArrayLike) -> dict[str, float]:
    return {
        "mse": mse(reference, candidate),
        "psnr_db": psnr(reference, candidate),
        "ssim_global": ssim_global(reference, candidate),
        "ssim_windowed": ssim_windowed(reference, candidate),
        "ncc": normalized_correlation(reference, candidate),
        "ncc_paper_equation": ncc_paper(reference, candidate),
        "ber": bit_error_rate(reference, candidate),
    }

