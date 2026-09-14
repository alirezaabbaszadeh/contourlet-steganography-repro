"""End-to-end deterministic versioned bitstream encoding and decoding."""

from __future__ import annotations

from dataclasses import dataclass
import zlib
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike

from .bitplanes import (
    PayloadLayout,
    bits_to_bytes,
    bytes_to_bits,
    bytes_to_symbols,
    payload_layout,
    recombine_progressive,
    split_secret,
    split_secret_progressive,
    symbols_to_bytes,
)
from .config import DigitalADConfig
from .header import (
    FLAG_COMPLETE_PAYLOAD_CRC,
    FLAG_LAYER_CRCS,
    HEADER_BITS,
    DigitalHeader,
    canonical_config_digest,
    decode_header,
    encode_header,
)
from .payload_profiles import profiles_for_payload
from .randomization import (
    deinterleave,
    interleave,
    permutation_sha256,
    xor_scramble,
)
from .reed_solomon import (
    CODEWORD_BYTES,
    RSProfile,
    decode_layer,
    encode_layer,
)
from .seeds import layer_seed_digest, purpose_digest, seed_id
from .types import BitArray, DecodeFailure, DecodeOutcome, MethodId


# Historical full-payload constants retained for format-v1 callers.
TOTAL_BITS = 222_360
BODY_BITS = TOTAL_BITS - HEADER_BITS
TRANSPORT_BLOCK_BITS = CODEWORD_BYTES * 8

_LAYOUT_TO_FRACTION = {
    (2, 0): 0.25,
    (4, 0): 0.50,
    (4, 2): 0.75,
    (4, 4): 1.00,
}


@dataclass(frozen=True)
class LayerTransport:
    name: str
    raw_bytes: bytes
    encoded_bits: BitArray
    transport_bits: BitArray
    permutation_sha256: str
    profile: RSProfile
    layer_digest: bytes


@dataclass(frozen=True)
class EncodedBitstream:
    method: MethodId
    payload_fraction: float
    layout: PayloadLayout
    header: DigitalHeader
    header_bits: BitArray
    base: LayerTransport
    detail: LayerTransport
    body_bits: BitArray
    bits: BitArray
    manifest: Mapping[str, Any]


def profiles_for_method(
    method: MethodId | str | int,
    *,
    base_bits: int = 4,
    detail_bits: int = 4,
) -> tuple[RSProfile, RSProfile]:
    """Compatibility wrapper around the progressive profile registry."""

    return profiles_for_payload(
        method,
        base_bits=base_bits,
        detail_bits=detail_bits,
    )


def _encode_transport(
    name: str,
    raw: bytes,
    profile: RSProfile,
    digest: bytes,
) -> LayerTransport:
    encoded = encode_layer(raw, profile)
    encoded_bits = bytes_to_bits(encoded)
    scrambled = xor_scramble(encoded_bits, digest)
    transport, permutation = interleave(scrambled, digest)
    return LayerTransport(
        name=name,
        raw_bytes=raw,
        encoded_bits=encoded_bits,
        transport_bits=transport,
        permutation_sha256=permutation_sha256(permutation),
        profile=profile,
        layer_digest=digest,
    )


def _transport_blocks(bits: BitArray) -> list[BitArray]:
    if bits.size % TRANSPORT_BLOCK_BITS:
        raise ValueError("transport layer is not codeword-aligned")
    return [
        bits[offset : offset + TRANSPORT_BLOCK_BITS]
        for offset in range(0, bits.size, TRANSPORT_BLOCK_BITS)
    ]


def _concat_blocks(blocks: list[BitArray]) -> BitArray:
    if not blocks:
        return np.empty(0, dtype=np.uint8)
    return np.concatenate(blocks).astype(np.uint8)


