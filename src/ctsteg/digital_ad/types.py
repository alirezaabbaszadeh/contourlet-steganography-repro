"""Shared immutable types for the digital A+D implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Mapping

import numpy as np
from numpy.typing import NDArray


UInt8Image = NDArray[np.uint8]
FloatImage = NDArray[np.float64]
BitArray = NDArray[np.uint8]


class MethodId(IntEnum):
    """Controlled factorial methods from the prospective protocol."""

    C0_FIXED = 0
    C1_A = 1
    C2_D = 2
    C3_A_D = 3

    @classmethod
    def parse(cls, value: str | int | "MethodId") -> "MethodId":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        normalized = value.strip().upper().replace("-", "_")
        aliases = {
            "C0": cls.C0_FIXED,
            "C0_FIXED": cls.C0_FIXED,
            "C1": cls.C1_A,
            "C1_A": cls.C1_A,
            "C2": cls.C2_D,
            "C2_D": cls.C2_D,
            "C3": cls.C3_A_D,
            "C3_A_D": cls.C3_A_D,
            "DIGITAL_A_D": cls.C3_A_D,
        }
        try:
            return aliases[normalized]
        except KeyError as error:
            raise ValueError(f"unknown digital A+D method: {value!r}") from error

    @property
    def uses_adaptive_allocation(self) -> bool:
        return self in {MethodId.C1_A, MethodId.C3_A_D}

    @property
    def uses_unequal_protection(self) -> bool:
        return self in {MethodId.C2_D, MethodId.C3_A_D}


@dataclass(frozen=True)
class DecodeFailure:
    """One explicit decoding failure; no replacement data are fabricated."""

    stage: str
    reason: str
    layer: str | None = None
    codeword_index: int | None = None


@dataclass(frozen=True)
class DecodeOutcome:
    """Structured decode result with explicit validity and failure metadata."""

    header_valid: bool
    payload_crc_valid: bool
    base_bytes: bytes | None
    detail_bytes: bytes | None
    recovered_secret: UInt8Image | None
    failures: tuple[DecodeFailure, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return (
            self.header_valid
            and self.payload_crc_valid
            and self.base_bytes is not None
            and self.detail_bytes is not None
            and self.recovered_secret is not None
            and not self.failures
        )
