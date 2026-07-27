"""Canonical SHA-256 seed derivation and deterministic PCG64 streams."""

from __future__ import annotations

import hashlib

import numpy as np

from .types import MethodId


_DOMAIN = b"ctsteg-digital-ad-v1\0"


def layer_seed_digest(
    master_seed: int,
    pair_id: str,
    method: MethodId,
    layer_name: str,
) -> bytes:
    if not 0 <= master_seed < 2**128:
        raise ValueError("master_seed must fit in unsigned 128 bits")
    pair = pair_id.encode("utf-8")
    layer = layer_name.encode("ascii")
    if len(pair) > 65_535 or len(layer) > 255:
        raise ValueError("seed identity field is too long")
    material = b"".join(
        (
            _DOMAIN,
            master_seed.to_bytes(16, "big"),
            len(pair).to_bytes(2, "big"),
            pair,
            int(method).to_bytes(1, "big"),
            len(layer).to_bytes(1, "big"),
            layer,
        )
    )
    return hashlib.sha256(material).digest()


def purpose_digest(layer_digest: bytes, purpose: str) -> bytes:
    if len(layer_digest) != 32:
        raise ValueError("layer digest must contain 32 bytes")
    return hashlib.sha256(layer_digest + b"\0" + purpose.encode("ascii")).digest()


def pcg64(digest: bytes) -> np.random.Generator:
    if len(digest) != 32:
        raise ValueError("PCG64 seed digest must contain 32 bytes")
    seed = int.from_bytes(digest[:16], "big")
    return np.random.Generator(np.random.PCG64(seed))


def seed_id(*digests: bytes) -> int:
    if not digests:
        raise ValueError("at least one seed digest is required")
    aggregate = hashlib.sha256(b"".join(digests)).digest()
    return int.from_bytes(aggregate[:8], "big")
