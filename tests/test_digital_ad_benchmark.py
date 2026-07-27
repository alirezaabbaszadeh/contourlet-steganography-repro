from __future__ import annotations

from dataclasses import replace
import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from ctsteg.digital_ad.benchmark import run_digital_benchmark
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.statistics import analyze_factorial


class DigitalBenchmarkTests(unittest.TestCase):
    def test_manifest_benchmark_and_factorial_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rng = np.random.default_rng(91)
            Image.fromarray(
                rng.integers(0, 256, (512, 512), dtype=np.uint8),
                mode="L",
            ).save(root / "cover.png")
            Image.fromarray(
                rng.integers(0, 256, (128, 128), dtype=np.uint8),
                mode="L",
            ).save(root / "secret.png")
            manifest = root / "pairs.csv"
            manifest.write_text(
                "pair_id,cover,secret,split,seed\n"
                "fixture,cover.png,secret.png,pilot,2026\n",
                encoding="utf-8",
            )
            benchmark_dir = root / "benchmark"
            result = run_digital_benchmark(
                manifest,
                replace(DigitalADConfig(), lambda_iterations=8),
                benchmark_dir,
                attack_profile="none",
            )
            self.assertEqual(result["failed_units"], 0)
            self.assertEqual(result["successful_units"], 4)
            self.assertTrue((benchmark_dir / "results_long.csv").is_file())
            analysis = analyze_factorial(
                benchmark_dir / "results_long.csv",
                root / "factorial",
                bootstrap_resamples=64,
                permutation_resamples=64,
            )
            self.assertGreater(len(analysis["comparisons"]), 0)
            contrasts = {
                item["contrast"] for item in analysis["comparisons"]
            }
            self.assertIn("A_x_D", contrasts)
            self.assertIn("C3_minus_C0", contrasts)

    def test_factorial_aggregates_repeated_seeds_within_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = root / "results.csv"
            fields = (
                "method",
                "method_version",
                "pair_id",
                "split",
                "seed",
                "scope",
                "attack",
                "parameter",
                "attack_value",
                "metric",
                "direction",
                "value",
            )
            with results.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for pair_index, pair_id in enumerate(("a", "b")):
                    for seed in (2026, 2027):
                        for method_index, method in enumerate(
                            ("C0_FIXED", "C1_A", "C2_D", "C3_A_D")
                        ):
                            writer.writerow(
                                {
                                    "method": method,
                                    "method_version": "digital-ad-v1",
                                    "pair_id": pair_id,
                                    "split": "test",
                                    "seed": seed,
                                    "scope": "attacked_decode",
                                    "attack": "jpeg",
                                    "parameter": "quality",
                                    "attack_value": 70,
                                    "metric": "effective_unrecovered_bit_rate",
                                    "direction": "lower",
                                    "value": (
                                        0.5
                                        - 0.02 * method_index
                                        + 0.001 * pair_index
                                        + 0.0001 * (seed - 2026)
                                    ),
                                }
                            )
            analysis = analyze_factorial(
                results,
                root / "analysis",
                bootstrap_resamples=64,
                permutation_resamples=64,
            )
            self.assertTrue(analysis["comparisons"])
            self.assertTrue(
                all(item["n_pairs"] == 2 for item in analysis["comparisons"])
            )


if __name__ == "__main__":
    unittest.main()
