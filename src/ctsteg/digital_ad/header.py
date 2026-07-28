"""Fixed 127-byte digital A+D header and its RS(255,127) protection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import struct
import zlib
from typing import Any, Mapping

from .reed_solomon import decode_codeword, encode_codeword
from .types import MethodId


MAGIC = b"CTAD"
RAW_HEADER_BYTES = 127
ENCODED_HEADER_BYTES = 255
HEADER_BITS = 2_040
_CRC_OFFSET = 123
_PREFIX = struct.Struct(">4sBBBBHHBBHHHHIQQI32s")
_RESERVED_BYTES = _CRC_OFFSET - _PREFIX.size


def canonical_config_digest(config: Mapping[str, Any]) -> bytes:
    payload = json.dumps(
        dict(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).digest()


@dataclass(frozen=True)
class DigitalHeader:
    format_version: int
    method: MethodId
    flags: int
    ecc_mode: int
    secret_width: int
    secret_height: int
    base_bits: int
    detail_bits: int
    base_codewords: int
    detail_codewords: int
    base_padding: int
    detail_padding: int
    payload_bits: int
    interleaver_seed_id: int
    scrambler_seed_id: int
    payload_crc32: int
    config_digest: bytes

    def validate(self) -> "DigitalHeader":
        if self.format_version != 1:
            raise ValueError("unsupported header format version")
        if self.secret_width != 128 or self.secret_height != 128:
            raise ValueError("format version 1 requires a 128x128 secret")
        if self.base_bits != 4 or self.detail_bits != 4:
            raise ValueError("format version 1 requires a 4+4 bit split")
        if self.payload_bits != 222_360:
            raise ValueError("format version 1 requires 222,360 embedded bits")
        if self.ecc_mode not in {0, 1}:
            raise ValueError("unknown ECC mode")
        expected = (
            (54, 54, 74, 74, 0)
            if not self.method.uses_unequal_protection
            else (65, 43, 63, 21, 1)
        )
        actual = (
            self.base_codewords,
            self.detail_codewords,
            self.base_padding,
            self.detail_padding,
            self.ecc_mode,
        )
        if actual != expected:
            raise ValueError(
                f"header ECC fields {actual} do not match method {self.method.name}"
            )
        if not 0 <= self.flags <= 255:
            raise ValueError("header flags must fit in one byte")
        if len(self.config_digest) != 32:
            raise ValueError("config_digest must contain 32 bytes")
        for value in (self.interleaver_seed_id, self.scrambler_seed_id):
            if not 0 <= value < 2**64:
                raise ValueError("seed identifiers must fit in uint64")
        if not 0 <= self.payload_crc32 < 2**32:
            raise ValueError("payload CRC must fit in uint32")
        return self


def pack_header(header: DigitalHeader) -> bytes:
    value = header.validate()
    prefix = _PREFIX.pack(
        MAGIC,
        value.format_version,
        int(value.method),
        value.flags,
        value.ecc_mode,
        value.secret_width,
        value.secret_height,
        value.base_bits,
        value.detail_bits,
        value.base_codewords,
        value.detail_codewords,
        value.base_padding,
        value.detail_padding,
        value.payload_bits,
        value.interleaver_seed_id,
        value.scrambler_seed_id,
        value.payload_crc32,
        value.config_digest,
    )
    protected = prefix + bytes(_RESERVED_BYTES)
    if len(protected) != _CRC_OFFSET:
        raise AssertionError("header prefix size is not 123 bytes")
    crc = zlib.crc32(protected) & 0xFFFFFFFF
    return protected + crc.to_bytes(4, "big")


def unpack_header(payload: bytes) -> DigitalHeader:
    if len(payload) != RAW_HEADER_BYTES:
        raise ValueError("raw header must contain exactly 127 bytes")
    protected = payload[:_CRC_OFFSET]
    expected_crc = int.from_bytes(payload[_CRC_OFFSET:], "big")
    actual_crc = zlib.crc32(protected) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise ValueError("header CRC32 mismatch")
    values = _PREFIX.unpack(protected[: _PREFIX.size])
    if values[0] != MAGIC:
        raise ValueError("header magic mismatch")
    if any(protected[_PREFIX.size :]):
        raise ValueError("header reserved bytes are not zero")
    try:
        method = MethodId(values[2])
    except ValueError as error:
        raise ValueError("unknown header method identifier") from error
    return DigitalHeader(
        format_version=values[1],
        method=method,
        flags=values[3],
        ecc_mode=values[4],
        secret_width=values[5],
        secret_height=values[6],
        base_bits=values[7],
        detail_bits=values[8],
        base_codewords=values[9],
        detail_codewords=values[10],
        base_padding=values[11],
        detail_padding=values[12],
        payload_bits=values[13],
        interleaver_seed_id=values[14],
        scrambler_seed_id=values[15],
        payload_crc32=values[16],
        config_digest=values[17],
    ).validate()


def encode_header(header: DigitalHeader) -> bytes:
    return encode_codeword(pack_header(header), data_symbols=RAW_HEADER_BYTES)


def decode_header(codeword: bytes) -> DigitalHeader:
    result = decode_codeword(codeword, data_symbols=RAW_HEADER_BYTES)
    if not result.success or result.data is None:
        raise ValueError(f"header RS decode failed: {result.reason}")
    return unpack_header(result.data)
