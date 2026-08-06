from __future__ import annotations

import unittest

import numpy as np

from ctsteg.digital_ad.bitstream import (
    decode_bitstream,
    encode_bitstream,
    merge_body,
)
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.failure_severity import (
    evaluate_internal_failure_severity,
)
from ctsteg.digital_ad.randomization import deinterleave, interleave
from ctsteg.digital_ad.types import MethodId


class FailureSeverityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(20260808)
        cls.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cls.config = DigitalADConfig(format_version=2)

    @staticmethod
    def _damage_transport_symbols(
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

    def _encoded(self, pair_id: str):
        return encode_bitstream(
            self.secret,
            pair_id=pair_id,
            method=MethodId.C3_A_D,
            config=self.config,
            payload_fraction=1.0,
        )

    def test_clean_stream_has_zero_overload_and_complete_recovery(self) -> None:
        pair_id = "severity-clean"
        encoded = self._encoded(pair_id)
        outcome = decode_bitstream(
            encoded.bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.config,
        )
        report = evaluate_internal_failure_severity(
            encoded=encoded,
            extracted_bits=encoded.bits,
            outcome=outcome,
        )
        self.assertEqual(report["failure_stage"], "S0_COMPLETE")
        self.assertEqual(report["header"]["overload_max"], 0)
        self.assertEqual(report["base"]["overload_max"], 0)
        self.assertEqual(report["detail"]["overload_max"], 0)
        self.assertEqual(report["recovery"]["payload_correct_fraction"], 1.0)
        self.assertEqual(report["recovery"]["unknown_bit_fraction"], 0.0)

    def test_correctable_detail_errors_are_measured_without_failure(self) -> None:
        pair_id = "severity-correctable"
        encoded = self._encoded(pair_id)
        damaged_detail = self._damage_transport_symbols(
            encoded.detail.transport_bits,
            digest=encoded.detail.layer_digest,
            symbol_count=5,
        )
        bits = np.concatenate(
            (
                encoded.header_bits,
                merge_body(
                    MethodId.C3_A_D,
                    encoded.base.transport_bits,
                    damaged_detail,
                ),
            )
        )
        outcome = decode_bitstream(
            bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.config,
        )
        report = evaluate_internal_failure_severity(
            encoded=encoded,
            extracted_bits=bits,
            outcome=outcome,
        )
        first = report["detail"]["records"][0]
        self.assertTrue(outcome.success)
        self.assertEqual(report["failure_stage"], "S0_COMPLETE")
        self.assertEqual(first["observed_symbol_errors"], 5)
        self.assertEqual(first["ecc_overload"], 0)
        self.assertEqual(first["decoder_status"], "success")
        self.assertEqual(first["corrected_symbols"], 5)

    def test_detail_overload_quantifies_base_only_failure_gap(self) -> None:
        pair_id = "severity-base-only"
        encoded = self._encoded(pair_id)
        damaged_detail = self._damage_transport_symbols(
            encoded.detail.transport_bits,
            digest=encoded.detail.layer_digest,
            symbol_count=40,
        )
        bits = np.concatenate(
            (
                encoded.header_bits,
                merge_body(
                    MethodId.C3_A_D,
                    encoded.base.transport_bits,
                    damaged_detail,
                ),
            )
        )
        outcome = decode_bitstream(
            bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.config,
        )
        report = evaluate_internal_failure_severity(
            encoded=encoded,
            extracted_bits=bits,
            outcome=outcome,
        )
        first = report["detail"]["records"][0]
        self.assertEqual(outcome.validity_state, "valid_base_only_recovery")
        self.assertEqual(report["failure_stage"], "S1_BASE_ONLY")
        self.assertEqual(first["observed_symbol_errors"], 40)
        self.assertEqual(first["correction_radius"], 32)
        self.assertEqual(first["ecc_overload"], 8)
        self.assertEqual(report["base"]["raw_correct_fraction"], 1.0)
        self.assertGreater(report["detail"]["failed"], 0)
        self.assertGreater(report["recovery"]["unknown_bit_fraction"], 0.0)

    def test_header_overload_is_distinct_from_payload_failure(self) -> None:
        pair_id = "severity-header"
        encoded = self._encoded(pair_id)
        bits = encoded.bits.copy()
        for symbol_index in range(70):
            bits[symbol_index * 8] ^= np.uint8(1)
        outcome = decode_bitstream(
            bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_A_D,
            config=self.config,
        )
        report = evaluate_internal_failure_severity(
            encoded=encoded,
            extracted_bits=bits,
            outcome=outcome,
        )
        header = report["header"]["records"][0]
        self.assertFalse(outcome.header_valid)
        self.assertEqual(report["failure_stage"], "S4_HEADER_FAILURE")
        self.assertEqual(header["observed_symbol_errors"], 70)
        self.assertEqual(header["correction_radius"], 64)
        self.assertEqual(header["ecc_overload"], 6)

    def test_absent_detail_is_not_applicable_not_zero(self) -> None:
        pair_id = "severity-no-detail"
        encoded = encode_bitstream(
            self.secret,
            pair_id=pair_id,
            method=MethodId.C3_NP,
            config=self.config,
            payload_fraction=0.50,
        )
        outcome = decode_bitstream(
            encoded.bits,
            pair_id=pair_id,
            expected_method=MethodId.C3_NP,
            config=self.config,
            expected_payload_fraction=0.50,
        )
        report = evaluate_internal_failure_severity(
            encoded=encoded,
            extracted_bits=encoded.bits,
            outcome=outcome,
        )
        self.assertEqual(report["failure_stage"], "S0_COMPLETE")
        self.assertEqual(report["detail"]["applicability"], "not_applicable")
        self.assertIsNone(report["detail"]["total"])
        self.assertIsNone(report["detail"]["raw_correct_fraction"])
        self.assertEqual(report["recovery"]["payload_correct_fraction"], 1.0)


if __name__ == "__main__":
    unittest.main()
