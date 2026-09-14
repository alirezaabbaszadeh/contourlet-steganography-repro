from __future__ import annotations
from pathlib import Path

from ctsteg.provenance import sha256_json as provenance_sha256_json
import tempfile
import unittest
from unittest.mock import patch

from ctsteg.digital_ad.engineering_dry_run_5j import EXPECTED_COUNTS, METHODS, PLAN_KIND, RUN_ID_PREFIX, build_plan
from ctsteg.digital_ad.runtime_5j import validate_execution_plan

ROOT=Path(__file__).resolve().parents[1]

class EngineeringDryRunTests(unittest.TestCase):
    def pairs(self):
        return [
            {"pair_id":"dry-a","cover_sha256":"a"*64,"secret_sha256":"b"*64},
            {"pair_id":"dry-b","cover_sha256":"c"*64,"secret_sha256":"d"*64},
        ]

    def test_plan_has_two_pairs_all_seven_methods_and_22_channels(self):
        with patch("ctsteg.digital_ad.engineering_dry_run_5j.source_tree_fingerprint",return_value="1"*64), patch(
            "ctsteg.digital_ad.engineering_dry_run_5j._baseline_fingerprints",
            return_value={"B1":"2"*64,"B2":"3"*64},
        ):
            plan=build_plan(self.pairs(),repository_root=ROOT,runtime_bindings_sha256="4"*64)
        self.assertEqual(plan["plan_kind"],PLAN_KIND)
        self.assertTrue(plan["run_id"].startswith(RUN_ID_PREFIX+"-"))
        self.assertEqual(plan["counts"],EXPECTED_COUNTS)
        self.assertEqual({x["method"] for x in plan["embeddings"]},set(METHODS))
        self.assertEqual(len(plan["embeddings"]),14)
        self.assertEqual(len(plan["evaluations"]),308)
        index=validate_execution_plan(plan,expected_counts=EXPECTED_COUNTS,run_id_prefix=RUN_ID_PREFIX,expected_plan_kind=PLAN_KIND)
        self.assertEqual(index["counts"]["total_embeddings"],14)

    def test_internal_method_fingerprints_match_worker_contract(self):
        source = "1" * 64
        with patch("ctsteg.digital_ad.engineering_dry_run_5j.source_tree_fingerprint", return_value=source), patch(
            "ctsteg.digital_ad.engineering_dry_run_5j._baseline_fingerprints",
            return_value={"B1": "2" * 64, "B2": "3" * 64},
        ):
            plan = build_plan(self.pairs(), repository_root=ROOT, runtime_bindings_sha256="4" * 64)
        for method in ("C0", "C1", "C2", "C3_NP", "C3"):
            task = next(item for item in plan["embeddings"] if item["method"] == method)
            expected = provenance_sha256_json({
                "protocol_id": "FINAL-5J-v1",
                "payload_format_version": 2,
                "method": method,
                "source_fingerprint": source,
            })
            self.assertEqual(task["method_fingerprint"], expected)

    def test_scientific_validator_rejects_engineering_plan_kind(self):
        with patch("ctsteg.digital_ad.engineering_dry_run_5j.source_tree_fingerprint",return_value="1"*64), patch(
            "ctsteg.digital_ad.engineering_dry_run_5j._baseline_fingerprints",
            return_value={"B1":"2"*64,"B2":"3"*64},
        ):
            plan=build_plan(self.pairs(),repository_root=ROOT,runtime_bindings_sha256="4"*64)
        with self.assertRaisesRegex(Exception,"plan_kind"):
            validate_execution_plan(plan,expected_counts=EXPECTED_COUNTS)

if __name__=="__main__": unittest.main()
