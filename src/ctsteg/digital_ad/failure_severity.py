"""Comparative failure-severity diagnostics for internal 5J transports."""

from __future__ import annotations

import statistics
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike

from .bitplanes import bits_to_bytes
from .bitstream import EncodedBitstream, split_body
from .header import RAW_HEADER_BYTES, pack_header
from .randomization import deinterleave, xor_scramble
from .reed_solomon import CODEWORD_BYTES, RSProfile, decode_codeword
from .types import DecodeOutcome


_HEADER_PROFILE = RSProfile(
    name="header_rs_255_127",
    data_symbols=(RAW_HEADER_BYTES,),
    padding_bytes=0,
)


def _fraction(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else float(numerator / denominator)


def _encoded_bytes_from_transport(
    transport_bits: ArrayLike,
    *,
    digest: bytes,
) -> bytes:
    deinterleaved, _ = deinterleave(transport_bits, digest)
    descrambled = xor_scramble(deinterleaved, digest)
    return bits_to_bytes(descrambled)


def codeword_diagnostics(
    *,
    expected_encoded: bytes,
    observed_encoded: bytes,
    raw_reference: bytes,
    profile: RSProfile,
    applicability: str = "applicable",
) -> dict[str, Any]:
    """Compare received codewords with ground truth and decoder capability."""

    profile.validate()
    if applicability not in {"applicable", "not_applicable"}:
        raise ValueError("unsupported applicability")
    if applicability == "not_applicable":
        if expected_encoded or observed_encoded or raw_reference or profile.codeword_count:
            raise ValueError("not-applicable layer must be empty")
        return {
            "applicability": "not_applicable",
            "total": None,
            "successful": None,
            "failed": None,
            "corrected_symbols": None,
            "fraction_at_or_below_radius": None,
            "overload_mean": None,
            "overload_median": None,
            "overload_max": None,
            "raw_known_fraction": None,
            "raw_correct_fraction": None,
            "raw_unknown_fraction": None,
            "raw_known_bits": None,
            "raw_correct_bits": None,
            "raw_unknown_bits": None,
            "records": [],
        }
    if len(expected_encoded) != profile.encoded_bytes:
        raise ValueError("expected encoded layer length does not match profile")
    if len(observed_encoded) != profile.encoded_bytes:
        raise ValueError("observed encoded layer length does not match profile")
    if len(raw_reference) != profile.input_bytes:
        raise ValueError("raw reference length does not match profile")

    records: list[dict[str, Any]] = []
    raw_cursor = 0
    encoded_cursor = 0
    correct_bits = 0
    known_bits = 0
    unknown_bits = 0
    corrected_total = 0
    overloads: list[int] = []
    at_or_below = 0
    successful = 0

    for index, data_symbols in enumerate(profile.data_symbols):
        expected_codeword = expected_encoded[
            encoded_cursor : encoded_cursor + CODEWORD_BYTES
        ]
        observed_codeword = observed_encoded[
            encoded_cursor : encoded_cursor + CODEWORD_BYTES
        ]
        expected_values = np.frombuffer(expected_codeword, dtype=np.uint8)
        observed_values = np.frombuffer(observed_codeword, dtype=np.uint8)
        symbol_errors = int(np.count_nonzero(expected_values != observed_values))
        correction_radius = (CODEWORD_BYTES - data_symbols) // 2
        overload = max(0, symbol_errors - correction_radius)
        overloads.append(overload)
        if symbol_errors <= correction_radius:
            at_or_below += 1

        available_raw_bytes = max(
            0,
            min(data_symbols, len(raw_reference) - raw_cursor),
        )
        expected_raw = raw_reference[
            raw_cursor : raw_cursor + available_raw_bytes
        ]
        result = decode_codeword(
            observed_codeword,
            data_symbols=data_symbols,
        )
        padding_bytes = data_symbols - available_raw_bytes
        padding_valid: bool | None = None
        raw_bit_errors: int | None = None
        candidate_available = result.success and result.data is not None
        if candidate_available:
            assert result.data is not None
            candidate_raw = result.data[:available_raw_bytes]
            expected_raw_values = np.frombuffer(expected_raw, dtype=np.uint8)
            candidate_values = np.frombuffer(candidate_raw, dtype=np.uint8)
            raw_bit_errors = int(
                np.unpackbits(
                    np.bitwise_xor(expected_raw_values, candidate_values)
                ).sum()
            )
            known = available_raw_bytes * 8
            known_bits += known
            correct_bits += known - raw_bit_errors
            if padding_bytes:
                padding_valid = not any(result.data[available_raw_bytes:])
            else:
                padding_valid = True
        else:
            unknown_bits += available_raw_bytes * 8

        decoder_success = bool(candidate_available and padding_valid)
        if decoder_success:
            successful += 1
            status = "success"
        elif candidate_available:
            status = "padding_failure"
        else:
            status = "decode_failure"
        corrected_symbols = (
            int(result.corrected_symbols) if result.success else None
        )
        if corrected_symbols is not None:
            corrected_total += corrected_symbols
        records.append(
            {
                "index": index,
                "data_symbols": data_symbols,
                "parity_symbols": CODEWORD_BYTES - data_symbols,
                "correction_radius": correction_radius,
                "observed_symbol_errors": symbol_errors,
                "ecc_overload": overload,
                "decoder_status": status,
                "decoder_reason": result.reason,
                "corrected_symbols": corrected_symbols,
                "raw_data_bytes": available_raw_bytes,
                "raw_bit_errors": raw_bit_errors,
                "padding_bytes": padding_bytes,
                "padding_valid": padding_valid,
            }
        )
        raw_cursor += data_symbols
        encoded_cursor += CODEWORD_BYTES

    total_raw_bits = len(raw_reference) * 8
    if known_bits + unknown_bits != total_raw_bits:
        raise AssertionError("codeword diagnostics did not account for all raw bits")
    failed = profile.codeword_count - successful
    return {
        "applicability": "applicable",
        "total": profile.codeword_count,
        "successful": successful,
        "failed": failed,
        "corrected_symbols": corrected_total,
        "fraction_at_or_below_radius": _fraction(
            at_or_below,
            profile.codeword_count,
        ),
        "overload_mean": (
            float(statistics.fmean(overloads)) if overloads else None
        ),
        "overload_median": (
            float(statistics.median(overloads)) if overloads else None
        ),
        "overload_max": max(overloads) if overloads else None,
        "raw_known_fraction": _fraction(known_bits, total_raw_bits),
        "raw_correct_fraction": _fraction(correct_bits, total_raw_bits),
        "raw_unknown_fraction": _fraction(unknown_bits, total_raw_bits),
        "raw_known_bits": known_bits,
        "raw_correct_bits": correct_bits,
        "raw_unknown_bits": unknown_bits,
        "records": records,
    }


def failure_stage(
    outcome: DecodeOutcome,
    *,
    base_diagnostics: Mapping[str, Any] | None = None,
    detail_diagnostics: Mapping[str, Any] | None = None,
) -> str:
    """Map one scientific decode outcome to the preregistered S0--S5 stage."""

    if outcome.validity_state == "complete_valid_recovery":
        return "S0_COMPLETE"
    if outcome.validity_state == "valid_base_only_recovery":
        return "S1_BASE_ONLY"
    if not outcome.header_valid or outcome.validity_state == "header_failure":
        return "S4_HEADER_FAILURE"
    if any(
        failure.stage in {"extraction", "transform"}
        for failure in outcome.failures
    ):
        return "S5_EXTRACTION_TRANSFORM_FAILURE"
    diagnostics = (base_diagnostics, detail_diagnostics)
    if any(
        item is not None
        and item.get("applicability") == "applicable"
        and int(item.get("failed") or 0) > 0
        for item in diagnostics
    ):
        return "S3_PAYLOAD_ECC_FAILURE"
    return "S2_HEADER_VALID_PARTIAL"


def evaluate_internal_failure_severity(
    *,
    encoded: EncodedBitstream,
    extracted_bits: ArrayLike,
    outcome: DecodeOutcome,
) -> dict[str, Any]:
    """Produce header/Base/Detail diagnostics for an internal 5J method."""

    observed = np.asarray(extracted_bits, dtype=np.uint8).reshape(-1)
    if observed.shape != encoded.bits.shape:
        raise ValueError("extracted bitstream length differs from encoded stream")
    if ((observed != 0) & (observed != 1)).any():
        raise ValueError("extracted bitstream must be binary")

    header_expected = bits_to_bytes(encoded.header_bits)
    header_observed = bits_to_bytes(observed[: encoded.header_bits.size])
    header = codeword_diagnostics(
        expected_encoded=header_expected,
        observed_encoded=header_observed,
        raw_reference=pack_header(encoded.header),
        profile=_HEADER_PROFILE,
    )

    base_transport, detail_transport = split_body(
        encoded.method,
        observed[encoded.header_bits.size :],
        base_codewords=encoded.base.profile.codeword_count,
        detail_codewords=encoded.detail.profile.codeword_count,
    )
    base_observed = _encoded_bytes_from_transport(
        base_transport,
        digest=encoded.base.layer_digest,
    )
    detail_observed = _encoded_bytes_from_transport(
        detail_transport,
        digest=encoded.detail.layer_digest,
    )
    base = codeword_diagnostics(
        expected_encoded=bits_to_bytes(encoded.base.encoded_bits),
        observed_encoded=base_observed,
        raw_reference=encoded.base.raw_bytes,
        profile=encoded.base.profile,
    )
    detail_applicability = (
        "applicable"
        if encoded.layout.detail_bits > 0
        else "not_applicable"
    )
    detail = codeword_diagnostics(
        expected_encoded=bits_to_bytes(encoded.detail.encoded_bits),
        observed_encoded=detail_observed,
        raw_reference=encoded.detail.raw_bytes,
        profile=encoded.detail.profile,
        applicability=detail_applicability,
    )

    declared_raw_bits = encoded.layout.raw_bits
    base_correct = int(base["raw_correct_bits"] or 0)
    base_known = int(base["raw_known_bits"] or 0)
    base_unknown = int(base["raw_unknown_bits"] or 0)
    detail_correct = int(detail["raw_correct_bits"] or 0)
    detail_known = int(detail["raw_known_bits"] or 0)
    detail_unknown = int(detail["raw_unknown_bits"] or 0)
    correct = base_correct + detail_correct
    known = base_known + detail_known
    unknown = base_unknown + detail_unknown
    if known + unknown != declared_raw_bits:
        raise AssertionError("layer diagnostics do not cover the declared payload")

    stage = failure_stage(
        outcome,
        base_diagnostics=base,
        detail_diagnostics=detail,
    )
    return {
        "failure_stage": stage,
        "validity_state": outcome.validity_state,
        "header": header,
        "base": base,
        "detail": detail,
        "recovery": {
            "declared_raw_bits": declared_raw_bits,
            "known_output_bits": known,
            "correct_output_bits": correct,
            "unknown_bits": unknown,
            "payload_known_fraction": _fraction(known, declared_raw_bits),
            "payload_correct_fraction": _fraction(correct, declared_raw_bits),
            "unknown_bit_fraction": _fraction(unknown, declared_raw_bits),
            "base_correct_fraction": base["raw_correct_fraction"],
            "detail_correct_fraction": detail["raw_correct_fraction"],
        },
    }
