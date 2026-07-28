from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ctsteg.digital_ad.adaptive import band_features
from ctsteg.digital_ad.allocation import (
    build_slot_plan,
    capped_largest_remainder,
)
from ctsteg.digital_ad.attacks import (
    final_attack_suite,
    gaussian,
    jpeg,
    salt_and_pepper,
)
from ctsteg.digital_ad.bitstream import encode_bitstream
from ctsteg.digital_ad.calibration import calibrate_stability
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.embedding import (
    apply_perturbation,
    build_unit_perturbation,
    extract_bits,
)
from ctsteg.digital_ad.experiment import run_digital_experiment
from ctsteg.digital_ad.pipeline import run_clean
from ctsteg.digital_ad.transform_adapter import make_transform_adapter
from ctsteg.digital_ad.transform_audit import audit_transform
from ctsteg.digital_ad.types import MethodId


class DigitalPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        rng = np.random.default_rng(17)
        cls.cover = rng.integers(0, 256, (512, 512), dtype=np.uint8)
        cls.secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cls.config = replace(DigitalADConfig(), lambda_iterations=12)

    def test_transform_audits_are_explicit(self) -> None:
        control = audit_transform(self.config)
        self.assertEqual(control["candidate_coefficients"], 262_144)
        self.assertEqual(control["sampling"], "critically_sampled")
        self.assertEqual(control["filters"]["family"], "separable_2d_haar")
        self.assertNotIn("gaussian_sigma", control["filters"])
        self.assertLessEqual(
            control["perfect_reconstruction"]["max_abs_error"],
            1e-12,
        )
        proxy = audit_transform(
            replace(
                self.config,
                transform_profile="proxy_directional_lp_v1",
                levels=4,
            )
        )
        self.assertEqual(proxy["candidate_coefficients"], 1_048_576)
        self.assertEqual(proxy["sampling"], "redundant")
        self.assertEqual(
            proxy["filters"]["family"],
            "directional_laplacian_proxy",
        )
        self.assertEqual(proxy["filters"]["gaussian_sigma"], 1.0)
        self.assertIn("not the authors", proxy["paper_difference"])

    def test_allocator_is_exact_capped_and_deterministic(self) -> None:
        allocation = capped_largest_remainder(
            [1.0, 2.0, 3.0],
            [2, 10, 10],
            15,
            epsilon=1e-12,
        )
        self.assertEqual(sum(allocation), 15)
        self.assertLessEqual(allocation[0], 2)
        self.assertEqual(
            allocation,
            capped_largest_remainder(
                [1.0, 2.0, 3.0],
                [2, 10, 10],
                15,
                epsilon=1e-12,
            ),
        )

    def test_coefficient_domain_embedding_has_zero_ber(self) -> None:
        adapter = make_transform_adapter(self.config)
        coefficients = adapter.analyze(self.cover)
        bands = adapter.eligible_bands(coefficients)
        descriptors = adapter.descriptors(coefficients, eligible_only=True)
        features = band_features(
            bands,
            [item.band_id for item in descriptors],
            config=self.config,
        )
        encoded = encode_bitstream(
            self.secret,
            pair_id="coefficient-fixture",
            method=MethodId.C3_A_D,
            config=self.config,
        )
        plan = build_slot_plan(
            method=MethodId.C3_A_D,
            bands=bands,
            band_ids=[item.band_id for item in descriptors],
            features=features,
            epsilon=self.config.allocation_epsilon,
        )
        self.assertEqual(plan.total_slots, 222_360)
        unit = build_unit_perturbation(
            coefficients,
            plan,
            encoded.header_bits,
            encoded.body_bits,
            eligible_level=0,
        )
        modified = apply_perturbation(
            coefficients,
            unit,
            eligible_level=0,
            strength=1.0,
        )
        _, _, extracted = extract_bits(
            modified,
            coefficients,
            plan,
            eligible_level=0,
        )
        np.testing.assert_array_equal(extracted, encoded.bits)

    def test_all_controlled_methods_clean_decode_at_psnr_constraint(self) -> None:
        for method in MethodId:
            run = run_clean(
                self.cover,
                self.secret,
                pair_id="clean-fixture",
                method=method,
                config=self.config,
            )
            self.assertTrue(run.success, run.failure_reason)
            self.assertGreaterEqual(
                run.embedding.lambda_search.psnr_db,
                self.config.psnr_target_db,
            )
            # Image clipping/rounding may flip a small number of raw channel
            # bits; the clean end-to-end contract is exact post-ECC recovery.
            self.assertLess(run.extraction.raw_ber, 0.01)
            np.testing.assert_array_equal(
                run.extraction.decode.recovered_secret,
                self.secret,
            )

    def test_directional_proxy_failure_is_explicit_not_relabelled(self) -> None:
        proxy_config = replace(
            self.config,
            transform_profile="proxy_directional_lp_v1",
            levels=4,
            lambda_iterations=8,
        )
        run = run_clean(
            self.cover,
            self.secret,
            pair_id="proxy-failure-fixture",
            method=MethodId.C0_FIXED,
            config=proxy_config,
        )
        self.assertFalse(run.success)
        self.assertGreaterEqual(
            run.embedding.lambda_search.psnr_db,
            proxy_config.psnr_target_db,
        )
        self.assertGreater(run.extraction.raw_ber, 0.1)
        self.assertIsNone(run.extraction.decode.recovered_secret)

    def test_digital_attacks_are_deterministic_uint8(self) -> None:
        functions = (
            lambda: gaussian(self.cover, variance=10.0, seed=2026),
            lambda: salt_and_pepper(self.cover, density=0.03, seed=2026),
            lambda: jpeg(self.cover, quality=70),
        )
        for function in functions:
            first = function()
            second = function()
            self.assertEqual(first.dtype, np.uint8)
            np.testing.assert_array_equal(first, second)

    def test_final_profile_contains_only_lean_medium_conditions(self) -> None:
        attacks = final_attack_suite(2026)
        self.assertEqual(
            [(item.name, item.parameter, item.value) for item in attacks],
            [
                ("jpeg", "quality", 70),
                ("gaussian", "variance", 10.0),
                ("salt_and_pepper", "density", 0.03),
            ],
        )

    def test_calibration_profile_is_transform_bound(self) -> None:
        profile = calibrate_stability([self.cover], config=self.config)
        self.assertEqual(profile.artifact["image_count"], 1)
        self.assertEqual(len(profile.values), 4)
        self.assertTrue(all(value > 0 for value in profile.values.values()))

    def test_final_adaptive_run_requires_calibration_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                ValueError,
                "transform-matched calibration",
            ):
                run_digital_experiment(
                    self.cover,
                    self.secret,
                    pair_id="missing-calibration-fixture",
                    method=MethodId.C3_A_D,
                    config=self.config,
                    output_dir=Path(temporary) / "run",
                    attack_profile="final",
                )

    def test_experiment_writes_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "run"
            result = run_digital_experiment(
                self.cover,
                self.secret,
                pair_id="artifact-fixture",
                method=MethodId.C0_FIXED,
                config=self.config,
                output_dir=output,
                attack_profile="none",
            )
            self.assertTrue(result["success"])
            for filename in (
                "config.json",
                "transform_audit.json",
                "capacity_report.json",
                "bitstream_manifest.json",
                "coefficient_map.json",
                "permutation_hashes.json",
                "metrics.json",
                "metrics.csv",
                "failures.json",
                "provenance.json",
                "runtime.json",
                "stdout.log",
                "stderr.log",
                "run_status.json",
            ):
                self.assertTrue((output / filename).is_file(), filename)
            self.assertTrue((output / "images" / "recovered.png").is_file())


if __name__ == "__main__":
    unittest.main()
