"""Coefficient-domain sign embedding and semi-blind bit extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

from ctsteg.transform import PyramidCoefficients

from .allocation import Slot, SlotPlan
from .types import BitArray


@dataclass(frozen=True)
class UnitPerturbation:
    details: tuple[np.ndarray, ...]


def _binary(values: np.ndarray, *, expected: int) -> BitArray:
    bits = np.asarray(values, dtype=np.uint8).reshape(-1)
    if bits.size != expected or ((bits != 0) & (bits != 1)).any():
        raise ValueError(f"expected exactly {expected} binary values")
    return bits


def _accumulate(
    arrays: Sequence[np.ndarray],
    slots: Sequence[Slot],
    bits: BitArray,
) -> None:
    signs = bits.astype(np.float64) * 2.0 - 1.0
    by_band: dict[int, list[tuple[int, float]]] = {}
    for slot, sign in zip(slots, signs, strict=True):
        by_band.setdefault(slot.band_index, []).append(
            (slot.flat_index, slot.weight * float(sign))
        )
    for band_index, entries in by_band.items():
        indices = np.fromiter(
            (entry[0] for entry in entries),
            dtype=np.int64,
            count=len(entries),
        )
        values = np.fromiter(
            (entry[1] for entry in entries),
            dtype=np.float64,
            count=len(entries),
        )
        arrays[band_index].reshape(-1)[indices] = values


def build_unit_perturbation(
    cover_coefficients: PyramidCoefficients,
    plan: SlotPlan,
    header_bits: np.ndarray,
    body_bits: np.ndarray,
    *,
    eligible_level: int,
    eligible_bands: Sequence[np.ndarray] | None = None,
) -> UnitPerturbation:
    header = _binary(header_bits, expected=len(plan.header_slots))
    body = _binary(body_bits, expected=len(plan.body_slots))
    eligible = (
        cover_coefficients.details[eligible_level]
        if eligible_bands is None
        else eligible_bands
    )
    arrays = [np.zeros_like(band, dtype=np.float64) for band in eligible]
    _accumulate(arrays, plan.header_slots, header)
    _accumulate(arrays, plan.body_slots, body)
    return UnitPerturbation(details=tuple(arrays))


def apply_perturbation(
    cover_coefficients: PyramidCoefficients,
    perturbation: UnitPerturbation,
    *,
    eligible_level: int,
    strength: float,
    adapter: Any | None = None,
) -> PyramidCoefficients:
    if strength < 0:
        raise ValueError("embedding strength must be non-negative")
    if adapter is not None:
        return adapter.apply_eligible_perturbation(
            cover_coefficients,
            perturbation.details,
            strength=strength,
        )
    modified = cover_coefficients.copy()
    bands = modified.details[eligible_level]
    if len(bands) != len(perturbation.details):
        raise ValueError("perturbation band count does not match transform")
    for band, unit in zip(bands, perturbation.details, strict=True):
        if band.shape != unit.shape:
            raise ValueError("perturbation band shape does not match transform")
        band += strength * unit
    return modified


def _extract_slots(
    delta_bands: Sequence[np.ndarray],
    slots: Sequence[Slot],
) -> BitArray:
    values = np.empty(len(slots), dtype=np.uint8)
    by_band: dict[int, list[tuple[int, int]]] = {}
    for output_index, slot in enumerate(slots):
        by_band.setdefault(slot.band_index, []).append(
            (output_index, slot.flat_index)
        )
    for band_index, entries in by_band.items():
        output_indices = np.fromiter(
            (entry[0] for entry in entries),
            dtype=np.int64,
            count=len(entries),
        )
        flat_indices = np.fromiter(
            (entry[1] for entry in entries),
            dtype=np.int64,
            count=len(entries),
        )
        differences = delta_bands[band_index].reshape(-1)[flat_indices]
        values[output_indices] = (differences >= 0.0).astype(np.uint8)
    return values


def extract_bits(
    stego_coefficients: PyramidCoefficients,
    cover_coefficients: PyramidCoefficients,
    plan: SlotPlan,
    *,
    eligible_level: int,
    adapter: Any | None = None,
) -> tuple[BitArray, BitArray, BitArray]:
    stego_bands = (
        stego_coefficients.details[eligible_level]
        if adapter is None
        else adapter.eligible_bands(stego_coefficients)
    )
    cover_bands = (
        cover_coefficients.details[eligible_level]
        if adapter is None
        else adapter.eligible_bands(cover_coefficients)
    )
    if len(stego_bands) != len(cover_bands):
        raise ValueError("stego and cover transform structures differ")
    delta = [
        np.asarray(stego, dtype=np.float64)
        - np.asarray(cover, dtype=np.float64)
        for stego, cover in zip(stego_bands, cover_bands, strict=True)
    ]
    header = _extract_slots(delta, plan.header_slots)
    body = _extract_slots(delta, plan.body_slots)
    return header, body, np.concatenate((header, body)).astype(np.uint8)
