"""Rule-based subband features, robust normalization, and A scores."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np

from .config import DigitalADConfig


@dataclass(frozen=True)
class BandFeatures:
    band_id: str
    energy: float
    variance: float
    entropy: float
    stability: float
    energy_normalized: float
    variance_normalized: float
    entropy_normalized: float
    stability_normalized: float
    score: float
    weight: float


def _robust_normalize(values: Sequence[float], *, clip: float) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not array.size or not np.isfinite(array).all():
        raise ValueError("normalization values must be finite and one-dimensional")
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    if mad == 0:
        minimum = float(np.min(array))
        maximum = float(np.max(array))
        if maximum == minimum:
            return np.full(array.shape, 0.5, dtype=np.float64)
        return (array - minimum) / (maximum - minimum)
    robust_z = (array - median) / (1.4826 * mad)
    clipped = np.clip(robust_z, -clip, clip)
    return (clipped + clip) / (2.0 * clip)


def _entropy(values: np.ndarray, *, bins: int, maximum: float) -> float:
    absolute = np.abs(np.asarray(values, dtype=np.float64)).reshape(-1)
    if maximum <= 0:
        return 0.0
    counts, _ = np.histogram(absolute, bins=bins, range=(0.0, maximum))
    probabilities = counts[counts > 0].astype(np.float64) / absolute.size
    return float(-np.sum(probabilities * np.log2(probabilities)))


def band_features(
    bands: Sequence[np.ndarray],
    band_ids: Sequence[str],
    *,
    config: DigitalADConfig,
    stability_profile: Mapping[str, float] | None = None,
) -> tuple[BandFeatures, ...]:
    cfg = config.validate()
    if len(bands) != len(band_ids) or not bands:
        raise ValueError("bands and band IDs must be non-empty and aligned")
    maximum = max(float(np.max(np.abs(band))) for band in bands)
    energies = [float(np.mean(np.square(band))) for band in bands]
    variances = [float(np.var(band)) for band in bands]
    entropies = [
        _entropy(band, bins=cfg.entropy_bins, maximum=maximum) for band in bands
    ]
    stability = [
        float((stability_profile or {}).get(band_id, 0.5))
        for band_id in band_ids
    ]
    if not all(math.isfinite(value) and value >= 0 for value in stability):
        raise ValueError("stability values must be finite and non-negative")
    normalized = [
        _robust_normalize(values, clip=cfg.robust_clip)
        for values in (energies, variances, entropies, stability)
    ]
    output: list[BandFeatures] = []
    for index, band_id in enumerate(band_ids):
        score = float(sum(values[index] for values in normalized) / 4.0)
        weight = cfg.adaptive_weight_min + (
            cfg.adaptive_weight_max - cfg.adaptive_weight_min
        ) * score
        output.append(
            BandFeatures(
                band_id=band_id,
                energy=energies[index],
                variance=variances[index],
                entropy=entropies[index],
                stability=stability[index],
                energy_normalized=float(normalized[0][index]),
                variance_normalized=float(normalized[1][index]),
                entropy_normalized=float(normalized[2][index]),
                stability_normalized=float(normalized[3][index]),
                score=score,
                weight=float(weight),
            )
        )
    return tuple(output)
