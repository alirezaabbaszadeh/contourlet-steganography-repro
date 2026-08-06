"""Fixed 127-byte digital header and its RS(255,127) protection."""

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
_LAYER_CRC_FIELDS = struct.Struct(">II")

FLAG_COMPLETE_PAYLOAD_CRC = 0b0000_0001
FLAG_LAYER_CRCS = 0b0000_0010


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
    base_crc32: int = 0
    detail_crc32: int = 0

    def validate(self) -> "DigitalHeader":
        if self.format_version not in {1, 2}:
            raise ValueError("unsupported header format version")
        if self.format_version == 1 and self.method is MethodId.C3_NP:
            raise ValueError("C3_NP is defined only for format version 2")
        if self.secret_width != 128 or self.secret_height != 128:
            raise ValueError("digital formats require a 128x128 secret")
        if self.base_bits != 4 or self.detail_bits != 4:
            raise ValueError("digital formats require a 4+4 bit split")
        if self.payload_bits != 222_360:
            raise ValueError("digital formats require 222,360 embedded bits")
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
        expected_flags = (
            FLAG_COMPLETE_PAYLOAD_CRC
            if self.format_version == 1
            else FLAG_COMPLETE_PAYLOAD_CRC | FLAG_LAYER_CRCS
        )
        if self.flags != expected_flags:
            raise ValueError(
                f"format version {self.format_version} requires flags "
                f"0b{expected_flags:08b}"
            )
        if len(self.config_digest) != 32:
            raise ValueError("config_digest must contain 32 bytes")
        for value in (self.interleaver_seed_id, self.scrambler_seed_id):
            if not 0 <= value < 2**64:
                raise ValueError("seed identifiers must fit in uint64")
        for name, value in (
            ("payload_crc32", self.payload_crc32),
            ("base_crc32", self.base_crc32),
            ("detail_crc32", self.detail_crc32),
        ):
            if not 0 <= value < 2**32:
                raise ValueError(f"{name} must fit in uint32")
        if self.format_version == 1 and (self.base_crc32 or self.detail_crc32):
            raise ValueError("format version 1 requires zero layer CRC fields")
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
    if value.format_version == 1:
        reserved = bytes(_RESERVED_BYTES)
    else:
        reserved = _LAYER_CRC_FIELDS.pack(
            value.base_crc32,
            value.detail_crc32,
        ) + bytes(_RESERVED_BYTES - _LAYER_CRC_FIELDS.size)
    protected = prefix + reserved
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
    format_version = values[1]
    reserved = protected[_PREFIX.size :]
    if format_version == 1:
        if any(reserved):
            raise ValueError("format-v1 header reserved bytes are not zero")
        base_crc32 = 0
        detail_crc32 = 0
    elif format_version == 2:
        base_crc32, detail_crc32 = _LAYER_CRC_FIELDS.unpack(
            reserved[: _LAYER_CRC_FIELDS.size]
        )
        if any(reserved[_LAYER_CRC_FIELDS.size :]):
            raise ValueError("format-v2 trailing reserved bytes are not zero")
    else:
        raise ValueError("unsupported header format version")
    try:
        method = MethodId(values[2])
    except ValueError as error:
        raise ValueError("unknown header method identifier") from error
    return DigitalHeader(
        format_version=format_version,
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
        base_crc32=base_crc32,
        detail_crc32=detail_crc32,
    ).validate()


def encode_header(header: DigitalHeader) -> bytes:
    return encode_codeword(pack_header(header), data_symbols=RAW_HEADER_BYTES)


def decode_header(codeword: bytes) -> DigitalHeader:
    result = decode_codeword(codeword, data_symbols=RAW_HEADER_BYTES)
    if not result.success or result.data is None:
        raise ValueError(f"header RS decode failed: {result.reason}")
    return unpack_header(result.data)
