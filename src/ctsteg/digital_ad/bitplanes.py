"""Secret bitplane splitting, recombination, and MSB-first packing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from .types import BitArray, UInt8Image


SECRET_SHAPE = (128, 128)
SECRET_PIXELS = SECRET_SHAPE[0] * SECRET_SHAPE[1]
LAYER_BITS = 65_536
LAYER_BYTES = 8_192
SECRET_BITS = 131_072


@dataclass(frozen=True)
class PayloadLayout:
    """One preregistered progressive raw-secret operating point."""

    fraction: float
    base_bits: int
    detail_bits: int
    reconstruction_mask: int

    @property
    def raw_bits(self) -> int:
        return SECRET_PIXELS * (self.base_bits + self.detail_bits)

    @property
    def raw_bytes(self) -> int:
        return self.raw_bits // 8

    @property
    def base_bytes(self) -> int:
        return SECRET_PIXELS * self.base_bits // 8

    @property
    def detail_bytes(self) -> int:
        return SECRET_PIXELS * self.detail_bits // 8


_PAYLOAD_LAYOUTS = {
    0.25: PayloadLayout(0.25, 2, 0, 0xC0),
    0.50: PayloadLayout(0.50, 4, 0, 0xF0),
    0.75: PayloadLayout(0.75, 4, 2, 0xFC),
    1.00: PayloadLayout(1.00, 4, 4, 0xFF),
}


def payload_layout(payload_fraction: float) -> PayloadLayout:
    """Return the exact preregistered progressive payload definition."""

    try:
        fraction = float(payload_fraction)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload_fraction must be numeric") from exc
    try:
        return _PAYLOAD_LAYOUTS[fraction]
    except KeyError as exc:
        raise ValueError(
            "payload_fraction must be one of 0.25, 0.50, 0.75, or 1.00"
        ) from exc


def _secret(secret: ArrayLike) -> UInt8Image:
    pixels = np.asarray(secret)
    if pixels.shape != SECRET_SHAPE or pixels.dtype != np.uint8:
        raise ValueError("secret must be a 128x128 uint8 image")
    return pixels


def split_secret(secret: ArrayLike) -> tuple[UInt8Image, UInt8Image]:
    """Historical 4+4 split retained for format-v1 compatibility."""

    pixels = _secret(secret)
    base = np.right_shift(pixels, 4).astype(np.uint8)
    detail = np.bitwise_and(pixels, 0x0F).astype(np.uint8)
    return base, detail


def split_secret_progressive(
    secret: ArrayLike,
    *,
    payload_fraction: float,
) -> tuple[UInt8Image, UInt8Image | None, PayloadLayout]:
    """Split the most significant declared bitplanes into Base and Detail."""

    pixels = _secret(secret)
    layout = payload_layout(payload_fraction)
    base_shift = 8 - layout.base_bits
    base_mask = (1 << layout.base_bits) - 1
    base = np.bitwise_and(
        np.right_shift(pixels, base_shift),
        base_mask,
    ).astype(np.uint8)
    if layout.detail_bits == 0:
        detail = None
    else:
        detail_shift = 4 - layout.detail_bits
        detail_mask = (1 << layout.detail_bits) - 1
        detail = np.bitwise_and(
            np.right_shift(pixels, detail_shift),
            detail_mask,
        ).astype(np.uint8)
    return base, detail, layout


def recombine_secret(base: ArrayLike, detail: ArrayLike) -> UInt8Image:
    """Historical 4+4 recombination retained for format-v1 compatibility."""

    base_values = np.asarray(base)
    detail_values = np.asarray(detail)
    if base_values.shape != detail_values.shape:
        raise ValueError("base and detail shapes must match")
    if base_values.dtype != np.uint8 or detail_values.dtype != np.uint8:
        raise ValueError("base and detail must be uint8")
    if ((base_values > 0x0F) | (detail_values > 0x0F)).any():
        raise ValueError("base and detail must contain four-bit nibbles")
    return np.bitwise_or(np.left_shift(base_values, 4), detail_values).astype(
        np.uint8
    )


def recombine_progressive(
    base: ArrayLike,
    detail: ArrayLike | None,
    *,
    base_bits: int,
    detail_bits: int,
) -> UInt8Image:
    """Reconstruct a declared progressive payload with omitted bits set to zero."""

    allowed = {(2, 0), (4, 0), (4, 2), (4, 4)}
    if (base_bits, detail_bits) not in allowed:
        raise ValueError("unsupported progressive Base/Detail bit layout")
    base_values = np.asarray(base)
    if base_values.shape != SECRET_SHAPE or base_values.dtype != np.uint8:
        raise ValueError("base must be a 128x128 uint8 array")
    if (base_values >= (1 << base_bits)).any():
        raise ValueError("base value exceeds the declared bit width")
    result = np.left_shift(base_values, 8 - base_bits).astype(np.uint8)
    if detail_bits == 0:
        if detail is not None:
            detail_values = np.asarray(detail)
            if detail_values.size and np.any(detail_values):
                raise ValueError("absent Detail must not contain non-zero values")
        return result
    if detail is None:
        raise ValueError("declared Detail bits require Detail values")
    detail_values = np.asarray(detail)
    if detail_values.shape != SECRET_SHAPE or detail_values.dtype != np.uint8:
        raise ValueError("detail must be a 128x128 uint8 array")
    if (detail_values >= (1 << detail_bits)).any():
        raise ValueError("detail value exceeds the declared bit width")
    detail_shift = 4 - detail_bits
    return np.bitwise_or(
        result,
        np.left_shift(detail_values, detail_shift),
    ).astype(np.uint8)


def progressive_reference(
    secret: ArrayLike,
    *,
    payload_fraction: float,
) -> UInt8Image:
    """Return the deterministic full-image reference for a payload fraction."""

    pixels = _secret(secret)
    layout = payload_layout(payload_fraction)
    return np.bitwise_and(pixels, np.uint8(layout.reconstruction_mask)).astype(
        np.uint8
    )


def symbols_to_bits(symbols: ArrayLike, *, bits_per_symbol: int) -> BitArray:
    values = np.asarray(symbols)
    if values.dtype != np.uint8 or values.ndim != 2:
        raise ValueError("symbols must be a two-dimensional uint8 array")
    if bits_per_symbol not in {2, 4}:
        raise ValueError("bits_per_symbol must be 2 or 4")
    if (values >= (1 << bits_per_symbol)).any():
        raise ValueError("symbol value exceeds the declared bit width")
    shifts = np.arange(
        bits_per_symbol - 1,
        -1,
        -1,
        dtype=np.uint8,
    )
    shifted = np.right_shift(values.reshape(-1, 1), shifts).astype(np.uint8)
    return np.bitwise_and(shifted, 1).reshape(-1)


def bits_to_symbols(
    bits: ArrayLike,
    *,
    shape: tuple[int, int],
    bits_per_symbol: int,
) -> UInt8Image:
    if bits_per_symbol not in {2, 4}:
        raise ValueError("bits_per_symbol must be 2 or 4")
    values = np.asarray(bits, dtype=np.uint8).reshape(-1)
    expected = shape[0] * shape[1] * bits_per_symbol
    if values.size != expected or ((values != 0) & (values != 1)).any():
        raise ValueError(f"expected exactly {expected} binary values")
    groups = values.reshape(-1, bits_per_symbol)
    weights = np.left_shift(
        np.uint8(1),
        np.arange(bits_per_symbol - 1, -1, -1, dtype=np.uint8),
    )
    return np.sum(groups * weights, axis=1, dtype=np.uint8).reshape(shape)


def nibbles_to_bits(nibbles: ArrayLike) -> BitArray:
    return symbols_to_bits(nibbles, bits_per_symbol=4)


def bits_to_nibbles(bits: ArrayLike, *, shape: tuple[int, int]) -> UInt8Image:
    return bits_to_symbols(bits, shape=shape, bits_per_symbol=4)


def bits_to_bytes(bits: ArrayLike) -> bytes:
    values = np.asarray(bits, dtype=np.uint8).reshape(-1)
    if values.size % 8 or ((values != 0) & (values != 1)).any():
        raise ValueError("bits must be binary and byte-aligned")
    return np.packbits(values, bitorder="big").tobytes()


def bytes_to_bits(payload: bytes) -> BitArray:
    return np.unpackbits(
        np.frombuffer(payload, dtype=np.uint8),
        bitorder="big",
    ).astype(np.uint8)


def symbols_to_bytes(symbols: ArrayLike, *, bits_per_symbol: int) -> bytes:
    return bits_to_bytes(
        symbols_to_bits(symbols, bits_per_symbol=bits_per_symbol)
    )


def bytes_to_symbols(
    payload: bytes,
    *,
    shape: tuple[int, int],
    bits_per_symbol: int,
) -> UInt8Image:
    expected_bytes = shape[0] * shape[1] * bits_per_symbol // 8
    if len(payload) != expected_bytes:
        raise ValueError(
            f"expected exactly {expected_bytes} bytes for {bits_per_symbol}-bit symbols"
        )
    return bits_to_symbols(
        bytes_to_bits(payload),
        shape=shape,
        bits_per_symbol=bits_per_symbol,
    )


def nibbles_to_bytes(nibbles: ArrayLike) -> bytes:
    return symbols_to_bytes(nibbles, bits_per_symbol=4)


def bytes_to_nibbles(payload: bytes, *, shape: tuple[int, int]) -> UInt8Image:
    return bytes_to_symbols(payload, shape=shape, bits_per_symbol=4)