def merge_body(
    method: MethodId,
    base_bits: ArrayLike,
    detail_bits: ArrayLike,
) -> BitArray:
    base = np.asarray(base_bits, dtype=np.uint8).reshape(-1)
    detail = np.asarray(detail_bits, dtype=np.uint8).reshape(-1)
    if method.uses_base_first_placement:
        return np.concatenate((base, detail)).astype(np.uint8)
    base_blocks = _transport_blocks(base)
    detail_blocks = _transport_blocks(detail)
    merged: list[BitArray] = []
    for index in range(max(len(base_blocks), len(detail_blocks))):
        if index < len(base_blocks):
            merged.append(base_blocks[index])
        if index < len(detail_blocks):
            merged.append(detail_blocks[index])
    return _concat_blocks(merged)


def split_body(
    method: MethodId,
    body_bits: ArrayLike,
    *,
    base_codewords: int,
    detail_codewords: int,
) -> tuple[BitArray, BitArray]:
    body = np.asarray(body_bits, dtype=np.uint8).reshape(-1)
    expected = (base_codewords + detail_codewords) * TRANSPORT_BLOCK_BITS
    if body.size != expected:
        raise ValueError(f"expected {expected} body bits")
    if method.uses_base_first_placement:
        boundary = base_codewords * TRANSPORT_BLOCK_BITS
        return body[:boundary].copy(), body[boundary:].copy()
    blocks = _transport_blocks(body)
    base: list[BitArray] = []
    detail: list[BitArray] = []
    base_remaining = base_codewords
    detail_remaining = detail_codewords
    next_base = True
    for block in blocks:
        if next_base and base_remaining:
            base.append(block)
            base_remaining -= 1
        elif detail_remaining:
            detail.append(block)
            detail_remaining -= 1
        elif base_remaining:
            base.append(block)
            base_remaining -= 1
        else:
            raise AssertionError("transport split consumed too many blocks")
        next_base = not next_base
    if base_remaining or detail_remaining:
        raise AssertionError("transport split did not recover all layer blocks")
    return _concat_blocks(base), _concat_blocks(detail)


def _raw_layers(
    secret: ArrayLike,
    *,
    config: DigitalADConfig,
    payload_fraction: float,
) -> tuple[bytes, bytes, PayloadLayout]:
    layout = payload_layout(payload_fraction)
    if config.format_version == 1:
        if layout.fraction != 1.0:
            raise ValueError("format version 1 supports only payload_fraction=1.0")
        base_values, detail_values = split_secret(secret)
    else:
        base_values, detail_values, layout = split_secret_progressive(
            secret,
            payload_fraction=layout.fraction,
        )
    base_raw = symbols_to_bytes(
        base_values,
        bits_per_symbol=layout.base_bits,
    )
    detail_raw = (
        b""
        if detail_values is None
        else symbols_to_bytes(
            detail_values,
            bits_per_symbol=layout.detail_bits,
        )
    )
    if len(base_raw) != layout.base_bytes or len(detail_raw) != layout.detail_bytes:
        raise AssertionError("progressive raw-layer byte count is invalid")
    return base_raw, detail_raw, layout


