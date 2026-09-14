from __future__ import annotations

from unittest.mock import patch
import unittest

from ctsteg.digital_ad.analysis_5j import (
    aggregate_pair_overall,
    aggregate_pair_rows,
    build_analysis_payload,
    failure_stage_summary,
    holm_adjust,
    primary_comparisons,
)


class Final5JAnalysisTests(unittest.TestCase):
    @staticmethod
    def _rows() -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        methods = ("C0", "C3_NP", "C3", "B1", "B2")
        for pair_index in range(50):
            pair_id = f"pair-{pair_index:03d}"
            for method in methods:
                for condition, realization in (("clean", 1), ("gaussian:10", 1), ("gaussian:10", 2)):
                    advantage = {
                        "C0": 0.0,
                        "C3_NP": 0.10,
                        "C3": 0.20,
                        "B1": -0.05,
                        "B2": 0.02,
                    }[method]
                    complete = 1.0 if condition == "clean" else max(0.0, 0.4 + advantage)
                    ber = max(0.0, 0.25 - advantage / 2.0)
                    rows.append(
                        {
                            "evaluation_id": f"{pair_id}-{method}-{condition}-{realization}",
                            "embedding_id": f"embed-{pair_id}-{method}",
                            "component": "main",
                            "pair_id": pair_id,
                            "method": method,
                            "channel_instance_id": condition,
                            "channel_family": condition.split(":")[0],
                            "channel_severity": None if condition == "clean" else 10,
                            "condition_key": condition,
                            "realization": realization,
                            "pair_seed": None,
                            "status": "complete" if complete == 1.0 else "scientific_failure",
                            "operational_failure": False,
                            "validity_state": "complete_valid_recovery" if complete == 1.0 else "header_valid_no_valid_layer",
                            "failure_stage": "S0_COMPLETE" if complete == 1.0 else "S3_PAYLOAD_ECC_FAILURE",
                            "header_valid": True,
                            "payload_crc_valid": complete == 1.0,
                            "complete_recovery": complete,
                            "valid_base_only_recovery": None if method.startswith("B") else 0.0,
                            "raw_ber": ber,
                            "payload_correct_fraction": 1.0 - ber,
                            "raw_secret_correct_fraction": 1.0 - ber,
                            "base_correct_fraction": None,
                            "detail_correct_fraction": None,
                            "base_ber": None,
                            "detail_ber": None,
                            "unknown_bit_fraction": 0.0,
                            "reconstruction_psnr": 20.0 + 10.0 * (1.0 - ber),
                            "reconstruction_ssim": 0.5 + 0.4 * (1.0 - ber),
                            "reconstruction_ncc": 0.5 + 0.4 * (1.0 - ber),
                            "cover_stego_psnr": 45.0,
                            "cover_stego_ssim": 0.99,
                            "runtime_seconds": 1.0 + 0.1 * methods.index(method),
                            "peak_memory_bytes": 1000.0,
                        }
                    )
        return rows

    def test_pair_aggregation_and_primary_comparisons(self) -> None:
        rows = self._rows()
        condition = aggregate_pair_rows(rows)
        overall = aggregate_pair_overall(condition)
        self.assertEqual(len(condition), 50 * 5 * 2)
        self.assertEqual(len(overall), 50 * 5)
        comparisons = primary_comparisons(
            overall,
            plan_id="f" * 64,
            bootstrap_repetitions=500,
        )
        self.assertEqual(len(comparisons), 4 * 6)
        c3_c0 = next(
            item
            for item in comparisons
            if item["method_a"] == "C3"
            and item["method_b"] == "C0"
            and item["metric"] == "complete_recovery"
        )
        self.assertEqual(c3_c0["paired_n"], 50)
        self.assertGreater(c3_c0["absolute_difference"]["mean"], 0.0)
        self.assertEqual(c3_c0["direction_count"]["positive"], 50)
        self.assertIsNotNone(c3_c0["holm_adjusted_p"])
        bootstrap = c3_c0["cluster_bootstrap"]
        self.assertLessEqual(bootstrap["ci95_low"], bootstrap["ci95_high"])
        self.assertLessEqual(
            bootstrap["ci95_low"],
            c3_c0["absolute_difference"]["mean"],
        )
        self.assertGreaterEqual(
            bootstrap["ci95_high"],
            c3_c0["absolute_difference"]["mean"],
        )

    def test_holm_is_monotone_and_preserves_missing(self) -> None:
        adjusted = holm_adjust([0.01, 0.02, 0.04, None])
        self.assertEqual(adjusted, [0.03, 0.04, 0.04, None])

    def test_failure_stage_summary_preserves_scientific_failures(self) -> None:
        rows = self._rows()
        summary = failure_stage_summary(rows)
        stages = {item["failure_stage"] for item in summary}
        self.assertIn("S0_COMPLETE", stages)
        self.assertIn("S3_PAYLOAD_ECC_FAILURE", stages)

    def test_full_payload_contains_operational_sensitivity(self) -> None:
        rows = self._rows()
        rows[0]["operational_failure"] = True
        rows[0]["status"] = "operational_failure"
        with patch(
            "ctsteg.digital_ad.analysis_5j.validate_execution_plan",
            return_value={"run_id": "5j-fixture", "plan_id": "a" * 64},
        ):
            payload = build_analysis_payload(
                {},
                rows,
                bootstrap_repetitions=200,
            )
        self.assertEqual(payload["analysis_unit"], "image_pair")
        self.assertEqual(payload["raw_row_count"], len(rows))
        sensitivity = payload["operational_failure_sensitivity"]
        self.assertTrue(sensitivity["pair_overall_rows"])


if __name__ == "__main__":
    unittest.main()
