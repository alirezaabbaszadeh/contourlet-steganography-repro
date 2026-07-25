import math
import unittest

import numpy as np

from ctsteg.attacks import (
    central_crop_with_zero_fill,
    gaussian_noise,
    jpeg_compression,
    rotate,
    salt_and_pepper_noise,
)
from ctsteg.metrics import (
    bit_error_rate,
    normalized_correlation,
    psnr,
    ssim_global,
)


class MetricsAndAttacksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.image = np.arange(64 * 64, dtype=np.float64).reshape(64, 64) % 256

    def test_identity_metrics(self) -> None:
        self.assertTrue(math.isinf(psnr(self.image, self.image)))
        self.assertAlmostEqual(ssim_global(self.image, self.image), 1.0)
        self.assertAlmostEqual(normalized_correlation(self.image, self.image), 1.0)
        self.assertEqual(bit_error_rate(self.image, self.image), 0.0)

    def test_attacks_preserve_shape(self) -> None:
        outputs = [
            gaussian_noise(self.image, variance=5, seed=1),
            salt_and_pepper_noise(self.image, density=0.03, seed=1),
            jpeg_compression(self.image, quality=70),
            rotate(self.image, angle_degrees=15),
            central_crop_with_zero_fill(self.image, keep_fraction=0.75),
        ]
        self.assertTrue(all(output.shape == self.image.shape for output in outputs))

    def test_noise_is_deterministic_for_a_seed(self) -> None:
        first = gaussian_noise(self.image, variance=10, seed=42)
        second = gaussian_noise(self.image, variance=10, seed=42)
        np.testing.assert_array_equal(first, second)


if __name__ == "__main__":
    unittest.main()