def encode_bitstream(
    secret: ArrayLike,
    *,
    pair_id: str,
    method: MethodId | str | int,
    config: DigitalADConfig,
    payload_fraction: float = 1.0,
) -> EncodedBitstream:
    cfg = config.validate()
    selected = MethodId.parse(method)
    base_raw, detail_raw, layout = _raw_layers(
        secret,
        config=cfg,
        payload_fraction=payload_fraction,
    )
    base_profile, detail_profile = profiles_for_method(
        selected,
        base_bits=layout.base_bits,
        detail_bits=layout.detail_bits,
    )
    base_digest = layer_seed_digest(
        cfg.master_seed,
        pair_id,
        selected,
        "base",
    )
    detail_digest = layer_seed_digest(
        cfg.master_seed,
        pair_id,
        selected,
        "detail",
    )
    base = _encode_transport("base", base_raw, base_profile, base_digest)
    detail = _encode_transport(
        "detail",
        detail_raw,
        detail_profile,
        detail_digest,
    )
    body = merge_body(selected, base.transport_bits, detail.transport_bits)
    expected_body_bits = (
        base_profile.codeword_count + detail_profile.codeword_count
    ) * TRANSPORT_BLOCK_BITS
    if body.size != expected_body_bits:
        raise AssertionError(
            f"body contains {body.size}, expected {expected_body_bits} bits"
        )
    total_bits = HEADER_BITS + int(body.size)
    interleaver_id = seed_id(
        purpose_digest(base_digest, "interleave"),
        purpose_digest(detail_digest, "interleave"),
    )
    scrambler_id = seed_id(
        purpose_digest(base_digest, "scramble"),
        purpose_digest(detail_digest, "scramble"),
    )
    payload_crc = zlib.crc32(base_raw + detail_raw) & 0xFFFFFFFF
    base_crc = zlib.crc32(base_raw) & 0xFFFFFFFF if cfg.format_version == 2 else 0
    detail_crc = (
        zlib.crc32(detail_raw) & 0xFFFFFFFF
        if cfg.format_version == 2 and layout.detail_bits > 0
        else 0
    )
    flags = FLAG_COMPLETE_PAYLOAD_CRC
    if cfg.format_version == 2:
        flags |= FLAG_LAYER_CRCS
    header = DigitalHeader(
        format_version=cfg.format_version,
        method=selected,
        flags=flags,
        ecc_mode=1 if selected.uses_unequal_protection else 0,
        secret_width=cfg.secret_size,
        secret_height=cfg.secret_size,
        base_bits=layout.base_bits,
        detail_bits=layout.detail_bits,
        base_codewords=base_profile.codeword_count,
        detail_codewords=detail_profile.codeword_count,
        base_padding=base_profile.padding_bytes,
        detail_padding=detail_profile.padding_bytes,
        payload_bits=total_bits,
        interleaver_seed_id=interleaver_id,
        scrambler_seed_id=scrambler_id,
        payload_crc32=payload_crc,
        config_digest=canonical_config_digest(cfg.to_dict()),
        base_crc32=base_crc,
        detail_crc32=detail_crc,
    )
    header_bits = bytes_to_bits(encode_header(header))
    bits = np.concatenate((header_bits, body)).astype(np.uint8)
    if header_bits.size != HEADER_BITS or bits.size != total_bits:
        raise AssertionError("versioned bitstream has an invalid size")
    manifest = {
        "schema": cfg.format_version,
        "format_version": cfg.format_version,
        "method": selected.name,
        "payload_fraction": layout.fraction,
        "raw_secret_bits": layout.raw_bits,
        "raw_secret_bytes": layout.raw_bytes,
        "total_bits": int(bits.size),
        "protected_payload_bits": int(bits.size),
        "header_bits": int(header_bits.size),
        "body_bits": int(body.size),
        "body_layout": (
            "base_then_detail_high_score_first"
            if selected.uses_base_first_placement
            else "alternating_layer_transport"
        ),
        "base": {
            "bits_per_pixel": layout.base_bits,
            "raw_bytes": len(base_raw),
            "profile": base.profile.name,
            "padding_bytes": base.profile.padding_bytes,
            "codewords": base.profile.codeword_count,
            "encoded_bits": int(base.transport_bits.size),
            "permutation_sha256": base.permutation_sha256,
            "crc32": f"{base_crc:08x}" if cfg.format_version == 2 else None,
            "applicability": "applicable",
        },
        "detail": {
            "bits_per_pixel": layout.detail_bits,
            "raw_bytes": len(detail_raw),
            "profile": detail.profile.name,
            "padding_bytes": detail.profile.padding_bytes,
            "codewords": detail.profile.codeword_count,
            "encoded_bits": int(detail.transport_bits.size),
            "permutation_sha256": detail.permutation_sha256,
            "crc32": (
                f"{detail_crc:08x}"
                if cfg.format_version == 2 and layout.detail_bits > 0
                else None
            ),
            "applicability": (
                "applicable" if layout.detail_bits > 0 else "not_applicable"
            ),
        },
        "payload_crc32": f"{payload_crc:08x}",
        "interleaver_seed_id": f"{interleaver_id:016x}",
        "scrambler_seed_id": f"{scrambler_id:016x}",
        "cryptographic_claim": False,
    }
    return EncodedBitstream(
        method=selected,
        payload_fraction=layout.fraction,
        layout=layout,
        header=header,
        header_bits=header_bits,
        base=base,
        detail=detail,
        body_bits=body,
        bits=bits,
        manifest=manifest,
    )


