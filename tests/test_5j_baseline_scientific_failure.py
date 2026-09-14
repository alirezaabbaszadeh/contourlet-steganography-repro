from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ctsteg.digital_ad.baselines_5j import Baseline5JError
from ctsteg.digital_ad.runtime_baseline_worker_5j import execute_baseline_task
from ctsteg.provenance import sha256_file, sha256_json
from ctsteg.runtime import ContentStore


class BaselineScientificFailureTests(unittest.TestCase):
    def _fixture(self, root: Path):
        cover = np.arange(512 * 512, dtype=np.uint32).reshape(512, 512).astype(np.uint8)
        secret = np.arange(128 * 128, dtype=np.uint32).reshape(128, 128).astype(np.uint8)
        cover_path = root / "cover.png"
        secret_path = root / "secret.png"
        Image.fromarray(cover).save(cover_path)
        Image.fromarray(secret).save(secret_path)
        pair_id = "pair-scientific-infeasible"
        fingerprint = sha256_json({"baseline": "B2-fixture"})
        embedding = {
            "embedding_id": sha256_json({"fixture": "embedding-scientific-failure"}),
            "component": "main",
            "pair_id": pair_id,
            "method": "B2",
            "cover_sha256": sha256_file(cover_path),
            "secret_sha256": sha256_file(secret_path),
            "method_fingerprint": fingerprint,
            "payload_fraction": 1.0,
            "target_psnr_db": 45.0,
            "payload_format_version": 2,
        }
        evaluation = {
            **embedding,
            "evaluation_id": sha256_json({"fixture": "evaluation-not-evaluated"}),
            "channel_instance_id": "clean",
            "family": "clean",
            "severity": None,
            "realization": 1,
            "pair_seed": None,
        }
        context = {
            "run_id": "5j-fixture-scientific-failure",
            "source_fingerprint": "1" * 64,
            "base_config_sha256": "2" * 64,
            "baseline_method_fingerprints": {"B1": "3" * 64, "B2": fingerprint},
            "pair_inputs": {pair_id: {"cover": str(cover_path), "secret": str(secret_path)}},
        }
        return embedding, evaluation, context

    def test_clean_infeasible_embedding_and_dependents_are_scientific_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            embedding, evaluation, context = self._fixture(root)
            with patch(
                "ctsteg.digital_ad.runtime_baseline_worker_5j.embed_baseline",
                side_effect=Baseline5JError("no clean-valid embedding candidate exists"),
            ):
                result = execute_baseline_task(
                    embedding, kind="embedding", context=context, cache_dir=cache
                )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["scientific_status"], "scientific_failure")
            check = ContentStore(cache).verify(embedding["embedding_id"], deep=True)
            self.assertTrue(check.valid, check.reason)
            record = json.loads((check.path / "embedding.json").read_text())
            self.assertEqual(record["status"], "scientific_failure")
            self.assertEqual(record["failure"]["kind"], "clean_embedding_infeasible")
            self.assertEqual(record["failure"]["missingness"], "not_evaluated")
            self.assertIsNone(record["stego_sha256"])
            self.assertEqual(record["protected_payload_bits"], 131072)

            evaluated = execute_baseline_task(
                evaluation, kind="evaluation", context=context, cache_dir=cache
            )
            self.assertEqual(evaluated["status"], "completed")
            self.assertEqual(evaluated["scientific_status"], "scientific_failure")
            evaluation_check = ContentStore(cache).verify(
                evaluation["evaluation_id"], deep=True
            )
            self.assertTrue(evaluation_check.valid, evaluation_check.reason)
            evaluation_record = json.loads(
                (evaluation_check.path / "evaluation.json").read_text()
            )
            self.assertEqual(evaluation_record["status"], "scientific_failure")
            self.assertEqual(
                evaluation_record["failure_stage"],
                "S5_EXTRACTION_TRANSFORM_FAILURE",
            )
            self.assertEqual(evaluation_record["validity_state"], "extraction_failure")
            self.assertFalse(evaluation_record["recovery"]["complete_recovery"])
            self.assertIsNone(evaluation_record["recovery"]["raw_ber"])
            self.assertTrue(
                evaluation_record["failures"][0]["reason"].startswith(
                    "not_evaluated: prerequisite"
                )
            )
            self.assertIsNone(evaluation_record["provenance"]["attacked_sha256"])

    def test_other_baseline_errors_remain_operational_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            embedding, _evaluation, context = self._fixture(root)
            with patch(
                "ctsteg.digital_ad.runtime_baseline_worker_5j.embed_baseline",
                side_effect=Baseline5JError("B2 payload exceeds fixed DCT capacity"),
            ):
                result = execute_baseline_task(
                    embedding, kind="embedding", context=context, cache_dir=root / "cache"
                )
            self.assertEqual(result["status"], "failed")
            self.assertIn("capacity", result["error"])
