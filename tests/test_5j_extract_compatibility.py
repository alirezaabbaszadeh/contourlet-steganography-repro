from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np

from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.pipeline import embed, extract
from ctsteg.digital_ad.types import MethodId


class DirectExtractionCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(20260808)
        cls.cover = rng.integers(0, 256, (512, 512), dtype=np.uint8)
        cls.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cls.config = replace(
            DigitalADConfig(format_version=2),
            lambda_iterations=10,
        )

    def test_extract_without_reference_derives_protected_length(self) -> None:
        fraction = 0.25
        embedding = embed(
            self.cover,
            self.secret,
            pair_id="direct-extract-fallback",
            method=MethodId.C3_A_D,
            config=self.config,
            payload_fraction=fraction,
        )
        extraction = extract(
            embedding.stego,
            embedding.cover,
            pair_id=embedding.pair_id,
            method=embedding.method,
            config=embedding.config,
            expected_payload_fraction=fraction,
        )
        self.assertTrue(extraction.decode.success, extraction.decode.failures)
        self.assertTrue(np.isnan(extraction.raw_ber))
        self.assertEqual(extraction.extracted_bits.size, embedding.encoded.bits.size)
        np.testing.assert_array_equal(
            extraction.decode.recovered_secret,
            self.secret & np.uint8(0xC0),
        )

    def test_extract_with_reference_retains_raw_ber(self) -> None:
        embedding = embed(
            self.cover,
            self.secret,
            pair_id="direct-extract-reference",
            method=MethodId.C0_FIXED,
            config=self.config,
            payload_fraction=0.50,
        )
        extraction = extract(
            embedding.stego,
            embedding.cover,
            pair_id=embedding.pair_id,
            method=embedding.method,
            config=embedding.config,
            expected_bits=embedding.encoded.bits,
            expected_payload_fraction=0.50,
        )
        self.assertTrue(extraction.decode.success, extraction.decode.failures)
        self.assertGreaterEqual(extraction.raw_ber, 0.0)
        self.assertLess(extraction.raw_ber, 0.01)


if __name__ == "__main__":
    unittest.main()