def _decode_transport(
    bits: BitArray,
    *,
    digest: bytes,
    profile: RSProfile,
) -> tuple[bytes | None, tuple[int, ...], tuple[int, ...], str]:
    deinterleaved, permutation = deinterleave(bits, digest)
    descrambled = xor_scramble(deinterleaved, digest)
    encoded = bits_to_bytes(descrambled)
    result = decode_layer(encoded, profile)
    return (
        result.data,
        result.failures,
        result.corrected_symbols,
        permutation_sha256(permutation),
    )


def _reconstruction(
    base_data: bytes,
    detail_data: bytes,
    *,
    base_bits: int,
    detail_bits: int,
) -> np.ndarray:
    base_values = bytes_to_symbols(
        base_data,
        shape=(128, 128),
        bits_per_symbol=base_bits,
    )
    detail_values = (
        None
        if detail_bits == 0
        else bytes_to_symbols(
            detail_data,
            shape=(128, 128),
            bits_per_symbol=detail_bits,
        )
    )
    return recombine_progressive(
        base_values,
        detail_values,
        base_bits=base_bits,
        detail_bits=detail_bits,
    )


def _base_reconstruction(base_data: bytes, *, base_bits: int) -> np.ndarray:
    base_values = bytes_to_symbols(
        base_data,
        shape=(128, 128),
        bits_per_symbol=base_bits,
    )
    return recombine_progressive(
        base_values,
        None,
        base_bits=base_bits,
        detail_bits=0,
    )


