import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ctsteg.benchmark import RESULT_FIELDS
from ctsteg.statistics import (
    compare_benchmarks,
    holm_adjust,
    paired_bootstrap_mean_ci,
    paired_sign_flip_test,
    rank_biserial_paired,
)


def _write_results(
    path: Path,
    *,
    method: str,
    psnr_values: list[float],
    ber_values: list[float],
) -> None:
    rows = []
    for index, (psnr, ber) in enumerate(zip(psnr_values, ber_values, strict=True)):
        common = {
            "method": method,
            "method_version": "1",
            "pair_id": f"pair-{index}",
            "split": "test",
            "seed": 2026,
            "scope": "recovery",
            "attack": "",
            "parameter": "",
            "attack_value": "",
        }
        rows.append(
            {
                **common,
                "metric": "psnr_db",
                "direction": "higher",
                "value": psnr,
            }
        )
        rows.append(
            {
                **common,
                "metric": "ber",
                "direction": "lower",
                "value": ber,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


class StatisticsTests(unittest.TestCase):
    def test_core_paired_statistics_are_directionally_consistent(self) -> None:
        differences = np.ones(4, dtype=np.float64)
        low, high = paired_bootstrap_mean_ci(
            differences,
            resamples=128,
            rng=np.random.default_rng(4),
        )
        self.assertAlmostEqual(low, 1.0)
        self.assertAlmostEqual(high, 1.0)
        p_value, mode = paired_sign_flip_test(differences, resamples=128)
        self.assertEqual(mode, "exact")
        self.assertAlmostEqual(p_value, 0.125)
        self.assertAlmostEqual(rank_biserial_paired(differences), 1.0)
        monte_carlo_p, monte_carlo_mode = paired_sign_flip_test(
            np.linspace(-1.0, 2.0, 17),
            resamples=128,
            rng=np.random.default_rng(4),
        )
        self.assertEqual(monte_carlo_mode, "monte_carlo")
        self.assertGreaterEqual(monte_carlo_p, 0.0)
        self.assertLessEqual(monte_carlo_p, 1.0)

    def test_holm_adjustment(self) -> None:
        adjusted = holm_adjust([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06])

    def test_repeated_seeds_are_aggregated_at_image_pair_level(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.csv"
            proposed = root / "proposed.csv"
            units = [
                ("pair-a", 1, 0.0, 1.0),
                ("pair-a", 2, 0.0, 1.0),
                ("pair-a", 3, 0.0, 1.0),
                ("pair-b", 1, 0.0, 3.0),
            ]
            for path, method, value_index in (
                (baseline, "baseline", 2),
                (proposed, "candidate", 3),
            ):
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
                    writer.writeheader()
                    for pair_id, seed, baseline_value, proposed_value in units:
                        values = (pair_id, seed, baseline_value, proposed_value)
                        writer.writerow(
                            {
                                "method": method,
                                "method_version": "1",
                                "pair_id": pair_id,
                                "split": "test",
                                "seed": seed,
                                "scope": "recovery",
                                "attack": "",
                                "parameter": "",
                                "attack_value": "",
                                "metric": "psnr_db",
                                "direction": "higher",
                                "value": values[value_index],
                            }
                        )

            result = compare_benchmarks(
                baseline,
                proposed,
                root / "comparison",
                bootstrap_resamples=128,
                permutation_resamples=128,
            )

            comparison = result["comparisons"][0]
            self.assertEqual(comparison["n_total"], 2)
            self.assertEqual(comparison["n_seed_units_total"], 4)
            self.assertAlmostEqual(comparison["mean_improvement"], 2.0)

    def test_comparison_writes_machine_and_human_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline" / "results_long.csv"
            proposed = root / "proposed" / "results_long.csv"
            _write_results(
                baseline,
                method="paper_baseline",
                psnr_values=[30.0, 31.0, 32.0, 33.0],
                ber_values=[0.20, 0.15, 0.10, 0.05],
            )
            _write_results(
                proposed,
                method="candidate",
                psnr_values=[31.0, 32.0, 33.0, 34.0],
                ber_values=[0.10, 0.10, 0.05, 0.04],
            )
            output = root / "comparison"

            result = compare_benchmarks(
                baseline,
                proposed,
                output,
                bootstrap_resamples=256,
                permutation_resamples=256,
                seed=7,
            )

            self.assertEqual(len(result["comparisons"]), 2)
            by_metric = {
                row["metric"]: row for row in result["comparisons"]
            }
            self.assertAlmostEqual(by_metric["psnr_db"]["mean_improvement"], 1.0)
            self.assertGreater(by_metric["ber"]["mean_improvement"], 0.0)
            for row in result["comparisons"]:
                self.assertGreaterEqual(
                    row["p_sign_flip_holm"],
                    row["p_sign_flip"],
                )
            self.assertTrue((output / "comparison.csv").is_file())
            self.assertTrue((output / "comparison.json").is_file())
            self.assertTrue((output / "comparison.md").is_file())
            with (output / "comparison.json").open(encoding="utf-8") as stream:
                saved = json.load(stream)
            self.assertEqual(saved["alignment"]["common_group_count"], 2)
            self.assertEqual(len(saved["analysis_id"]), 16)
            self.assertEqual(
                len(saved["analysis_provenance"]["statistics_sha256"]),
                64,
            )

    def test_misaligned_pairs_are_rejected_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline.csv"
            proposed = root / "proposed.csv"
            _write_results(
                baseline,
                method="baseline",
                psnr_values=[30.0, 31.0],
                ber_values=[0.2, 0.1],
            )
            _write_results(
                proposed,
                method="candidate",
                psnr_values=[31.0],
                ber_values=[0.1],
            )
            with self.assertRaisesRegex(ValueError, "do not align"):
                compare_benchmarks(
                    baseline,
                    proposed,
                    root / "comparison",
                    bootstrap_resamples=32,
                    permutation_resamples=32,
                )

    def test_provenance_mismatch_is_rejected_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline" / "results_long.csv"
            proposed = root / "proposed" / "results_long.csv"
            _write_results(
                baseline,
                method="baseline",
                psnr_values=[30.0, 31.0],
                ber_values=[0.2, 0.1],
            )
            _write_results(
                proposed,
                method="candidate",
                psnr_values=[31.0, 32.0],
                ber_values=[0.1, 0.05],
            )
            common = {
                "manifest": {
                    "sha256": "manifest",
                    "input_files_sha256": "inputs",
                },
                "options": {"include_attacks": False},
                "evaluation_code": {"metrics_sha256": "same"},
            }
            (baseline.parent / "provenance.json").write_text(
                json.dumps({**common, "config_sha256": "baseline-config"}),
                encoding="utf-8",
            )
            (proposed.parent / "provenance.json").write_text(
                json.dumps({**common, "config_sha256": "proposed-config"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "config_sha256"):
                compare_benchmarks(
                    baseline,
                    proposed,
                    root / "comparison",
                    bootstrap_resamples=32,
                    permutation_resamples=32,
                )


if __name__ == "__main__":
    unittest.main()
