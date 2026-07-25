import unittest

import numpy as np

from ctsteg.transform import DirectionalLaplacianPyramid


class TransformTests(unittest.TestCase):
    def test_analysis_synthesis_reconstructs_input(self) -> None:
        rng = np.random.default_rng(11)
        image = rng.normal(100, 30, size=(64, 64))
        transform = DirectionalLaplacianPyramid(levels=3, directions=4)
        coefficients = transform.analyze(image)
        reconstructed = transform.synthesize(coefficients)
        np.testing.assert_allclose(reconstructed, image, atol=1e-9)

    def test_redundancy_is_explicit(self) -> None:
        transform = DirectionalLaplacianPyramid(levels=3, directions=4)
        self.assertGreater(transform.redundancy_ratio((64, 64)), 1.0)


if __name__ == "__main__":
    unittest.main()

