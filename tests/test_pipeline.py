from dataclasses import replace
import unittest

import numpy as np

from ctsteg.config import ExperimentConfig
from ctsteg.experiment import synthetic_pair
from ctsteg.metrics import bit_error_rate
from ctsteg.pipeline import embed_secret, extract_secret


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cover, self.secret = synthetic_pair(size=64, seed=9)
        self.base = replace(
            ExperimentConfig(),
            image_size=64,
            levels=3,
            band_policy="all_details",
            embed_lowpass=True,
            quantize_stego=False,
        )

    def test_float_all_coefficient_path_is_reversible(self) -> None:
        embedded = embed_secret(self.cover, self.secret, self.base)
        extracted = extract_secret(embedded.stego, self.cover, self.base)
        self.assertEqual(bit_error_rate(self.secret, extracted.recovered_secret), 0.0)
        np.testing.assert_allclose(
            extracted.recovered_secret, self.secret, atol=1e-6
        )

    def test_literal_high_frequency_only_does_not_recover_full_secret(self) -> None:
        literal = replace(
            self.base,
            band_policy="finest",
            embed_lowpass=False,
        )
        embedded = embed_secret(self.cover, self.secret, literal)
        extracted = extract_secret(embedded.stego, self.cover, literal)
        self.assertGreater(
            bit_error_rate(self.secret, extracted.recovered_secret), 0.01
        )

    def test_quantization_is_an_explicit_loss_source(self) -> None:
        quantized = replace(self.base, quantize_stego=True)
        embedded = embed_secret(self.cover, self.secret, quantized)
        extracted = extract_secret(embedded.stego, self.cover, quantized)
        self.assertGreater(
            bit_error_rate(self.secret, extracted.recovered_secret), 0.0
        )


if __name__ == "__main__":
    unittest.main()

