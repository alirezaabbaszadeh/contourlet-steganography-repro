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
    """Controlled methods from the locked protocols.

    Values 0--3 are the immutable format-v1 C0--C3 identities.  C3_NP is an
    additive 5J ablation and therefore receives a new value instead of
    renumbering any historical method.
    """

    C0_FIXED = 0
    C1_A = 1
    C2_D = 2
    C3_A_D = 3
    C3_NP = 4

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
            "C3_NP": cls.C3_NP,
            "C3_NON_PRIORITIZED": cls.C3_NP,
        }
        try:
            return aliases[normalized]
        except KeyError as error:
            raise ValueError(f"unknown digital A+D method: {value!r}") from error

    @property
    def uses_adaptive_allocation(self) -> bool:
        return self in {MethodId.C1_A, MethodId.C3_A_D, MethodId.C3_NP}

    @property
    def uses_unequal_protection(self) -> bool:
        return self in {MethodId.C2_D, MethodId.C3_A_D, MethodId.C3_NP}

    @property
    def uses_base_first_placement(self) -> bool:
        return self is MethodId.C3_A_D


@dataclass(frozen=True)
class DecodeFailure:
    """One explicit decoding failure; no replacement data are fabricated."""

    stage: str
    reason: str
    layer: str | None = None
    codeword_index: int | None = None


@dataclass(frozen=True)
class DecodeOutcome:
    """Structured decode result with explicit complete and layer validity."""

    header_valid: bool
    payload_crc_valid: bool
    base_bytes: bytes | None
    detail_bytes: bytes | None
    recovered_secret: UInt8Image | None
    failures: tuple[DecodeFailure, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    base_crc_valid: bool | None = None
    detail_crc_valid: bool | None = None
    base_reconstruction: UInt8Image | None = None
    validity_state: str = "unknown"

    @property
    def success(self) -> bool:
        """True only for exact complete-payload recovery."""

        return (
            self.header_valid
            and self.payload_crc_valid
            and self.base_bytes is not None
            and self.detail_bytes is not None
            and self.recovered_secret is not None
            and self.validity_state == "complete_valid_recovery"
            and not self.failures
        )

    @property
    def base_only_success(self) -> bool:
        """True only for independently validated format-v2 Base recovery."""

        return (
            self.header_valid
            and self.base_crc_valid is True
            and self.base_bytes is not None
            and self.base_reconstruction is not None
            and self.validity_state in {
                "complete_valid_recovery",
                "valid_base_only_recovery",
            }
        )
