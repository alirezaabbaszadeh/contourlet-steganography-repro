from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from ctsteg.digital_ad.engineering_worker_plan_5j import (
    METHODS,
    PAYLOAD_FRACTIONS,
    PURPOSE,
    build_engineering_plan,
    load_engineering_pairs,
)
from ctsteg.digital_ad.worker_trial_5j import validate_selection


class EngineeringWorkerPlanTests(unittest.TestCase):
    @staticmethod
    def _digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    def test_plan_has_exact_internal_performance_matrix(self) -> None:
        pairs = [
            {
                "pair_id": f"dry-{index}",
                "cover_sha256": self._digest(f"cover-{index}"),
                "secret_sha256": self._digest(f"secret-{index}"),
            }
            for index in range(2)
        ]
        plan, index, selection = build_engineering_plan(
            pairs,
            source_fingerprint=self._digest("source"),
            config_sha256=self._digest("config"),
            runtime_bindings_sha256=self._digest("runtime"),
        )
        self.assertEqual(plan["plan_kind"], PURPOSE)
        self.assertEqual(plan["counts"]["embeddings"], 40)
        self.assertEqual(plan["counts"]["evaluations"], 160)
        self.assertEqual(len(index["embedding_by_id"]), 40)
        self.assertEqual(len(index["evaluation_by_id"]), 160)
        self.assertTrue(plan["run_id"].startswith("5j-perf-"))
        self.assertEqual(
            {item["method"] for item in plan["embeddings"]},
            set(METHODS),
        )
        self.assertEqual(
            {float(item["payload_fraction"]) for item in plan["embeddings"]},
            set(PAYLOAD_FRACTIONS),
        )
        self.assertEqual(
            {item["family"] for item in plan["evaluations"]},
            {"clean", "jpeg", "gaussian", "salt_pepper"},
        )
        validated = validate_selection(selection, index=index)
        self.assertEqual(len(validated["embeddings"]), 40)
        self.assertEqual(len(validated["evaluations"]), 160)

    def test_engineering_ids_change_with_runtime_binding(self) -> None:
        pairs = [
            {
                "pair_id": f"dry-{index}",
                "cover_sha256": self._digest(f"cover-{index}"),
                "secret_sha256": self._digest(f"secret-{index}"),
            }
            for index in range(2)
        ]
        first, _first_index, _first_selection = build_engineering_plan(
            pairs,
            source_fingerprint=self._digest("source"),
            config_sha256=self._digest("config"),
            runtime_bindings_sha256=self._digest("runtime-a"),
        )
        second, _second_index, _second_selection = build_engineering_plan(
            pairs,
            source_fingerprint=self._digest("source"),
            config_sha256=self._digest("config"),
            runtime_bindings_sha256=self._digest("runtime-b"),
        )
        self.assertNotEqual(first["plan_id"], second["plan_id"])
        self.assertTrue(
            all(
                left["embedding_id"] != right["embedding_id"]
                for left, right in zip(
                    first["embeddings"], second["embeddings"], strict=True
                )
            )
        )

    def test_tracked_dry_run_manifest_resolves_inside_repository(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = root / "data-manifests/5j/dry_run.csv"
        pairs, inputs = load_engineering_pairs(manifest, repository_root=root)
        self.assertEqual(len(pairs), 2)
        for pair_id, paths in inputs.items():
            with self.subTest(pair_id=pair_id):
                for role in ("cover", "secret"):
                    resolved = Path(paths[role]).resolve()
                    self.assertTrue(resolved.is_relative_to(root))
                    self.assertTrue(resolved.is_file())

    def test_manifest_requires_two_hash_verified_dry_run_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for index in range(2):
                cover = root / f"cover-{index}.png"
                secret = root / f"secret-{index}.png"
                cover.write_bytes(f"cover-{index}".encode("ascii"))
                secret.write_bytes(f"secret-{index}".encode("ascii"))
                rows.append(
                    {
                        "pair_id": f"dry-{index}",
                        "split": "dry_run",
                        "cover": cover.name,
                        "secret": secret.name,
                        "cover_sha256": hashlib.sha256(cover.read_bytes()).hexdigest(),
                        "secret_sha256": hashlib.sha256(secret.read_bytes()).hexdigest(),
                    }
                )
            manifest = root / "dry-run.csv"
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "pair_id",
                        "split",
                        "cover",
                        "secret",
                        "cover_sha256",
                        "secret_sha256",
                    ],
                )
                writer.writeheader()
                writer.writerows(rows)
            pairs, inputs = load_engineering_pairs(
                manifest,
                repository_root=root,
            )
            self.assertEqual(len(pairs), 2)
            self.assertEqual(set(inputs), {"dry-0", "dry-1"})


if __name__ == "__main__":
    unittest.main()
