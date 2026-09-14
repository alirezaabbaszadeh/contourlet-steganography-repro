from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest

from ctsteg.digital_ad.analysis_5j import build_analysis_payload


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "scripts/5j/build_tables.py"
FIGURES = ROOT / "scripts/5j/build_figures.py"


class Final5JReportingTests(unittest.TestCase):
    @staticmethod
    def _rows() -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        methods = ("C0", "C1", "C2", "C3_NP", "C3", "B1", "B2")
        for pair_index in range(5):
            for method_index, method in enumerate(methods):
                for condition in ("clean", "jpeg:70"):
                    complete = 1.0 if condition == "clean" else min(
                        1.0, 0.2 + method_index * 0.08
                    )
                    ber = 0.0 if condition == "clean" else max(
                        0.0, 0.3 - method_index * 0.025
                    )
                    rows.append(
                        {
                            "evaluation_id": f"e-{pair_index}-{method}-{condition}",
                            "embedding_id": f"m-{pair_index}-{method}",
                            "component": "main",
                            "pair_id": f"pair-{pair_index}",
                            "method": method,
                            "channel_instance_id": condition,
                            "channel_family": condition.split(":")[0],
                            "channel_severity": None if condition == "clean" else 70,
                            "condition_key": condition,
                            "realization": 1,
                            "pair_seed": None,
                            "status": "complete" if complete == 1.0 else "scientific_failure",
                            "operational_failure": False,
                            "validity_state": "complete_valid_recovery" if complete == 1.0 else "header_valid_no_valid_layer",
                            "failure_stage": "S0_COMPLETE" if complete == 1.0 else "S3_PAYLOAD_ECC_FAILURE",
                            "header_valid": True,
                            "payload_crc_valid": complete == 1.0,
                            "complete_recovery": complete,
                            "valid_base_only_recovery": None if method.startswith("B") else 0.1,
                            "raw_ber": ber,
                            "payload_correct_fraction": 1.0 - ber,
                            "raw_secret_correct_fraction": 1.0 - ber,
                            "base_correct_fraction": None,
                            "detail_correct_fraction": None,
                            "base_ber": None,
                            "detail_ber": None,
                            "unknown_bit_fraction": 0.0,
                            "reconstruction_psnr": 25.0 + method_index,
                            "reconstruction_ssim": 0.7 + method_index * 0.02,
                            "reconstruction_ncc": 0.7 + method_index * 0.02,
                            "cover_stego_psnr": 45.0,
                            "cover_stego_ssim": 0.99,
                            "runtime_seconds": 1.0 + method_index * 0.2,
                            "peak_memory_bytes": 1000.0 + method_index,
                        }
                    )
        return rows

    def test_tables_and_figures_are_generated_from_analysis(self) -> None:
        with patch(
            "ctsteg.digital_ad.analysis_5j.validate_execution_plan",
            return_value={"run_id": "5j-fixture", "plan_id": "f" * 64},
        ):
            analysis = build_analysis_payload(
                {},
                self._rows(),
                bootstrap_repetitions=200,
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            analysis_path = root / "analysis.json"
            analysis_path.write_text(
                json.dumps(analysis, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tables = root / "tables"
            figures = root / "figures"
            table_run = subprocess.run(
                [
                    sys.executable,
                    str(TABLES),
                    "--analysis",
                    str(analysis_path),
                    "--output-dir",
                    str(tables),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(table_run.returncode, 0, table_run.stdout)
            figure_run = subprocess.run(
                [
                    sys.executable,
                    str(FIGURES),
                    "--analysis",
                    str(analysis_path),
                    "--output-dir",
                    str(figures),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(figure_run.returncode, 0, figure_run.stdout)
            self.assertTrue((tables / "table_method_summary.tex").is_file())
            self.assertTrue((tables / "table_primary_comparisons.md").is_file())
            self.assertTrue((figures / "figure_complete_recovery.png").is_file())
            self.assertTrue((figures / "figure_failure_stages.pdf").is_file())
            latex = (tables / "table_method_summary.tex").read_text(encoding="utf-8")
            self.assertIn("\\begin{table}", latex)
            self.assertIn("\\\\", latex)


if __name__ == "__main__":
    unittest.main()
