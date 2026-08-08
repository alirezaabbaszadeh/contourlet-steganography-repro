"""Preregistered Reed--Solomon profiles for progressive 5J payloads."""

from __future__ import annotations

from .reed_solomon import (
    BASE_UEP_PROFILE,
    DETAIL_UEP_PROFILE,
    STRONG_K,
    SYMMETRIC_PROFILE,
    WEAK_K,
    RSProfile,
)
from .types import MethodId


EMPTY_PROFILE = RSProfile(
    name="absent_layer",
    data_symbols=(),
    padding_bytes=0,
)
SYMMETRIC_2BIT_PROFILE = RSProfile(
    name="symmetric_2bit_16x127_11x191",
    data_symbols=(STRONG_K,) * 16 + (WEAK_K,) * 11,
    padding_bytes=37,
)
BASE_UEP_2BIT_PROFILE = RSProfile(
    name="base_2bit_rs_255_127",
    data_symbols=(STRONG_K,) * 33,
    padding_bytes=95,
)
DETAIL_UEP_2BIT_PROFILE = RSProfile(
    name="detail_2bit_rs_255_191",
    data_symbols=(WEAK_K,) * 22,
    padding_bytes=106,
)


def profiles_for_payload(
    method: MethodId | str | int,
    *,
    base_bits: int,
    detail_bits: int,
) -> tuple[RSProfile, RSProfile]:
    """Return the exact profiles for one declared progressive payload."""

    selected = MethodId.parse(method)
    if (base_bits, detail_bits) not in {(2, 0), (4, 0), (4, 2), (4, 4)}:
        raise ValueError("unsupported progressive Base/Detail bit layout")
    if selected.uses_unequal_protection:
        base = BASE_UEP_2BIT_PROFILE if base_bits == 2 else BASE_UEP_PROFILE
        if detail_bits == 0:
            detail = EMPTY_PROFILE
        elif detail_bits == 2:
            detail = DETAIL_UEP_2BIT_PROFILE
        else:
            detail = DETAIL_UEP_PROFILE
    else:
        base = SYMMETRIC_2BIT_PROFILE if base_bits == 2 else SYMMETRIC_PROFILE
        if detail_bits == 0:
            detail = EMPTY_PROFILE
        elif detail_bits == 2:
            detail = SYMMETRIC_2BIT_PROFILE
        else:
            detail = SYMMETRIC_PROFILE
    return base, detail


def protected_payload_bits(
    method: MethodId | str | int,
    *,
    base_bits: int,
    detail_bits: int,
    header_bits: int = 2_040,
) -> int:
    base, detail = profiles_for_payload(
        method,
        base_bits=base_bits,
        detail_bits=detail_bits,
    )
    return header_bits + 8 * (base.encoded_bytes + detail.encoded_bytes)
