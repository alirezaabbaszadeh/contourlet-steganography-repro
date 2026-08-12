from __future__ import annotations

from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from ctsteg.runtime import ContentStore, DurableTask, atomic_write_json

from ctsteg.digital_ad.runtime_dispatch_5j import (
    _dispatch_worker,
    build_embedding_tasks,
    build_evaluation_tasks,
    build_worker_context,
    _verify_embedding_acceptance,
)


class Final5JDispatchTests(unittest.TestCase):
    def test_spawn_adapter_routes_internal_and_baseline_methods(self) -> None:
        context = {"run_id": "5j-fixture"}
        with patch(
            "ctsteg.digital_ad.runtime_dispatch_5j.execute_internal_task",
            return_value={"status": "completed", "worker": "internal"},
        ) as internal:
            result = _dispatch_worker(
                {
                    "payload": {
                        "kind": "embedding",
                        "task": {"method": "C3", "embedding_id": "a" * 64},
                        "context": context,
                    }
                },
                "/tmp/cache",
            )
            self.assertEqual(result["worker"], "internal")
            internal.assert_called_once()

        with patch(
            "ctsteg.digital_ad.runtime_dispatch_5j.execute_baseline_task",
            return_value={"status": "completed", "worker": "baseline"},
        ) as baseline:
            result = _dispatch_worker(
                {
                    "payload": {
                        "kind": "evaluation",
                        "task": {"method": "B2", "evaluation_id": "b" * 64},
                        "context": context,
                    }
                },
                "/tmp/cache",
            )
            self.assertEqual(result["worker"], "baseline")
            baseline.assert_called_once()

    def test_worker_context_has_final_only_backup_policy(self) -> None:
        plan = {
            "created_from": {
                "source_fingerprint": "1" * 64,
                "config_sha256": "2" * 64,
            },
            "embeddings": [
                {"method": "B1", "method_fingerprint": "3" * 64},
                {"method": "B2", "method_fingerprint": "4" * 64},
            ],
        }
        index = {
            "run_id": "5j-fixture-run",
            "embedding_by_id": {},
            "evaluation_by_id": {},
        }
        runtime = {
            "stability_profile": "/tmp/stability.json",
            "stability_profile_sha256": "5" * 64,
        }
        with patch(
            "ctsteg.digital_ad.runtime_dispatch_5j.validate_execution_plan",
            return_value=index,
        ):
            context = build_worker_context(
                plan,
                runtime_report=runtime,
                pair_inputs={"pair-1": {"cover": "c", "secret": "s"}},
                config_path="/tmp/config.toml",
            )
        self.assertEqual(
            context["backup_policy"],
            "final_only_after_run_completion",
        )
        self.assertEqual(
            context["baseline_method_fingerprints"],
            {"B1": "3" * 64, "B2": "4" * 64},
        )

    def test_typed_baseline_scientific_embedding_failure_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache"
            object_id = "a" * 64
            store = ContentStore(cache)
            attempt = store.begin_attempt(object_id)
            atomic_write_json(
                attempt / "embedding.json",
                {
                    "status": "scientific_failure",
                    "method": "B2",
                    "failure": {
                        "kind": "clean_embedding_infeasible",
                        "reason": "no clean-valid embedding candidate exists",
                        "prerequisite_unreachable": True,
                        "missingness": "not_evaluated",
                    },
                },
            )
            store.commit_attempt(
                object_id,
                attempt,
                task_material_sha256="b" * 64,
            )
            task = DurableTask(
                object_id=object_id,
                kind="embedding",
                label="main:pair:B2",
                payload={"kind": "embedding", "task": {"method": "B2"}},
            )
            counts = _verify_embedding_acceptance([task], cache_dir=cache)
            self.assertEqual(counts, {"complete": 0, "scientific_failure": 1, "invalid": 0})

    def test_plan_tasks_preserve_two_stage_dependency(self) -> None:
        embedding = {
            "embedding_id": "a" * 64,
            "component": "main",
            "pair_id": "pair-1",
            "method": "B1",
            "cover_sha256": "c" * 64,
            "secret_sha256": "d" * 64,
            "method_fingerprint": "e" * 64,
            "payload_fraction": 1.0,
            "target_psnr_db": 45.0,
            "payload_format_version": 2,
        }
        evaluation = {
            "evaluation_id": "b" * 64,
            "embedding_id": "a" * 64,
            "component": "main",
            "pair_id": "pair-1",
            "method": "B1",
            "channel_instance_id": "clean",
            "family": "clean",
            "severity": None,
            "realization": 1,
            "pair_seed": None,
        }
        index = {
            "run_id": "5j-fixture-run",
            "embedding_by_id": {embedding["embedding_id"]: embedding},
            "evaluation_by_id": {evaluation["evaluation_id"]: evaluation},
        }
        context = {"run_id": "5j-fixture-run"}
        with patch(
            "ctsteg.digital_ad.runtime_dispatch_5j.validate_execution_plan",
            return_value=index,
        ):
            embeddings = build_embedding_tasks({}, context=context)
            evaluations = build_evaluation_tasks({}, context=context)
        self.assertEqual(len(embeddings), 1)
        self.assertEqual(len(evaluations), 1)
        self.assertEqual(embeddings[0].kind, "embedding")
        self.assertEqual(evaluations[0].kind, "evaluation")
        self.assertEqual(
            evaluations[0].payload["task"]["embedding_id"],
            embeddings[0].object_id,
        )


if __name__ == "__main__":
    unittest.main()
