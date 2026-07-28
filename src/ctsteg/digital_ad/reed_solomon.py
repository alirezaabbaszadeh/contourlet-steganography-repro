"""Self-contained full-length Reed--Solomon codecs for format version 1.

The implementation uses GF(2^8), primitive polynomial 0x11D, generator 2,
first consecutive root 0, and systematic 255-byte codewords.  Decoding uses
Berlekamp--Massey, Chien search, and a GF(256) linear solve for magnitudes.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence


PRIMITIVE_POLYNOMIAL = 0x11D
FIELD_GENERATOR = 2
CODEWORD_BYTES = 255


def _build_tables() -> tuple[tuple[int, ...], tuple[int, ...]]:
    exponent = [0] * 512
    logarithm = [0] * 256
    value = 1
    for index in range(255):
        exponent[index] = value
        logarithm[value] = index
        value <<= 1
        if value & 0x100:
            value ^= PRIMITIVE_POLYNOMIAL
    for index in range(255, 512):
        exponent[index] = exponent[index - 255]
    return tuple(exponent), tuple(logarithm)


_EXP, _LOG = _build_tables()


def gf_mul(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    return _EXP[_LOG[left] + _LOG[right]]


def gf_div(numerator: int, denominator: int) -> int:
    if denominator == 0:
        raise ZeroDivisionError("division by zero in GF(256)")
    if numerator == 0:
        return 0
    return _EXP[(_LOG[numerator] - _LOG[denominator]) % 255]


def gf_pow(value: int, exponent: int) -> int:
    if exponent == 0:
        return 1
    if value == 0:
        return 0
    return _EXP[(_LOG[value] * exponent) % 255]


def _poly_mul(left: Sequence[int], right: Sequence[int]) -> list[int]:
    output = [0] * (len(left) + len(right) - 1)
    for left_index, left_value in enumerate(left):
        if left_value == 0:
            continue
        for right_index, right_value in enumerate(right):
            if right_value:
                output[left_index + right_index] ^= gf_mul(
                    left_value,
                    right_value,
                )
    return output


def _poly_eval_descending(coefficients: Sequence[int], value: int) -> int:
    result = 0
    for coefficient in coefficients:
        result = gf_mul(result, value) ^ coefficient
    return result


def _poly_eval_ascending(coefficients: Sequence[int], value: int) -> int:
    result = 0
    power = 1
    for coefficient in coefficients:
        result ^= gf_mul(coefficient, power)
        power = gf_mul(power, value)
    return result


@lru_cache(maxsize=4)
def generator_polynomial(parity_symbols: int) -> tuple[int, ...]:
    if not 1 <= parity_symbols < CODEWORD_BYTES:
        raise ValueError("parity symbol count must be within [1,254]")
    polynomial = [1]
    for root in range(parity_symbols):
        polynomial = _poly_mul(
            polynomial,
            [1, gf_pow(FIELD_GENERATOR, root)],
        )
    return tuple(polynomial)


@dataclass(frozen=True)
class RSDecodeResult:
    data: bytes | None
    corrected_codeword: bytes | None
    corrected_symbols: int
    success: bool
    reason: str | None = None


@dataclass(frozen=True)
class LayerRSResult:
    data: bytes | None
    failures: tuple[int, ...]
    corrected_symbols: tuple[int, ...]

    @property
    def success(self) -> bool:
        return self.data is not None and not self.failures


@dataclass(frozen=True)
class RSProfile:
    name: str
    data_symbols: tuple[int, ...]
    padding_bytes: int

    @property
    def codeword_count(self) -> int:
        return len(self.data_symbols)

    @property
    def encoded_bytes(self) -> int:
        return self.codeword_count * CODEWORD_BYTES

    @property
    def input_bytes(self) -> int:
        return sum(self.data_symbols)


STRONG_K = 127
WEAK_K = 191
STRONG_T = 64
WEAK_T = 32

SYMMETRIC_PROFILE = RSProfile(
    name="symmetric_32x127_22x191",
    data_symbols=(STRONG_K,) * 32 + (WEAK_K,) * 22,
    padding_bytes=74,
)
BASE_UEP_PROFILE = RSProfile(
    name="base_rs_255_127",
    data_symbols=(STRONG_K,) * 65,
    padding_bytes=63,
)
DETAIL_UEP_PROFILE = RSProfile(
    name="detail_rs_255_191",
    data_symbols=(WEAK_K,) * 43,
    padding_bytes=21,
)


def encode_codeword(data: bytes, *, data_symbols: int) -> bytes:
    if len(data) != data_symbols:
        raise ValueError(f"expected {data_symbols} data symbols")
    parity_symbols = CODEWORD_BYTES - data_symbols
    generator = generator_polynomial(parity_symbols)
    working = list(data) + [0] * parity_symbols
    for data_index in range(data_symbols):
        coefficient = working[data_index]
        if coefficient == 0:
            continue
        for generator_index in range(1, len(generator)):
            working[data_index + generator_index] ^= gf_mul(
                generator[generator_index],
                coefficient,
            )
    return data + bytes(working[data_symbols:])


def syndromes(codeword: bytes, parity_symbols: int) -> tuple[int, ...]:
    if len(codeword) != CODEWORD_BYTES:
        raise ValueError("RS codeword must contain 255 symbols")
    return tuple(
        _poly_eval_descending(codeword, gf_pow(FIELD_GENERATOR, root))
        for root in range(parity_symbols)
    )


def _error_locator(syndrome_values: Sequence[int]) -> list[int]:
    count = len(syndrome_values)
    current = [1] + [0] * count
    previous = [1] + [0] * count
    degree = 0
    shift = 1
    previous_discrepancy = 1
    for position in range(count):
        discrepancy = syndrome_values[position]
        for index in range(1, degree + 1):
            discrepancy ^= gf_mul(
                current[index],
                syndrome_values[position - index],
            )
        if discrepancy == 0:
            shift += 1
            continue
        snapshot = current.copy()
        scale = gf_div(discrepancy, previous_discrepancy)
        for index in range(0, count + 1 - shift):
            if previous[index]:
                current[index + shift] ^= gf_mul(scale, previous[index])
        if 2 * degree <= position:
            degree = position + 1 - degree
            previous = snapshot
            previous_discrepancy = discrepancy
            shift = 1
        else:
            shift += 1
    return current[: degree + 1]


def _find_error_positions(
    locator: Sequence[int],
    *,
    codeword_length: int,
) -> list[int]:
    degree = len(locator) - 1
    positions: list[int] = []
    for position in range(codeword_length):
        exponent = codeword_length - 1 - position
        inverse_location = gf_pow(FIELD_GENERATOR, -exponent)
        if _poly_eval_ascending(locator, inverse_location) == 0:
            positions.append(position)
    if len(positions) != degree:
        raise ValueError(
            f"error locator degree {degree} produced {len(positions)} roots"
        )
    return positions


def _solve_gf(matrix: list[list[int]], vector: list[int]) -> list[int]:
    size = len(vector)
    augmented = [
        list(matrix[row]) + [vector[row]]
        for row in range(size)
    ]
    for column in range(size):
        pivot = next(
            (
                row
                for row in range(column, size)
                if augmented[row][column] != 0
            ),
            None,
        )
        if pivot is None:
            raise ValueError("singular GF(256) error-magnitude system")
        if pivot != column:
            augmented[column], augmented[pivot] = (
                augmented[pivot],
                augmented[column],
            )
        inverse = gf_div(1, augmented[column][column])
        augmented[column] = [
            gf_mul(value, inverse) for value in augmented[column]
        ]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            augmented[row] = [
                value ^ gf_mul(factor, pivot_value)
                for value, pivot_value in zip(
                    augmented[row],
                    augmented[column],
                    strict=True,
                )
            ]
    return [augmented[index][-1] for index in range(size)]


def decode_codeword(codeword: bytes, *, data_symbols: int) -> RSDecodeResult:
    if len(codeword) != CODEWORD_BYTES:
        raise ValueError("RS codeword must contain 255 symbols")
    if not 1 <= data_symbols < CODEWORD_BYTES:
        raise ValueError("data symbol count must be within [1,254]")
    parity_symbols = CODEWORD_BYTES - data_symbols
    syndrome_values = syndromes(codeword, parity_symbols)
    if not any(syndrome_values):
        return RSDecodeResult(
            data=codeword[:data_symbols],
            corrected_codeword=codeword,
            corrected_symbols=0,
            success=True,
        )
    try:
        locator = _error_locator(syndrome_values)
        error_count = len(locator) - 1
        if error_count == 0 or error_count > parity_symbols // 2:
            raise ValueError(
                f"estimated {error_count} errors exceeds correction capacity"
            )
        positions = _find_error_positions(
            locator,
            codeword_length=CODEWORD_BYTES,
        )
        locations = [
            gf_pow(FIELD_GENERATOR, CODEWORD_BYTES - 1 - position)
            for position in positions
        ]
        matrix = [
            [gf_pow(location, row) for location in locations]
            for row in range(error_count)
        ]
        magnitudes = _solve_gf(
            matrix,
            list(syndrome_values[:error_count]),
        )
        corrected = bytearray(codeword)
        for position, magnitude in zip(positions, magnitudes, strict=True):
            corrected[position] ^= magnitude
        corrected_bytes = bytes(corrected)
        if any(syndromes(corrected_bytes, parity_symbols)):
            raise ValueError("non-zero syndrome remains after correction")
        return RSDecodeResult(
            data=corrected_bytes[:data_symbols],
            corrected_codeword=corrected_bytes,
            corrected_symbols=error_count,
            success=True,
        )
    except ValueError as error:
        return RSDecodeResult(
            data=None,
            corrected_codeword=None,
            corrected_symbols=0,
            success=False,
            reason=str(error),
        )


def encode_layer(data: bytes, profile: RSProfile) -> bytes:
    if len(data) + profile.padding_bytes != profile.input_bytes:
        raise ValueError(
            f"profile {profile.name} expects {profile.input_bytes} bytes "
            f"including {profile.padding_bytes} bytes of padding"
        )
    padded = data + bytes(profile.padding_bytes)
    offset = 0
    codewords: list[bytes] = []
    for data_symbols in profile.data_symbols:
        block = padded[offset : offset + data_symbols]
        if len(block) != data_symbols:
            raise AssertionError("profile partition did not consume full block")
        codewords.append(encode_codeword(block, data_symbols=data_symbols))
        offset += data_symbols
    if offset != len(padded):
        raise AssertionError("profile did not consume the complete padded layer")
    return b"".join(codewords)


def decode_layer(encoded: bytes, profile: RSProfile) -> LayerRSResult:
    if len(encoded) != profile.encoded_bytes:
        raise ValueError(
            f"profile {profile.name} expects {profile.encoded_bytes} bytes"
        )
    decoded_blocks: list[bytes] = []
    failures: list[int] = []
    corrected: list[int] = []
    for index, data_symbols in enumerate(profile.data_symbols):
        start = index * CODEWORD_BYTES
        result = decode_codeword(
            encoded[start : start + CODEWORD_BYTES],
            data_symbols=data_symbols,
        )
        corrected.append(result.corrected_symbols)
        if not result.success or result.data is None:
            failures.append(index)
        else:
            decoded_blocks.append(result.data)
    if failures:
        return LayerRSResult(
            data=None,
            failures=tuple(failures),
            corrected_symbols=tuple(corrected),
        )
    padded = b"".join(decoded_blocks)
    if profile.padding_bytes:
        data = padded[: -profile.padding_bytes]
        padding = padded[-profile.padding_bytes :]
        if any(padding):
            return LayerRSResult(
                data=None,
                failures=(profile.codeword_count,),
                corrected_symbols=tuple(corrected),
            )
    else:
        data = padded
    return LayerRSResult(
        data=data,
        failures=(),
        corrected_symbols=tuple(corrected),
    )


def profile_codeword_sizes(profile: RSProfile) -> Iterable[tuple[int, int]]:
    for data_symbols in profile.data_symbols:
        yield data_symbols, CODEWORD_BYTES - data_symbols
