from __future__ import annotations

import copy
import unittest

from ctsteg.digital_ad.worker_trial_5j import (
    WorkerTrialError,
    _percentile,
    validate_selection,
)
from ctsteg.digital_ad.worker_tuning_5j import canonical_sha256


METHODS = ("C0", "C1", "C2", "C3_NP", "C3")
FAMILIES = ("clean", "jpeg", "gaussian", "salt_pepper")


def fixture() -> tuple[dict[str, object], dict[str, object]]:
    embeddings: dict[str, dict[str, object]] = {}
    evaluations: dict[str, dict[str, object]] = {}
    embedding_ids: list[str] = []
    evaluation_ids: list[str] = []
    for index in range(32):
        method = METHODS[index % len(METHODS)]
        embedding_id = f"{index + 1:064x}"
        embedding = {
            "embedding_id": embedding_id,
            "component": "payload_sweep" if index < 16 else "main",
            "pair_id": f"pair-{index:03d}",
            "method": method,
            "cover_sha256": f"{1000 + index:064x}",
            "secret_sha256": f"{2000 + index:064x}",
            "method_fingerprint": f"{3000 + index:064x}",
            "payload_fraction": 0.5 if index < 16 else 1.0,
            "target_psnr_db": 45.0,
            "payload_format_version": 2,
        }
        embeddings[embedding_id] = embedding
        embedding_ids.append(embedding_id)
        for family_index, family in enumerate(FAMILIES):
            evaluation_id = f"{10000 + index * 4 + family_index:064x}"
            evaluation = {
                "evaluation_id": evaluation_id,
                "embedding_id": embedding_id,
                "component": embedding["component"],
                "pair_id": embedding["pair_id"],
                "method": method,
                "channel_instance_id": f"{family}-{index}",
                "family": family,
                "severity": {
                    "clean": None,
                    "jpeg": 70,
                    "gaussian": 10,
                    "salt_pepper": 0.03,
                }[family],
                "realization": 1,
                "pair_seed": None if family in {"clean", "jpeg"} else index + 1,
            }
            evaluations[evaluation_id] = evaluation
            evaluation_ids.append(evaluation_id)
    material = {
        "schema_version": 1,
        "protocol_id": "FINAL-5J-v1",
        "status": "frozen_before_trial",
        "plan_id": "a" * 64,
        "run_id": "5j-fixture",
        "selection_policy": "fixture",
        "embedding_ids": embedding_ids,
        "evaluation_ids": evaluation_ids,
    }
    selection = {**material, "selection_sha256": canonical_sha256(material)}
    index = {
        "embedding_by_id": embeddings,
        "evaluation_by_id": evaluations,
    }
    return selection, index


class WorkerTrialTests(unittest.TestCase):
    def test_valid_selection_binds_32_embeddings_and_128_evaluations(self) -> None:
        selection, index = fixture()
        result = validate_selection(selection, index=index)
        self.assertEqual(len(result["embeddings"]), 32)
        self.assertEqual(len(result["evaluations"]), 128)
        self.assertEqual(
            {item["method"] for item in result["embeddings"]},
            set(METHODS),
        )
        self.assertEqual(
            {item["family"] for item in result["evaluations"]},
            set(FAMILIES),
        )

    def test_selection_hash_tampering_is_rejected(self) -> None:
        selection, index = fixture()
        selection["evaluation_ids"] = selection["evaluation_ids"][:-1]
        with self.assertRaisesRegex(WorkerTrialError, "SHA-256"):
            validate_selection(selection, index=index)

    def test_unselected_embedding_dependency_is_rejected(self) -> None:
        selection, index = fixture()
        damaged = copy.deepcopy(selection)
        evaluation_id = damaged["evaluation_ids"][0]
        index["evaluation_by_id"][evaluation_id]["embedding_id"] = "f" * 64
        material = dict(damaged)
        material.pop("selection_sha256")
        damaged["selection_sha256"] = canonical_sha256(material)
        with self.assertRaisesRegex(WorkerTrialError, "unselected embedding"):
            validate_selection(damaged, index=index)

    def test_baseline_embedding_is_rejected(self) -> None:
        selection, index = fixture()
        first = selection["embedding_ids"][0]
        index["embedding_by_id"][first]["method"] = "B1"
        with self.assertRaisesRegex(WorkerTrialError, "B1/B2"):
            validate_selection(selection, index=index)

    def test_percentile_uses_nearest_rank(self) -> None:
        self.assertEqual(_percentile([1.0, 2.0, 3.0, 4.0], 0.95), 4.0)
        self.assertEqual(_percentile([], 0.95), 0.0)


if __name__ == "__main__":
    unittest.main()
