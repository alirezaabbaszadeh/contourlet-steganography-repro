"""Self-contained, code-frozen baselines for FINAL-5J-v1.

B1 is a deterministic grayscale k-LSB replacement baseline. The smallest
k in [1, 4] whose realized cover--stego PSNR is closest to the requested
operating point is selected after simulating all candidates.

B2 is a blind block-DCT scalar-QIM baseline. It uses 32 fixed AC positions
per 8x8 block (exact capacity: 131,072 bits for a 512x512 cover), tries a
frozen list of QIM steps, rejects candidates that do not recover bit-exactly
from the clean uint8 stego image, and selects the clean-valid candidate whose
realized PSNR is closest to the requested target.

Both baselines embed the same progressive raw-secret bitplanes declared by
FINAL-5J-v1. They do not claim Base/Detail semantics or Reed--Solomon
protection; those fields are reported as not_applicable by the runtime adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.fft import dctn, idctn

from ctsteg.metrics import metric_bundle
from ctsteg.provenance import sha256_file, sha256_json

from .bitplanes import (
    SECRET_SHAPE,
    bits_to_symbols,
    payload_layout,
    recombine_progressive,
    split_secret_progressive,
    symbols_to_bits,
)


PROTOCOL_ID = "FINAL-5J-v1"
B1_ID = "B1"
B2_ID = "B2"
B1_REFERENCE_REPOSITORY = "https://github.com/ragibson/Steganography"
B1_REFERENCE_COMMIT = "06a3c920420e62f2e8a0589cfd5bfb2e51be4ee8"
B2_REFERENCE_REPOSITORY = "https://github.com/MasonEdgar/DCT-Image-Steganography"
B2_REFERENCE_COMMIT = "20da3e1e4d6b48dbcbe241c776ee156995bb65fe"
B1_K_CANDIDATES = (1, 2, 3, 4)
B2_DELTA_CANDIDATES = (
    2.0,
    3.0,
    3.25,
    3.5,
    3.75,
    4.0,
    5.0,
    6.0,
    8.0,
    10.0,
    12.0,
    16.0,
    20.0,
    24.0,
    32.0,
)


class Baseline5JError(RuntimeError):
    """Raised for an invalid baseline input, capacity, or clean decode."""


@dataclass(frozen=True)
class BaselineEmbedding:
    method: str
    stego: np.ndarray
    payload_bits: np.ndarray
    reconstructed_reference: np.ndarray
    parameters: Mapping[str, Any]
    cover_stego_metrics: Mapping[str, float]


@dataclass(frozen=True)
class BaselineExtraction:
    method: str
    payload_bits: np.ndarray
    reconstructed: np.ndarray
    bit_errors: int
    ber: float
    complete_recovery: bool


def _uint8_image(
    value: np.ndarray,
    *,
    shape: tuple[int, int],
    name: str,
) -> np.ndarray:
    image = np.asarray(value)
    if image.shape != shape or image.dtype != np.uint8:
        raise Baseline5JError(f"{name} must be {shape[0]}x{shape[1]} uint8")
    return image


def raw_payload_bits(secret: np.ndarray, *, payload_fraction: float) -> np.ndarray:
    """Pack only the declared progressive secret bitplanes, MSB first."""
    image = _uint8_image(secret, shape=SECRET_SHAPE, name="secret")
    base, detail, layout = split_secret_progressive(
        image,
        payload_fraction=payload_fraction,
    )
    chunks = [symbols_to_bits(base, bits_per_symbol=layout.base_bits)]
    if layout.detail_bits:
        if detail is None:
            raise Baseline5JError("declared Detail bits are absent")
        chunks.append(
            symbols_to_bits(detail, bits_per_symbol=layout.detail_bits)
        )
    bits = np.concatenate(chunks).astype(np.uint8, copy=False)
    if bits.size != layout.raw_bits:
        raise Baseline5JError("progressive payload length mismatch")
    return bits


def reconstruct_raw_payload(
    bits: np.ndarray,
    *,
    payload_fraction: float,
) -> np.ndarray:
    """Reconstruct progressive data with omitted bitplanes set to zero."""
    values = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if ((values != 0) & (values != 1)).any():
        raise Baseline5JError("payload contains non-binary values")
    layout = payload_layout(payload_fraction)
    if values.size != layout.raw_bits:
        raise Baseline5JError(
            f"payload contains {values.size} bits; expected {layout.raw_bits}"
        )
    base_count = SECRET_SHAPE[0] * SECRET_SHAPE[1] * layout.base_bits
    base = bits_to_symbols(
        values[:base_count],
        shape=SECRET_SHAPE,
        bits_per_symbol=layout.base_bits,
    )
    detail = None
    if layout.detail_bits:
        detail = bits_to_symbols(
            values[base_count:],
            shape=SECRET_SHAPE,
            bits_per_symbol=layout.detail_bits,
        )
    return recombine_progressive(
        base,
        detail,
        base_bits=layout.base_bits,
        detail_bits=layout.detail_bits,
    )


def _psnr(reference: np.ndarray, candidate: np.ndarray) -> float:
    return float(metric_bundle(reference, candidate)["psnr_db"])


def _bit_error_count(reference: np.ndarray, candidate: np.ndarray) -> int:
    first = np.asarray(reference, dtype=np.uint8).reshape(-1)
    second = np.asarray(candidate, dtype=np.uint8).reshape(-1)
    if first.size != second.size:
        raise Baseline5JError("payload lengths differ")
    return int(np.count_nonzero(first != second))


def _choose_closest(
    candidates: list[tuple[float, Any]],
    *,
    target_psnr_db: float,
) -> tuple[float, Any]:
    if not candidates:
        raise Baseline5JError("no clean-valid embedding candidate exists")
    return min(
        candidates,
        key=lambda item: (
            abs(item[0] - float(target_psnr_db)),
            -item[0],
        ),
    )


def _lsb_embed_with_k(
    cover: np.ndarray,
    bits: np.ndarray,
    k: int,
) -> np.ndarray:
    if k not in B1_K_CANDIDATES:
        raise Baseline5JError("B1 k must be within 1..4")
    flat = cover.reshape(-1).copy()
    groups = (bits.size + k - 1) // k
    if groups > flat.size:
        raise Baseline5JError("B1 payload exceeds cover capacity")
    padded = np.pad(bits, (0, groups * k - bits.size), constant_values=0)
    weights = np.left_shift(
        np.uint8(1),
        np.arange(k - 1, -1, -1, dtype=np.uint8),
    )
    symbols = np.sum(
        padded.reshape(groups, k) * weights,
        axis=1,
        dtype=np.uint8,
    )
    low_mask = (1 << k) - 1
    clear_mask = np.uint8(0xFF ^ low_mask)
    flat[:groups] = np.bitwise_or(
        np.bitwise_and(flat[:groups], clear_mask),
        symbols,
    )
    return flat.reshape(cover.shape)


def _lsb_extract(
    stego: np.ndarray,
    *,
    bit_count: int,
    k: int,
) -> np.ndarray:
    flat = stego.reshape(-1)
    groups = (bit_count + k - 1) // k
    if groups > flat.size:
        raise Baseline5JError("B1 extraction exceeds cover capacity")
    symbols = np.bitwise_and(flat[:groups], np.uint8((1 << k) - 1))
    shifts = np.arange(k - 1, -1, -1, dtype=np.uint8)
    bits = np.bitwise_and(
        np.right_shift(symbols.reshape(-1, 1), shifts),
        1,
    ).astype(np.uint8).reshape(-1)
    return bits[:bit_count]


def embed_b1(
    cover: np.ndarray,
    secret: np.ndarray,
    *,
    payload_fraction: float,
    target_psnr_db: float,
) -> BaselineEmbedding:
    cover_image = _uint8_image(cover, shape=(512, 512), name="cover")
    payload = raw_payload_bits(secret, payload_fraction=payload_fraction)
    candidates: list[tuple[float, tuple[int, np.ndarray]]] = []
    for k in B1_K_CANDIDATES:
        stego = _lsb_embed_with_k(cover_image, payload, k)
        recovered = _lsb_extract(stego, bit_count=payload.size, k=k)
        if _bit_error_count(payload, recovered) == 0:
            candidates.append((_psnr(cover_image, stego), (k, stego)))
    realized_psnr, (selected_k, stego) = _choose_closest(
        candidates,
        target_psnr_db=target_psnr_db,
    )
    return BaselineEmbedding(
        method=B1_ID,
        stego=stego,
        payload_bits=payload,
        reconstructed_reference=reconstruct_raw_payload(
            payload,
            payload_fraction=payload_fraction,
        ),
        parameters={
            "algorithm": "sequential_grayscale_k_lsb_replacement",
            "num_lsb": selected_k,
            "bit_count": int(payload.size),
            "payload_fraction": float(payload_fraction),
            "target_psnr_db": float(target_psnr_db),
            "reference_repository": B1_REFERENCE_REPOSITORY,
            "reference_commit": B1_REFERENCE_COMMIT,
        },
        cover_stego_metrics={
            **metric_bundle(cover_image, stego),
            "selected_psnr_db": realized_psnr,
        },
    )


def extract_b1(
    stego: np.ndarray,
    *,
    reference_bits: np.ndarray,
    payload_fraction: float,
    parameters: Mapping[str, Any],
) -> BaselineExtraction:
    image = _uint8_image(stego, shape=(512, 512), name="stego")
    k = int(parameters["num_lsb"])
    bit_count = int(parameters["bit_count"])
    extracted = _lsb_extract(image, bit_count=bit_count, k=k)
    errors = _bit_error_count(reference_bits, extracted)
    return BaselineExtraction(
        method=B1_ID,
        payload_bits=extracted,
        reconstructed=reconstruct_raw_payload(
            extracted,
            payload_fraction=payload_fraction,
        ),
        bit_errors=errors,
        ber=float(errors / reference_bits.size),
        complete_recovery=errors == 0,
    )


def _zigzag_positions() -> tuple[tuple[int, int], ...]:
    positions: list[tuple[int, int]] = []
    for diagonal in range(15):
        values: list[tuple[int, int]] = []
        row_min = max(0, diagonal - 7)
        row_max = min(7, diagonal)
        for row in range(row_min, row_max + 1):
            values.append((row, diagonal - row))
        if diagonal % 2 == 0:
            values.reverse()
        positions.extend(values)
    if len(positions) != 64 or positions[0] != (0, 0):
        raise AssertionError("invalid 8x8 zigzag table")
    return tuple(positions)


# Skip the very lowest-frequency four AC terms and use 32 consecutive
# low/mid-frequency positions. 4096 blocks * 32 bits = 131,072 bits.
B2_AC_POSITIONS = _zigzag_positions()[5:37]


def _blocks(image: np.ndarray) -> np.ndarray:
    height, width = image.shape
    if height % 8 or width % 8:
        raise Baseline5JError("B2 cover dimensions must be divisible by 8")
    return (
        image.astype(np.float64)
        .reshape(height // 8, 8, width // 8, 8)
        .transpose(0, 2, 1, 3)
        .copy()
    )


def _unblocks(blocks: np.ndarray) -> np.ndarray:
    rows, cols, _, _ = blocks.shape
    return blocks.transpose(0, 2, 1, 3).reshape(rows * 8, cols * 8)


def _dct_coefficients(image: np.ndarray) -> np.ndarray:
    return dctn(_blocks(image) - 128.0, axes=(-2, -1), norm="ortho")


def _spatial_from_coefficients(coefficients: np.ndarray) -> np.ndarray:
    reconstructed = idctn(
        coefficients,
        axes=(-2, -1),
        norm="ortho",
    ) + 128.0
    return np.clip(
        np.rint(_unblocks(reconstructed)),
        0,
        255,
    ).astype(np.uint8)


def _qim_quantize(
    values: np.ndarray,
    bits: np.ndarray,
    delta: float,
) -> np.ndarray:
    scaled = values / float(delta)
    lower = np.floor(scaled).astype(np.int64)
    upper = lower + 1
    lower += (bits.astype(np.int64) - (lower & 1)) & 1
    upper += (bits.astype(np.int64) - (upper & 1)) & 1
    lower_values = lower.astype(np.float64) * float(delta)
    upper_values = upper.astype(np.float64) * float(delta)
    choose_upper = (
        np.abs(upper_values - values) < np.abs(lower_values - values)
    )
    return np.where(choose_upper, upper_values, lower_values)


def _dct_embed_with_delta(
    cover_coefficients: np.ndarray,
    bits: np.ndarray,
    delta: float,
) -> np.ndarray:
    modified = cover_coefficients.copy()
    block_count = modified.shape[0] * modified.shape[1]
    capacity = block_count * len(B2_AC_POSITIONS)
    if bits.size > capacity:
        raise Baseline5JError("B2 payload exceeds fixed DCT capacity")
    flat_blocks = modified.reshape(block_count, 8, 8)
    for position_index, (row, col) in enumerate(B2_AC_POSITIONS):
        start = position_index * block_count
        if start >= bits.size:
            break
        stop = min(start + block_count, bits.size)
        count = stop - start
        flat_blocks[:count, row, col] = _qim_quantize(
            flat_blocks[:count, row, col],
            bits[start:stop],
            delta,
        )
    return _spatial_from_coefficients(modified)


def _dct_extract(
    stego: np.ndarray,
    *,
    bit_count: int,
    delta: float,
) -> np.ndarray:
    coefficients = _dct_coefficients(stego).reshape(-1, 8, 8)
    block_count = coefficients.shape[0]
    capacity = block_count * len(B2_AC_POSITIONS)
    if bit_count > capacity:
        raise Baseline5JError("B2 extraction exceeds fixed DCT capacity")
    chunks: list[np.ndarray] = []
    remaining = bit_count
    for row, col in B2_AC_POSITIONS:
        if remaining <= 0:
            break
        count = min(block_count, remaining)
        quantized = np.rint(
            coefficients[:count, row, col] / float(delta)
        ).astype(np.int64)
        chunks.append(np.bitwise_and(quantized, 1).astype(np.uint8))
        remaining -= count
    if remaining:
        raise Baseline5JError("B2 did not extract the declared payload")
    return (
        np.concatenate(chunks)
        if chunks
        else np.empty(0, dtype=np.uint8)
    )


def embed_b2(
    cover: np.ndarray,
    secret: np.ndarray,
    *,
    payload_fraction: float,
    target_psnr_db: float,
) -> BaselineEmbedding:
    cover_image = _uint8_image(cover, shape=(512, 512), name="cover")
    payload = raw_payload_bits(secret, payload_fraction=payload_fraction)
    coefficients = _dct_coefficients(cover_image)
    candidates: list[tuple[float, tuple[float, np.ndarray]]] = []
    clean_failures: dict[str, int] = {}
    for delta in B2_DELTA_CANDIDATES:
        stego = _dct_embed_with_delta(coefficients, payload, delta)
        recovered = _dct_extract(
            stego,
            bit_count=payload.size,
            delta=delta,
        )
        errors = _bit_error_count(payload, recovered)
        clean_failures[str(delta)] = errors
        if errors == 0:
            candidates.append((_psnr(cover_image, stego), (delta, stego)))
    realized_psnr, (selected_delta, stego) = _choose_closest(
        candidates,
        target_psnr_db=target_psnr_db,
    )
    return BaselineEmbedding(
        method=B2_ID,
        stego=stego,
        payload_bits=payload,
        reconstructed_reference=reconstruct_raw_payload(
            payload,
            payload_fraction=payload_fraction,
        ),
        parameters={
            "algorithm": "block_dct_scalar_qim",
            "block_size": 8,
            "ac_positions": [list(value) for value in B2_AC_POSITIONS],
            "delta": float(selected_delta),
            "delta_candidates": list(B2_DELTA_CANDIDATES),
            "clean_candidate_bit_errors": clean_failures,
            "bit_count": int(payload.size),
            "payload_fraction": float(payload_fraction),
            "target_psnr_db": float(target_psnr_db),
            "reference_repository": B2_REFERENCE_REPOSITORY,
            "reference_commit": B2_REFERENCE_COMMIT,
        },
        cover_stego_metrics={
            **metric_bundle(cover_image, stego),
            "selected_psnr_db": realized_psnr,
        },
    )


def extract_b2(
    stego: np.ndarray,
    *,
    reference_bits: np.ndarray,
    payload_fraction: float,
    parameters: Mapping[str, Any],
) -> BaselineExtraction:
    image = _uint8_image(stego, shape=(512, 512), name="stego")
    delta = float(parameters["delta"])
    bit_count = int(parameters["bit_count"])
    extracted = _dct_extract(
        image,
        bit_count=bit_count,
        delta=delta,
    )
    errors = _bit_error_count(reference_bits, extracted)
    return BaselineExtraction(
        method=B2_ID,
        payload_bits=extracted,
        reconstructed=reconstruct_raw_payload(
            extracted,
            payload_fraction=payload_fraction,
        ),
        bit_errors=errors,
        ber=float(errors / reference_bits.size),
        complete_recovery=errors == 0,
    )


def embed_baseline(
    method: str,
    cover: np.ndarray,
    secret: np.ndarray,
    *,
    payload_fraction: float,
    target_psnr_db: float,
) -> BaselineEmbedding:
    if method == B1_ID:
        return embed_b1(
            cover,
            secret,
            payload_fraction=payload_fraction,
            target_psnr_db=target_psnr_db,
        )
    if method == B2_ID:
        return embed_b2(
            cover,
            secret,
            payload_fraction=payload_fraction,
            target_psnr_db=target_psnr_db,
        )
    raise Baseline5JError(f"unknown baseline method: {method!r}")


def extract_baseline(
    method: str,
    stego: np.ndarray,
    *,
    reference_bits: np.ndarray,
    payload_fraction: float,
    parameters: Mapping[str, Any],
) -> BaselineExtraction:
    if method == B1_ID:
        return extract_b1(
            stego,
            reference_bits=reference_bits,
            payload_fraction=payload_fraction,
            parameters=parameters,
        )
    if method == B2_ID:
        return extract_b2(
            stego,
            reference_bits=reference_bits,
            payload_fraction=payload_fraction,
            parameters=parameters,
        )
    raise Baseline5JError(f"unknown baseline method: {method!r}")


def adapter_source_sha256() -> str:
    return sha256_file(Path(__file__).resolve())


def adapter_fingerprint(method: str) -> str:
    if method not in {B1_ID, B2_ID}:
        raise Baseline5JError(f"unknown baseline method: {method!r}")
    reference = (
        (B1_REFERENCE_REPOSITORY, B1_REFERENCE_COMMIT)
        if method == B1_ID
        else (B2_REFERENCE_REPOSITORY, B2_REFERENCE_COMMIT)
    )
    return sha256_json(
        {
            "protocol_id": PROTOCOL_ID,
            "method": method,
            "adapter_source_sha256": adapter_source_sha256(),
            "reference_repository": reference[0],
            "reference_commit": reference[1],
        }
    )
