from __future__ import annotations

import unittest

import numpy as np

from ctsteg.digital_ad.baselines_5j import (
    B2_AC_POSITIONS,
    B2_DELTA_CANDIDATES,
    embed_b1,
    embed_b2,
    extract_b1,
    extract_b2,
    raw_payload_bits,
    reconstruct_raw_payload,
)
from ctsteg.digital_ad.bitplanes import progressive_reference


class Final5JBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        y, x = np.indices((512, 512))
        cls.cover = (
            (3 * x + 5 * y + ((x // 16) ^ (y // 16)) * 19) % 256
        ).astype(np.uint8)
        sy, sx = np.indices((128, 128))
        cls.secret = (
            (11 * sx + 7 * sy + ((sx // 8) ^ (sy // 8)) * 31) % 256
        ).astype(np.uint8)

    def test_progressive_raw_payload_round_trip(self) -> None:
        expected_counts = {
            0.25: 32_768,
            0.50: 65_536,
            0.75: 98_304,
            1.00: 131_072,
        }
        for fraction, expected_count in expected_counts.items():
            with self.subTest(payload_fraction=fraction):
                bits = raw_payload_bits(
                    self.secret,
                    payload_fraction=fraction,
                )
                self.assertEqual(bits.size, expected_count)
                recovered = reconstruct_raw_payload(
                    bits,
                    payload_fraction=fraction,
                )
                np.testing.assert_array_equal(
                    recovered,
                    progressive_reference(
                        self.secret,
                        payload_fraction=fraction,
                    ),
                )

    def test_b1_clean_round_trip_and_target_selection(self) -> None:
        embedding = embed_b1(
            self.cover,
            self.secret,
            payload_fraction=1.0,
            target_psnr_db=45.0,
        )
        extraction = extract_b1(
            embedding.stego,
            reference_bits=embedding.payload_bits,
            payload_fraction=1.0,
            parameters=embedding.parameters,
        )
        self.assertTrue(extraction.complete_recovery)
        self.assertEqual(extraction.bit_errors, 0)
        self.assertIn(embedding.parameters["num_lsb"], {1, 2, 3, 4})
        np.testing.assert_array_equal(
            extraction.reconstructed,
            self.secret,
        )

    def test_b2_capacity_and_clean_round_trip(self) -> None:
        self.assertEqual(len(B2_AC_POSITIONS), 32)
        self.assertEqual(4096 * len(B2_AC_POSITIONS), 131_072)
        embedding = embed_b2(
            self.cover,
            self.secret,
            payload_fraction=1.0,
            target_psnr_db=45.0,
        )
        extraction = extract_b2(
            embedding.stego,
            reference_bits=embedding.payload_bits,
            payload_fraction=1.0,
            parameters=embedding.parameters,
        )
        self.assertTrue(extraction.complete_recovery)
        self.assertEqual(extraction.bit_errors, 0)
        self.assertIn(
            float(embedding.parameters["delta"]),
            B2_DELTA_CANDIDATES,
        )
        np.testing.assert_array_equal(
            extraction.reconstructed,
            self.secret,
        )

    def test_b2_is_deterministic(self) -> None:
        first = embed_b2(
            self.cover,
            self.secret,
            payload_fraction=0.25,
            target_psnr_db=45.0,
        )
        second = embed_b2(
            self.cover,
            self.secret,
            payload_fraction=0.25,
            target_psnr_db=45.0,
        )
        self.assertEqual(first.parameters, second.parameters)
        np.testing.assert_array_equal(first.stego, second.stego)
        np.testing.assert_array_equal(first.payload_bits, second.payload_bits)


if __name__ == "__main__":
    unittest.main()
