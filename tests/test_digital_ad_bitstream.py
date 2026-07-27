from __future__ import annotations

import unittest

import numpy as np

from ctsteg.digital_ad.bitplanes import (
    bits_to_bytes,
    bytes_to_bits,
    bytes_to_nibbles,
    nibbles_to_bytes,
    recombine_secret,
    split_secret,
)
from ctsteg.digital_ad.bitstream import (
    TOTAL_BITS,
    decode_bitstream,
    encode_bitstream,
)
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.header import decode_header, encode_header
from ctsteg.digital_ad.preprocessing import half_up_uint8
from ctsteg.digital_ad.randomization import (
    deinterleave,
    interleave,
    xor_scramble,
)
from ctsteg.digital_ad.reed_solomon import (
    decode_codeword,
    encode_codeword,
)
from ctsteg.digital_ad.seeds import layer_seed_digest
from ctsteg.digital_ad.types import MethodId


class DigitalBitstreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DigitalADConfig()
        rng = np.random.default_rng(2026)
        self.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)

    def test_half_up_rounding_is_not_bankers_rounding(self) -> None:
        values = np.asarray([-1.0, 0.49, 0.5, 1.5, 254.5, 300.0])
        observed = half_up_uint8(values)
        np.testing.assert_array_equal(
            observed,
            np.asarray([0, 0, 1, 2, 255, 255], dtype=np.uint8),
        )

    def test_split_pack_and_recombine_are_exact(self) -> None:
        all_values = np.tile(
            np.arange(256, dtype=np.uint8),
            64,
        ).reshape(128, 128)
        base, detail = split_secret(all_values)
        self.assertTrue(np.array_equal(recombine_secret(base, detail), all_values))
        for layer in (base, detail):
            packed = nibbles_to_bytes(layer)
            self.assertEqual(len(packed), 8_192)
            unpacked = bytes_to_nibbles(packed, shape=(128, 128))
            self.assertTrue(np.array_equal(unpacked, layer))
        bits = bytes_to_bits(bytes(range(256)))
        self.assertEqual(bits_to_bytes(bits), bytes(range(256)))

    def test_rs_corrects_to_bound_and_records_beyond_bound(self) -> None:
        for data_symbols, bound in ((127, 64), (191, 32)):
            data = bytes((index * 13 + 5) % 256 for index in range(data_symbols))
            encoded = bytearray(
                encode_codeword(data, data_symbols=data_symbols)
            )
            for index in range(bound):
                encoded[(index * 3) % 255] ^= (index % 254) + 1
            decoded = decode_codeword(bytes(encoded), data_symbols=data_symbols)
            self.assertTrue(decoded.success)
            self.assertEqual(decoded.corrected_symbols, bound)
            self.assertEqual(decoded.data, data)

            beyond = bytearray(
                encode_codeword(data, data_symbols=data_symbols)
            )
            for index in range(bound + 1):
                beyond[(index * 7 + 3) % 255] ^= (index % 254) + 1
            failed = decode_codeword(bytes(beyond), data_symbols=data_symbols)
            self.assertFalse(failed.success)
            self.assertIsNone(failed.data)

    def test_randomization_round_trips_deterministically(self) -> None:
        digest = layer_seed_digest(2026, "pair", MethodId.C3_A_D, "base")
        values = np.arange(4096, dtype=np.uint16).astype(np.uint8) & 1
        scrambled = xor_scramble(values, digest)
        np.testing.assert_array_equal(xor_scramble(scrambled, digest), values)
        shuffled, first_permutation = interleave(scrambled, digest)
        restored, second_permutation = deinterleave(shuffled, digest)
        np.testing.assert_array_equal(restored, scrambled)
        np.testing.assert_array_equal(first_permutation, second_permutation)

    def test_all_four_bitstreams_are_exact_and_deterministic(self) -> None:
        for method in MethodId:
            first = encode_bitstream(
                self.secret,
                pair_id="fixture",
                method=method,
                config=self.config,
            )
            second = encode_bitstream(
                self.secret,
                pair_id="fixture",
                method=method,
                config=self.config,
            )
            self.assertEqual(first.bits.size, TOTAL_BITS)
            np.testing.assert_array_equal(first.bits, second.bits)
            decoded = decode_bitstream(
                first.bits,
                pair_id="fixture",
                expected_method=method,
                config=self.config,
            )
            self.assertTrue(decoded.success)
            np.testing.assert_array_equal(decoded.recovered_secret, self.secret)
            header = decode_header(encode_header(first.header))
            self.assertEqual(header, first.header)

    def test_pair_identity_changes_transport_and_wrong_pair_fails(self) -> None:
        first = encode_bitstream(
            self.secret,
            pair_id="pair-a",
            method=MethodId.C3_A_D,
            config=self.config,
        )
        second = encode_bitstream(
            self.secret,
            pair_id="pair-b",
            method=MethodId.C3_A_D,
            config=self.config,
        )
        self.assertFalse(np.array_equal(first.body_bits, second.body_bits))
        wrong = decode_bitstream(
            first.bits,
            pair_id="pair-b",
            expected_method=MethodId.C3_A_D,
            config=self.config,
        )
        self.assertFalse(wrong.success)
        self.assertIsNone(wrong.recovered_secret)


if __name__ == "__main__":
    unittest.main()
