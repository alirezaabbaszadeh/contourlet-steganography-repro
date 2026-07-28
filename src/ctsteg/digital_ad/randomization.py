"""Deterministic non-cryptographic scrambling and interleaving."""

from __future__ import annotations

import hashlib

import numpy as np
from numpy.typing import ArrayLike

from .seeds import pcg64, purpose_digest
from .types import BitArray


def _bits(values: ArrayLike) -> BitArray:
    array = np.asarray(values, dtype=np.uint8).reshape(-1)
    if ((array != 0) & (array != 1)).any():
        raise ValueError("expected a binary array")
    return array


def xor_scramble(bits: ArrayLike, layer_digest: bytes) -> BitArray:
    values = _bits(bits)
    generator = pcg64(purpose_digest(layer_digest, "scramble"))
    mask = generator.integers(0, 2, size=values.size, dtype=np.uint8)
    return np.bitwise_xor(values, mask)


def interleave(bits: ArrayLike, layer_digest: bytes) -> tuple[BitArray, BitArray]:
    values = _bits(bits)
    generator = pcg64(purpose_digest(layer_digest, "interleave"))
    permutation = generator.permutation(values.size).astype(np.int64)
    return values[permutation], permutation


def deinterleave(
    bits: ArrayLike,
    layer_digest: bytes,
) -> tuple[BitArray, BitArray]:
    values = _bits(bits)
    generator = pcg64(purpose_digest(layer_digest, "interleave"))
    permutation = generator.permutation(values.size).astype(np.int64)
    restored = np.empty_like(values)
    restored[permutation] = values
    return restored, permutation


def permutation_sha256(permutation: ArrayLike) -> str:
    values = np.ascontiguousarray(np.asarray(permutation, dtype="<i8"))
    digest = hashlib.sha256()
    digest.update(b"ctsteg-pcg64-permutation-v1\0")
    digest.update(values.size.to_bytes(8, "big"))
    digest.update(values.tobytes(order="C"))
    return digest.hexdigest()
