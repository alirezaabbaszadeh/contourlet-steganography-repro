"""Secret nibble split, recombination, and MSB-first packing."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from .types import BitArray, UInt8Image


LAYER_BITS = 65_536
LAYER_BYTES = 8_192
SECRET_BITS = 131_072


def split_secret(secret: ArrayLike) -> tuple[UInt8Image, UInt8Image]:
    pixels = np.asarray(secret)
    if pixels.shape != (128, 128) or pixels.dtype != np.uint8:
        raise ValueError("secret must be a 128x128 uint8 image")
    base = np.right_shift(pixels, 4).astype(np.uint8)
    detail = np.bitwise_and(pixels, 0x0F).astype(np.uint8)
    return base, detail


def recombine_secret(base: ArrayLike, detail: ArrayLike) -> UInt8Image:
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


def nibbles_to_bits(nibbles: ArrayLike) -> BitArray:
    values = np.asarray(nibbles)
    if values.dtype != np.uint8 or values.ndim != 2:
        raise ValueError("nibbles must be a two-dimensional uint8 array")
    if (values > 0x0F).any():
        raise ValueError("nibble value exceeds 15")
    shifts = np.asarray([3, 2, 1, 0], dtype=np.uint8)
    shifted = np.right_shift(values.reshape(-1, 1), shifts).astype(np.uint8)
    return np.bitwise_and(shifted, 1).reshape(-1)


def bits_to_nibbles(bits: ArrayLike, *, shape: tuple[int, int]) -> UInt8Image:
    values = np.asarray(bits, dtype=np.uint8).reshape(-1)
    expected = shape[0] * shape[1] * 4
    if values.size != expected or ((values != 0) & (values != 1)).any():
        raise ValueError(f"expected exactly {expected} binary values")
    groups = values.reshape(-1, 4)
    weights = np.asarray([8, 4, 2, 1], dtype=np.uint8)
    return np.sum(groups * weights, axis=1, dtype=np.uint8).reshape(shape)


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


def nibbles_to_bytes(nibbles: ArrayLike) -> bytes:
    return bits_to_bytes(nibbles_to_bits(nibbles))


def bytes_to_nibbles(payload: bytes, *, shape: tuple[int, int]) -> UInt8Image:
    return bits_to_nibbles(bytes_to_bits(payload), shape=shape)
