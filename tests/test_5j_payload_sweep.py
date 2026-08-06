from __future__ import annotations

import unittest

import numpy as np

from ctsteg.digital_ad.adaptive import BandFeatures
from ctsteg.digital_ad.allocation import build_slot_plan
from ctsteg.digital_ad.bitplanes import (
    bytes_to_symbols,
    payload_layout,
    progressive_reference,
    split_secret_progressive,
    symbols_to_bytes,
)
from ctsteg.digital_ad.bitstream import decode_bitstream, encode_bitstream
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.payload_profiles import (
    profiles_for_payload,
    protected_payload_bits,
)
from ctsteg.digital_ad.types import MethodId


EXPECTED_PROTECTED_BITS = {
    "symmetric": {
        0.25: 57_120,
        0.50: 112_200,
        0.75: 167_280,
        1.00: 222_360,
    },
    "unequal": {
        0.25: 69_360,
        0.50: 134_640,
        0.75: 179_520,
        1.00: 222_360,
    },
}
EXPECTED_PROFILES = {
    "symmetric": {
        0.25: ((27, 37), (0, 0)),
        0.50: ((54, 74), (0, 0)),
        0.75: ((54, 74), (27, 37)),
        1.00: ((54, 74), (54, 74)),
    },
    "unequal": {
        0.25: ((33, 95), (0, 0)),
        0.50: ((65, 63), (0, 0)),
        0.75: ((65, 63), (22, 106)),
        1.00: ((65, 63), (43, 21)),
    },
}


class ProgressivePayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(20260807)
        cls.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cls.config = DigitalADConfig(format_version=2)

    def test_progressive_packing_round_trips_declared_symbols(self) -> None:
        for fraction in (0.25, 0.50, 0.75, 1.00):
            with self.subTest(fraction=fraction):
                base, detail, layout = split_secret_progressive(
                    self.secret,
                    payload_fraction=fraction,
                )
                base_payload = symbols_to_bytes(
                    base,
                    bits_per_symbol=layout.base_bits,
                )
                self.assertEqual(len(base_payload), layout.base_bytes)
                np.testing.assert_array_equal(
                    bytes_to_symbols(
                        base_payload,
                        shape=(128, 128),
                        bits_per_symbol=layout.base_bits,
                    ),
                    base,
                )
                if layout.detail_bits == 0:
                    self.assertIsNone(detail)
                    self.assertEqual(layout.detail_bytes, 0)
                else:
                    self.assertIsNotNone(detail)
                    assert detail is not None
                    detail_payload = symbols_to_bytes(
                        detail,
                        bits_per_symbol=layout.detail_bits,
                    )
                    self.assertEqual(len(detail_payload), layout.detail_bytes)
                    np.testing.assert_array_equal(
                        bytes_to_symbols(
                            detail_payload,
                            shape=(128, 128),
                            bits_per_symbol=layout.detail_bits,
                        ),
                        detail,
                    )

    def test_profile_counts_padding_and_protected_bits_are_exact(self) -> None:
        methods = (MethodId.C0_FIXED, MethodId.C3_A_D)
        for method in methods:
            family = "unequal" if method.uses_unequal_protection else "symmetric"
            for fraction in (0.25, 0.50, 0.75, 1.00):
                with self.subTest(method=method.name, fraction=fraction):
                    layout = payload_layout(fraction)
                    base, detail = profiles_for_payload(
                        method,
                        base_bits=layout.base_bits,
                        detail_bits=layout.detail_bits,
                    )
                    expected_base, expected_detail = EXPECTED_PROFILES[family][fraction]
                    self.assertEqual(
                        (base.codeword_count, base.padding_bytes),
                        expected_base,
                    )
                    self.assertEqual(
                        (detail.codeword_count, detail.padding_bytes),
                        expected_detail,
                    )
                    self.assertEqual(
                        protected_payload_bits(
                            method,
                            base_bits=layout.base_bits,
                            detail_bits=layout.detail_bits,
                        ),
                        EXPECTED_PROTECTED_BITS[family][fraction],
                    )

    def test_all_internal_sweep_methods_clean_decode_every_fraction(self) -> None:
        for method in (
            MethodId.C0_FIXED,
            MethodId.C3_NP,
            MethodId.C3_A_D,
        ):
            family = "unequal" if method.uses_unequal_protection else "symmetric"
            for fraction in (0.25, 0.50, 0.75, 1.00):
                with self.subTest(method=method.name, fraction=fraction):
                    encoded = encode_bitstream(
                        self.secret,
                        pair_id=f"payload-{method.name}-{fraction}",
                        method=method,
                        config=self.config,
                        payload_fraction=fraction,
                    )
                    self.assertEqual(
                        encoded.bits.size,
                        EXPECTED_PROTECTED_BITS[family][fraction],
                    )
                    self.assertEqual(
                        encoded.header.payload_bits,
                        EXPECTED_PROTECTED_BITS[family][fraction],
                    )
                    outcome = decode_bitstream(
                        encoded.bits,
                        pair_id=f"payload-{method.name}-{fraction}",
                        expected_method=method,
                        config=self.config,
                        expected_payload_fraction=fraction,
                    )
                    self.assertTrue(outcome.success, outcome.failures)
                    self.assertTrue(outcome.base_only_success)
                    self.assertTrue(outcome.payload_crc_valid)
                    self.assertTrue(outcome.base_crc_valid)
                    layout = payload_layout(fraction)
                    self.assertEqual(
                        outcome.detail_crc_valid,
                        None if layout.detail_bits == 0 else True,
                    )
                    np.testing.assert_array_equal(
                        outcome.recovered_secret,
                        progressive_reference(
                            self.secret,
                            payload_fraction=fraction,
                        ),
                    )
                    np.testing.assert_array_equal(
                        outcome.base_reconstruction,
                        self.secret & np.uint8(0xC0 if fraction == 0.25 else 0xF0),
                    )
                    self.assertEqual(
                        encoded.manifest["detail"]["applicability"],
                        "not_applicable" if layout.detail_bits == 0 else "applicable",
                    )

    def test_wrong_expected_fraction_is_a_header_identity_failure(self) -> None:
        encoded = encode_bitstream(
            self.secret,
            pair_id="fraction-mismatch",
            method=MethodId.C3_A_D,
            config=self.config,
            payload_fraction=0.25,
        )
        outcome = decode_bitstream(
            encoded.bits,
            pair_id="fraction-mismatch",
            expected_method=MethodId.C3_A_D,
            config=self.config,
            expected_payload_fraction=0.50,
        )
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.header_valid)
        self.assertEqual(outcome.validity_state, "header_failure")
        self.assertTrue(
            any("payload-fraction" in failure.reason for failure in outcome.failures)
        )

    def test_variable_slot_plan_matches_protected_stream_length(self) -> None:
        bands = [
            np.zeros((128, 512), dtype=np.float64)
            for _ in range(4)
        ]
        band_ids = [f"b{index}" for index in range(4)]
        features = tuple(
            BandFeatures(
                band_id=band_id,
                energy=1.0,
                variance=1.0,
                entropy=1.0,
                stability=1.0,
                energy_normalized=score,
                variance_normalized=score,
                entropy_normalized=score,
                stability_normalized=score,
                score=score,
                weight=0.75 + 0.5 * score,
            )
            for band_id, score in zip(
                band_ids,
                (0.2, 0.8, 0.4, 0.6),
                strict=True,
            )
        )
        for fraction, required_bits in EXPECTED_PROTECTED_BITS["unequal"].items():
            with self.subTest(fraction=fraction):
                c3 = build_slot_plan(
                    method=MethodId.C3_A_D,
                    bands=bands,
                    band_ids=band_ids,
                    features=features,
                    epsilon=1e-12,
                    required_bits=required_bits,
                )
                c3_np = build_slot_plan(
                    method=MethodId.C3_NP,
                    bands=bands,
                    band_ids=band_ids,
                    features=features,
                    epsilon=1e-12,
                    required_bits=required_bits,
                )
                self.assertEqual(c3.total_slots, required_bits)
                self.assertEqual(c3_np.total_slots, required_bits)
                self.assertEqual(c3.body_slots, c3_np.body_slots)
                self.assertEqual(
                    c3.coefficient_map_sha256,
                    c3_np.coefficient_map_sha256,
                )

    def test_format_v1_rejects_partial_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "format version 1"):
            encode_bitstream(
                self.secret,
                pair_id="v1-partial-rejected",
                method=MethodId.C0_FIXED,
                config=DigitalADConfig(format_version=1),
                payload_fraction=0.50,
            )


if __name__ == "__main__":
    unittest.main()
