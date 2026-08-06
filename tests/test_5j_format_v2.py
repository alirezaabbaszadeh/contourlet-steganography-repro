from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from ctsteg.digital_ad.bitstream import (
    HEADER_BITS,
    TRANSPORT_BLOCK_BITS,
    decode_bitstream,
    encode_bitstream,
    merge_body,
    profiles_for_method,
)
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.randomization import deinterleave, interleave
from ctsteg.digital_ad.types import MethodId


class FormatV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(20260806)
        cls.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cls.v1 = DigitalADConfig(format_version=1)
        cls.v2 = DigitalADConfig(format_version=2)

    def test_v1_clean_decode_remains_exact_and_has_no_layer_validity(self) -> None:
        encoded = encode_bitstream(
            self.secret,
            pair_id="v1-compatibility",
            method=MethodId.C3_A_D,
            config=self.v1,
        )
        outcome = decode_bitstream(
            encoded.bits,
            pair_id="v1-compatibility",
            expected_method=MethodId.C3_A_D,
            config=self.v1,
        )
        self.assertTrue(outcome.success)
        self.assertEqual(outcome.validity_state, "complete_valid_recovery")
        self.assertIsNone(outcome.base_crc_valid)
        self.assertIsNone(outcome.detail_crc_valid)
        self.assertIsNone(outcome.base_reconstruction)
        np.testing.assert_array_equal(outcome.recovered_secret, self.secret)

    def test_v2_clean_decode_validates_complete_base_and_detail(self) -> None:
        encoded = encode_bitstream(
            self.secret,
            pair_id="v2-clean",
            method=MethodId.C3_A_D,
            config=self.v2,
        )
        self.assertEqual(encoded.bits.size, 222_360)
        outcome = decode_bitstream(
            encoded.bits,
            pair_id="v2-clean",
            expected_method=MethodId.C3_A_D,
            config=self.v2,
        )
        self.assertTrue(outcome.success)
        self.assertTrue(outcome.base_only_success)
        self.assertTrue(outcome.payload_crc_valid)
        self.assertTrue(outcome.base_crc_valid)
        self.assertTrue(outcome.detail_crc_valid)
        self.assertEqual(outcome.validity_state, "complete_valid_recovery")
        np.testing.assert_array_equal(outcome.recovered_secret, self.secret)
        expected_base_only = self.secret & np.uint8(0xF0)
        np.testing.assert_array_equal(outcome.base_reconstruction, expected_base_only)

    @staticmethod
    def _damage_symbols(
        transport_bits: np.ndarray,
        *,
        digest: bytes,
        symbol_count: int,
    ) -> np.ndarray:
        deinterleaved, _ = deinterleave(transport_bits, digest)
        damaged = deinterleaved.copy()
        for symbol_index in range(symbol_count):
            damaged[symbol_index * 8] ^= np.uint8(1)
        result, _ = interleave(damaged, digest)
        return result

    def test_v2_detail_failure_produces_valid_base_only_recovery(self) -> None:
        pair_id = "v2-detail-failure"
        encoded = encode_bitstream(
            self.secret,
            pair_id=pair_id,
            method=MethodId.C3_A_D,
            config=self.v2,
        )
        damaged_detail = self._damage_symbols(
            encoded.detail.transport_bits,
            digest=encoded.detail.layer_digest,
            symbol_count=40,
        )
        damaged_body = merge_body(
            MethodId.C3_A_D,
            encoded.base.transport_bits,
            damaged_detail,
        )
        damaged_bits = np.concatenate((encoded.header_bits, damaged_body))
        outcome = decode_bitstream(
            damaged_bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.v2,
        )
        self.assertFalse(outcome.success)
        self.assertTrue(outcome.base_only_success)
        self.assertTrue(outcome.base_crc_valid)
        self.assertFalse(outcome.detail_crc_valid)
        self.assertFalse(outcome.payload_crc_valid)
        self.assertEqual(outcome.validity_state, "valid_base_only_recovery")
        self.assertIsNone(outcome.recovered_secret)
        np.testing.assert_array_equal(
            outcome.base_reconstruction,
            self.secret & np.uint8(0xF0),
        )

    def test_v2_base_failure_cannot_be_declared_base_only(self) -> None:
        pair_id = "v2-base-failure"
        encoded = encode_bitstream(
            self.secret,
            pair_id=pair_id,
            method=MethodId.C3_A_D,
            config=self.v2,
        )
        damaged_base = self._damage_symbols(
            encoded.base.transport_bits,
            digest=encoded.base.layer_digest,
            symbol_count=70,
        )
        damaged_body = merge_body(
            MethodId.C3_A_D,
            damaged_base,
            encoded.detail.transport_bits,
        )
        damaged_bits = np.concatenate((encoded.header_bits, damaged_body))
        outcome = decode_bitstream(
            damaged_bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.v2,
        )
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.base_only_success)
        self.assertFalse(outcome.base_crc_valid)
        self.assertIsNone(outcome.base_reconstruction)
        self.assertEqual(outcome.validity_state, "header_valid_no_valid_layer")

    def test_c3_np_is_adaptive_unequal_and_not_base_first(self) -> None:
        self.assertTrue(MethodId.C3_NP.uses_adaptive_allocation)
        self.assertTrue(MethodId.C3_NP.uses_unequal_protection)
        self.assertFalse(MethodId.C3_NP.uses_base_first_placement)
        self.assertTrue(MethodId.C3_A_D.uses_base_first_placement)
        self.assertEqual(
            profiles_for_method(MethodId.C3_NP),
            profiles_for_method(MethodId.C3_A_D),
        )

        base_first = np.zeros(TRANSPORT_BLOCK_BITS, dtype=np.uint8)
        base_second = np.ones(TRANSPORT_BLOCK_BITS, dtype=np.uint8)
        detail_first = np.tile(
            np.asarray([0, 1], dtype=np.uint8),
            TRANSPORT_BLOCK_BITS // 2,
        )
        base = np.concatenate((base_first, base_second))
        c3 = merge_body(MethodId.C3_A_D, base, detail_first)
        c3_np = merge_body(MethodId.C3_NP, base, detail_first)

        np.testing.assert_array_equal(c3[: 2 * TRANSPORT_BLOCK_BITS], base)
        np.testing.assert_array_equal(c3_np[:TRANSPORT_BLOCK_BITS], base_first)
        np.testing.assert_array_equal(
            c3_np[TRANSPORT_BLOCK_BITS : 2 * TRANSPORT_BLOCK_BITS],
            detail_first,
        )
        np.testing.assert_array_equal(
            c3_np[2 * TRANSPORT_BLOCK_BITS :],
            base_second,
        )

    def test_v2_config_digest_is_distinct_from_v1(self) -> None:
        encoded_v1 = encode_bitstream(
            self.secret,
            pair_id="format-identity",
            method=MethodId.C0_FIXED,
            config=self.v1,
        )
        encoded_v2 = encode_bitstream(
            self.secret,
            pair_id="format-identity",
            method=MethodId.C0_FIXED,
            config=replace(self.v1, format_version=2),
        )
        self.assertNotEqual(
            encoded_v1.header.config_digest,
            encoded_v2.header.config_digest,
        )
        self.assertNotEqual(encoded_v1.header.flags, encoded_v2.header.flags)
        self.assertEqual(encoded_v1.bits.size, encoded_v2.bits.size)


if __name__ == "__main__":
    unittest.main()