def decode_bitstream(
    bits: ArrayLike,
    *,
    pair_id: str,
    expected_method: MethodId | str | int,
    config: DigitalADConfig,
    expected_payload_fraction: float = 1.0,
) -> DecodeOutcome:
    cfg = config.validate()
    selected = MethodId.parse(expected_method)
    expected_layout = payload_layout(expected_payload_fraction)
    if cfg.format_version == 1 and expected_layout.fraction != 1.0:
        raise ValueError("format version 1 supports only payload_fraction=1.0")
    values = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if values.size < HEADER_BITS or ((values != 0) & (values != 1)).any():
        raise ValueError(
            f"bitstream must contain at least {HEADER_BITS} binary header bits"
        )
    failures: list[DecodeFailure] = []
    try:
        header = decode_header(bits_to_bytes(values[:HEADER_BITS]))
    except ValueError as error:
        return DecodeOutcome(
            header_valid=False,
            payload_crc_valid=False,
            base_bytes=None,
            detail_bytes=None,
            recovered_secret=None,
            failures=(DecodeFailure("header", str(error)),),
            validity_state="header_failure",
        )
    if header.format_version != cfg.format_version:
        failures.append(
            DecodeFailure(
                "header",
                f"format mismatch: header={header.format_version}, "
                f"expected={cfg.format_version}",
            )
        )
    if header.method != selected:
        failures.append(
            DecodeFailure(
                "header",
                f"method mismatch: header={header.method.name}, "
                f"expected={selected.name}",
            )
        )
    if (header.base_bits, header.detail_bits) != (
        expected_layout.base_bits,
        expected_layout.detail_bits,
    ):
        failures.append(
            DecodeFailure(
                "header",
                "payload-fraction bit layout mismatch: "
                f"header={header.base_bits}+{header.detail_bits}, "
                f"expected={expected_layout.base_bits}+{expected_layout.detail_bits}",
            )
        )
    if header.config_digest != canonical_config_digest(cfg.to_dict()):
        failures.append(DecodeFailure("header", "configuration digest mismatch"))
    if values.size != header.payload_bits:
        failures.append(
            DecodeFailure(
                "transport",
                f"bitstream length {values.size} does not match header "
                f"payload_bits={header.payload_bits}",
            )
        )
        header_valid = not any(failure.stage == "header" for failure in failures)
        return DecodeOutcome(
            header_valid=header_valid,
            payload_crc_valid=False,
            base_bytes=None,
            detail_bytes=None,
            recovered_secret=None,
            failures=tuple(failures),
            validity_state=(
                "header_valid_no_valid_layer" if header_valid else "header_failure"
            ),
            metadata={
                "format_version": header.format_version,
                "payload_fraction": _LAYOUT_TO_FRACTION.get(
                    (header.base_bits, header.detail_bits)
                ),
            },
        )

    actual_method = header.method
    base_profile, detail_profile = profiles_for_method(
        actual_method,
        base_bits=header.base_bits,
        detail_bits=header.detail_bits,
    )
    try:
        base_transport, detail_transport = split_body(
            actual_method,
            values[HEADER_BITS:],
            base_codewords=base_profile.codeword_count,
            detail_codewords=detail_profile.codeword_count,
        )
    except ValueError as error:
        failures.append(DecodeFailure("transport", str(error)))
        header_valid = not any(failure.stage == "header" for failure in failures)
        return DecodeOutcome(
            header_valid=header_valid,
            payload_crc_valid=False,
            base_bytes=None,
            detail_bytes=None,
            recovered_secret=None,
            failures=tuple(failures),
            validity_state=(
                "header_valid_no_valid_layer" if header_valid else "header_failure"
            ),
            metadata={
                "format_version": header.format_version,
                "payload_fraction": _LAYOUT_TO_FRACTION.get(
                    (header.base_bits, header.detail_bits)
                ),
            },
        )
    base_digest = layer_seed_digest(
        cfg.master_seed,
        pair_id,
        actual_method,
        "base",
    )
    detail_digest = layer_seed_digest(
        cfg.master_seed,
        pair_id,
        actual_method,
        "detail",
    )
    expected_interleaver_id = seed_id(
        purpose_digest(base_digest, "interleave"),
        purpose_digest(detail_digest, "interleave"),
    )
    expected_scrambler_id = seed_id(
        purpose_digest(base_digest, "scramble"),
        purpose_digest(detail_digest, "scramble"),
    )
    if header.interleaver_seed_id != expected_interleaver_id:
        failures.append(DecodeFailure("header", "interleaver seed ID mismatch"))
    if header.scrambler_seed_id != expected_scrambler_id:
        failures.append(DecodeFailure("header", "scrambler seed ID mismatch"))
    base_data, base_failed, base_corrected, base_permutation_hash = (
        _decode_transport(
            base_transport,
            digest=base_digest,
            profile=base_profile,
        )
    )
    detail_data, detail_failed, detail_corrected, detail_permutation_hash = (
        _decode_transport(
            detail_transport,
            digest=detail_digest,
            profile=detail_profile,
        )
    )
    for index in base_failed:
        failures.append(
            DecodeFailure(
                "reed_solomon",
                "base codeword decode or padding validation failed",
                layer="base",
                codeword_index=index,
            )
        )
    for index in detail_failed:
        failures.append(
            DecodeFailure(
                "reed_solomon",
                "detail codeword decode or padding validation failed",
                layer="detail",
                codeword_index=index,
            )
        )

    base_crc_valid: bool | None = None
    detail_crc_valid: bool | None = None
    base_crc_actual: int | None = None
    detail_crc_actual: int | None = None
    if header.format_version == 2:
        if base_data is not None:
            base_crc_actual = zlib.crc32(base_data) & 0xFFFFFFFF
            base_crc_valid = base_crc_actual == header.base_crc32
            if not base_crc_valid:
                failures.append(
                    DecodeFailure(
                        "payload_integrity",
                        "Base CRC32 mismatch",
                        layer="base",
                    )
                )
        else:
            base_crc_valid = False
        if header.detail_bits == 0:
            detail_crc_valid = None
        elif detail_data is not None:
            detail_crc_actual = zlib.crc32(detail_data) & 0xFFFFFFFF
            detail_crc_valid = detail_crc_actual == header.detail_crc32
            if not detail_crc_valid:
                failures.append(
                    DecodeFailure(
                        "payload_integrity",
                        "Detail CRC32 mismatch",
                        layer="detail",
                    )
                )
        else:
            detail_crc_valid = False

    crc_valid = False
    payload_crc_actual: int | None = None
    if base_data is not None and detail_data is not None:
        payload_crc_actual = zlib.crc32(base_data + detail_data) & 0xFFFFFFFF
        crc_valid = payload_crc_actual == header.payload_crc32
        if not crc_valid:
            failures.append(DecodeFailure("payload_integrity", "payload CRC32 mismatch"))

    header_valid = not any(failure.stage == "header" for failure in failures)
    layer_integrity_valid = (
        header.format_version == 1
        or (
            base_crc_valid is True
            and (
                header.detail_bits == 0
                or detail_crc_valid is True
            )
        )
    )
    complete_valid = (
        header_valid
        and crc_valid
        and base_data is not None
        and detail_data is not None
        and layer_integrity_valid
    )
    recovered = None
    if complete_valid:
        recovered = _reconstruction(
            base_data,
            detail_data,
            base_bits=header.base_bits,
            detail_bits=header.detail_bits,
        )

    base_reconstruction = None
    if header.format_version == 2 and header_valid and base_crc_valid is True:
        if base_data is None:
            raise AssertionError("valid Base CRC requires decoded Base bytes")
        base_reconstruction = _base_reconstruction(
            base_data,
            base_bits=header.base_bits,
        )

    if not header_valid:
        validity_state = "header_failure"
    elif complete_valid:
        validity_state = "complete_valid_recovery"
    elif header.format_version == 2 and base_crc_valid is True:
        validity_state = "valid_base_only_recovery"
    else:
        validity_state = "header_valid_no_valid_layer"

    return DecodeOutcome(
        header_valid=header_valid,
        payload_crc_valid=crc_valid,
        base_bytes=base_data,
        detail_bytes=detail_data,
        recovered_secret=recovered,
        failures=tuple(failures),
        base_crc_valid=base_crc_valid,
        detail_crc_valid=detail_crc_valid,
        base_reconstruction=base_reconstruction,
        validity_state=validity_state,
        metadata={
            "format_version": header.format_version,
            "payload_fraction": _LAYOUT_TO_FRACTION.get(
                (header.base_bits, header.detail_bits)
            ),
            "base_bits": header.base_bits,
            "detail_bits": header.detail_bits,
            "protected_payload_bits": header.payload_bits,
            "base_corrected_symbols": list(base_corrected),
            "detail_corrected_symbols": list(detail_corrected),
            "base_permutation_sha256": base_permutation_hash,
            "detail_permutation_sha256": detail_permutation_hash,
            "detail_applicability": (
                "applicable" if header.detail_bits > 0 else "not_applicable"
            ),
            "payload_crc32_expected": f"{header.payload_crc32:08x}",
            "payload_crc32_actual": (
                f"{payload_crc_actual:08x}" if payload_crc_actual is not None else None
            ),
            "base_crc32_expected": (
                f"{header.base_crc32:08x}" if header.format_version == 2 else None
            ),
            "base_crc32_actual": (
                f"{base_crc_actual:08x}" if base_crc_actual is not None else None
            ),
            "detail_crc32_expected": (
                f"{header.detail_crc32:08x}"
                if header.format_version == 2 and header.detail_bits > 0
                else None
            ),
            "detail_crc32_actual": (
                f"{detail_crc_actual:08x}" if detail_crc_actual is not None else None
            ),
        },
    )
