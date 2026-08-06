from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ctsteg.provenance import sha256_file, sha256_json
from ctsteg.runtime import ContentStore
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.preprocessing import save_uint8_grayscale
from ctsteg.digital_ad.runtime_tasks_5j import bind_evaluation_task
from ctsteg.digital_ad.runtime_worker_5j import execute_internal_task
from ctsteg.digital_ad.transform_adapter import make_transform_adapter


class InternalWorkerTests(unittest.TestCase):
    @staticmethod
    def _method_fingerprint(method: str, source_fingerprint: str) -> str:
        return sha256_json(
            {
                "protocol_id": "FINAL-5J-v1",
                "payload_format_version": 2,
                "method": method,
                "source_fingerprint": source_fingerprint,
            }
        )

    def _fixture(self, root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        rng = np.random.default_rng(20260809)
        cover = rng.integers(0, 256, (512, 512), dtype=np.uint8)
        secret = rng.integers(0, 256, (128, 128), dtype=np.uint8)
        cover_path = root / "cover.png"
        secret_path = root / "secret.png"
        save_uint8_grayscale(cover_path, cover)
        save_uint8_grayscale(secret_path, secret)

        config_path = root / "config.toml"
        config_path.write_text(
            """[digital_ad]
format_version = 2
cover_size = 512
secret_size = 128
grayscale_policy = "pillow_l"
resize_kernel = "bicubic"
rounding_policy = "half_up"
transform_profile = "haar_orthogonal_control_v1"
levels = 1
directions = 4
angular_concentration = 8.0
gaussian_sigma = 1.0
eligible_level = 0
master_seed = 2026
psnr_target_db = 45.0
psnr_tolerance_db = 0.1
lambda_low = 0.0
lambda_high = 16.0
lambda_iterations = 10
entropy_bins = 64
adaptive_weight_min = 0.75
adaptive_weight_max = 1.25
allocation_epsilon = 1e-12
robust_clip = 3.0
clean_decode_required = true
""",
            encoding="utf-8",
        )
        config = DigitalADConfig.from_toml(config_path)
        transform_fingerprint = make_transform_adapter(config).fingerprint()
        stability_path = root / "stability.json"
        stability_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "calibration_only": True,
                    "image_count": 1,
                    "transform_profile": config.transform_profile,
                    "transform_fingerprint": transform_fingerprint,
                    "stability": {
                        "H0:LL": 1.0,
                        "H0:HORIZONTAL": 1.0,
                        "H0:VERTICAL": 1.0,
                        "H0:DIAGONAL": 1.0,
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        source_fingerprint = hashlib.sha256(b"fixture-source").hexdigest()
        cover_sha = sha256_file(cover_path)
        secret_sha = sha256_file(secret_path)
        embedding = {
            "embedding_id": sha256_json({"fixture": "embedding"}),
            "component": "payload_sweep",
            "pair_id": "fixture-pair",
            "cover_sha256": cover_sha,
            "secret_sha256": secret_sha,
            "method": "C3",
            "method_fingerprint": self._method_fingerprint(
                "C3", source_fingerprint
            ),
            "payload_fraction": 0.5,
            "target_psnr_db": 45.0,
            "payload_format_version": 2,
        }
        evaluation = bind_evaluation_task(
            {
                "evaluation_id": sha256_json({"fixture": "evaluation"}),
                "embedding_id": embedding["embedding_id"],
                "component": embedding["component"],
                "pair_id": embedding["pair_id"],
                "method": embedding["method"],
                "channel_instance_id": "clean",
                "family": "clean",
                "severity": None,
                "realization": 1,
                "pair_seed": None,
            },
            embedding,
        )
        context = {
            "run_id": "5j-fixture-internal-worker",
            "source_fingerprint": source_fingerprint,
            "config_path": str(config_path),
            "base_config_sha256": sha256_file(config_path),
            "stability_path": str(stability_path),
            "stability_sha256": sha256_file(stability_path),
            "pair_inputs": {
                "fixture-pair": {
                    "cover": str(cover_path),
                    "secret": str(secret_path),
                    "cover_sha256": cover_sha,
                    "secret_sha256": secret_sha,
                }
            },
        }
        return embedding, evaluation, context

    def test_embedding_and_clean_evaluation_commit_valid_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            embedding, evaluation, context = self._fixture(root)

            embedded = execute_internal_task(
                embedding,
                kind="embedding",
                context=context,
                cache_dir=cache,
            )
            self.assertEqual(embedded["status"], "completed", embedded)
            self.assertEqual(embedded["scientific_status"], "complete")

            evaluated = execute_internal_task(
                evaluation,
                kind="evaluation",
                context=context,
                cache_dir=cache,
            )
            self.assertEqual(evaluated["status"], "completed", evaluated)
            self.assertEqual(evaluated["scientific_status"], "complete")

            store = ContentStore(cache)
            embedding_check = store.verify(embedding["embedding_id"], deep=True)
            evaluation_check = store.verify(evaluation["evaluation_id"], deep=True)
            self.assertTrue(embedding_check.valid, embedding_check.reason)
            self.assertTrue(evaluation_check.valid, evaluation_check.reason)

            embedding_record = json.loads(
                (embedding_check.path / "embedding.json").read_text(
                    encoding="utf-8"
                )
            )
            evaluation_record = json.loads(
                (evaluation_check.path / "evaluation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(embedding_record["payload_fraction"], 0.5)
            self.assertEqual(evaluation_record["failure_stage"], "S0_COMPLETE")
            self.assertTrue(evaluation_record["recovery"]["complete_recovery"])
            self.assertEqual(
                evaluation_record["recovery"]["payload_correct_fraction"],
                1.0,
            )

            cached = execute_internal_task(
                evaluation,
                kind="evaluation",
                context=context,
                cache_dir=cache,
            )
            self.assertEqual(cached["status"], "cached")

    def test_baseline_dispatch_fails_closed_without_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache"
            embedding, _evaluation, context = self._fixture(root)
            baseline = {
                **embedding,
                "embedding_id": sha256_json({"fixture": "baseline"}),
                "method": "B1",
                "method_fingerprint": sha256_json({"fixture": "B1"}),
            }
            result = execute_internal_task(
                baseline,
                kind="embedding",
                context=context,
                cache_dir=cache,
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("approved external adapter", result["error"])
            self.assertFalse(
                ContentStore(cache).verify(baseline["embedding_id"]).valid
            )


if __name__ == "__main__":
    unittest.main()
