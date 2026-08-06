"""Capacity-safe subband allocation and deterministic coefficient maps."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct
from typing import Sequence

import numpy as np

from .adaptive import BandFeatures
from .bitstream import BODY_BITS, HEADER_BITS, TOTAL_BITS
from .types import MethodId


@dataclass(frozen=True)
class Slot:
    band_index: int
    flat_index: int
    weight: float


@dataclass(frozen=True)
class SlotPlan:
    method: MethodId
    band_ids: tuple[str, ...]
    header_slots: tuple[Slot, ...]
    body_slots: tuple[Slot, ...]
    per_band_capacity: tuple[int, ...]
    per_band_body_slots: tuple[int, ...]
    band_scores: tuple[float, ...]
    band_weights: tuple[float, ...]
    coefficient_map_sha256: str
    body_layout: str

    @property
    def total_slots(self) -> int:
        return len(self.header_slots) + len(self.body_slots)


def capped_largest_remainder(
    weights: Sequence[float],
    capacities: Sequence[int],
    total: int,
    *,
    epsilon: float,
) -> tuple[int, ...]:
    values = np.asarray(weights, dtype=np.float64)
    caps = np.asarray(capacities, dtype=np.int64)
    if (
        values.ndim != 1
        or caps.ndim != 1
        or values.size != caps.size
        or not values.size
    ):
        raise ValueError("weights and capacities must be aligned vectors")
    if not np.isfinite(values).all() or (values < 0).any() or (caps < 0).any():
        raise ValueError("weights and capacities must be finite and non-negative")
    if total < 0 or total > int(np.sum(caps)):
        raise ValueError("requested slots exceed available capacity")
    allocation = np.zeros(caps.shape, dtype=np.int64)
    remaining = int(total)
    while remaining:
        active = np.flatnonzero(allocation < caps)
        if not active.size:
            raise AssertionError("allocator exhausted capacity early")
        active_weights = values[active] + epsilon
        ideal = remaining * active_weights / float(np.sum(active_weights))
        floors = np.floor(ideal).astype(np.int64)
        room = caps[active] - allocation[active]
        floors = np.minimum(floors, room)
        assigned = int(np.sum(floors))
        if assigned:
            allocation[active] += floors
            remaining -= assigned
            if not remaining:
                break
        active = np.flatnonzero(allocation < caps)
        active_weights = values[active] + epsilon
        ideal = remaining * active_weights / float(np.sum(active_weights))
        fractional = ideal - np.floor(ideal)
        order = sorted(
            range(active.size),
            key=lambda index: (-fractional[index], int(active[index])),
        )
        progressed = False
        for order_index in order:
            band_index = int(active[order_index])
            if remaining == 0:
                break
            if allocation[band_index] < caps[band_index]:
                allocation[band_index] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            raise AssertionError("capped largest remainder failed to progress")
    if int(np.sum(allocation)) != total or (allocation > caps).any():
        raise AssertionError("allocator violated its exact capacity contract")
    return tuple(int(value) for value in allocation)


def _round_robin(slots_by_band: Sequence[Sequence[Slot]]) -> tuple[Slot, ...]:
    output: list[Slot] = []
    maximum = max((len(slots) for slots in slots_by_band), default=0)
    for offset in range(maximum):
        for slots in slots_by_band:
            if offset < len(slots):
                output.append(slots[offset])
    return tuple(output)


def _map_hash(header: Sequence[Slot], body: Sequence[Slot]) -> str:
    digest = hashlib.sha256()
    digest.update(b"ctsteg-digital-coefficient-map-v1\0")
    for section, slots in ((0, header), (1, body)):
        for slot in slots:
            digest.update(
                struct.pack(
                    "<BHI d",
                    section,
                    slot.band_index,
                    slot.flat_index,
                    slot.weight,
                )
            )
    return digest.hexdigest()


def build_slot_plan(
    *,
    method: MethodId,
    bands: Sequence[np.ndarray],
    band_ids: Sequence[str],
    features: Sequence[BandFeatures],
    epsilon: float,
) -> SlotPlan:
    if len(bands) != len(band_ids) or len(features) != len(bands):
        raise ValueError("bands, IDs, and features must be aligned")
    capacities = [int(np.asarray(band).size) for band in bands]
    if sum(capacities) < TOTAL_BITS:
        raise ValueError("candidate coefficient pool is too small")
    header_slots: list[Slot] = []
    header_used = [0] * len(bands)
    remaining_header = HEADER_BITS
    for band_index, capacity in enumerate(capacities):
        count = min(capacity, remaining_header)
        header_slots.extend(
            Slot(band_index, flat_index, 1.0) for flat_index in range(count)
        )
        header_used[band_index] = count
        remaining_header -= count
        if remaining_header == 0:
            break
    if remaining_header:
        raise AssertionError("failed to reserve all fixed header slots")
    remaining_capacity = [
        capacity - used
        for capacity, used in zip(capacities, header_used, strict=True)
    ]
    if method.uses_adaptive_allocation:
        allocation_weights = [feature.score for feature in features]
        band_weights = [feature.weight for feature in features]
    else:
        allocation_weights = [1.0] * len(bands)
        band_weights = [1.0] * len(bands)
    quotas = capped_largest_remainder(
        allocation_weights,
        remaining_capacity,
        BODY_BITS,
        epsilon=epsilon,
    )
    slots_by_band: list[list[Slot]] = []
    for band_index, count in enumerate(quotas):
        start = header_used[band_index]
        slots_by_band.append(
            [
                Slot(
                    band_index=band_index,
                    flat_index=start + offset,
                    weight=float(band_weights[band_index]),
                )
                for offset in range(count)
            ]
        )

    # C3_NP must share the exact C3 coefficient ordering.  The ablation is
    # isolated in bitstream.merge_body(): C3 writes Base then Detail, whereas
    # C3_NP alternates their codewords.  Changing the slot map here would
    # confound layer priority with coordinate ranking.
    if method in {MethodId.C3_A_D, MethodId.C3_NP}:
        order = sorted(
            range(len(bands)),
            key=lambda index: (-features[index].score, band_ids[index]),
        )
        body_slots = tuple(
            slot for band_index in order for slot in slots_by_band[band_index]
        )
        body_layout = (
            "base_then_detail_high_score_first"
            if method is MethodId.C3_A_D
            else "alternating_layer_transport_high_score_first"
        )
    else:
        body_slots = _round_robin(slots_by_band)
        body_layout = "alternating_layer_transport_round_robin_bands"
    plan = SlotPlan(
        method=method,
        band_ids=tuple(band_ids),
        header_slots=tuple(header_slots),
        body_slots=body_slots,
        per_band_capacity=tuple(capacities),
        per_band_body_slots=quotas,
        band_scores=tuple(float(feature.score) for feature in features),
        band_weights=tuple(float(value) for value in band_weights),
        coefficient_map_sha256=_map_hash(header_slots, body_slots),
        body_layout=body_layout,
    )
    if plan.total_slots != TOTAL_BITS:
        raise AssertionError("slot plan does not contain exactly 222,360 slots")
    identities = {
        (slot.band_index, slot.flat_index)
        for slot in (*plan.header_slots, *plan.body_slots)
    }
    if len(identities) != TOTAL_BITS:
        raise AssertionError("slot plan contains overlapping coefficient slots")
    return plan
