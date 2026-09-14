from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ctsteg.provenance import sha256_json as provenance_sha256_json


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/5j/build_execution_plan.py"
STUDY = ROOT / "configs/5j/study_plan_v1.json"
SEEDS = ROOT / "configs/5j/seeds.lock.json"
CONFIG = ROOT / "configs/5j/format_v2_layer_integrity.toml"
SOURCE = ROOT / "src/ctsteg"


class ExecutionPlanTests(unittest.TestCase):
    @staticmethod
    def _digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    @classmethod
    def _write_manifest(cls, path: Path, pair_ids: list[str]) -> None:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["pair_id", "cover_sha256", "secret_sha256"],
            )
            writer.writeheader()
            for pair_id in pair_ids:
                writer.writerow(
                    {
                        "pair_id": pair_id,
                        "cover_sha256": cls._digest(f"cover:{pair_id}"),
                        "secret_sha256": cls._digest(f"secret:{pair_id}"),
                    }
                )

    @staticmethod
    def _approved_contract(slot: str) -> dict[str, object]:
        return {
            "protocol_id": "FINAL-5J-v1",
            "slot": slot,
            "status": "approved",
            "method_name": f"Fixture {slot}",
            "paper_citation": f"Fixture citation {slot}",
            "source_repository": f"https://example.invalid/{slot.lower()}",
            "source_commit": hashlib.sha256(slot.encode()).hexdigest(),
            "license": "MIT-fixture",
            "license_review": "compatible",
            "implementation_language": ["Python"],
            "extraction_mode": "blind",
            "input_contract": {"fixture": True},
            "payload_contract": {"fixture": True},
            "distortion_contract": {"fixture": True},
            "attack_contract": {"fixture": True},
            "metric_contract": {"fixture": True},
            "adaptations": [],
            "clean_round_trip": {
                "status": "passed",
                "evidence_object_id": f"fixture-clean-{slot.lower()}",
            },
            "adapter_fingerprint": hashlib.sha256(
                f"adapter:{slot}".encode()
            ).hexdigest(),
            "approved_by": "fixture-test",
            "approved_at": "2026-08-06T00:00:00Z",
            "limitations": ["Synthetic contract used only by unit tests."],
        }

    def _run_builder(self, temporary: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BUILDER),
                "--repository-root",
                str(temporary),
                "--study-plan",
                str(STUDY),
                "--seed-lock",
                str(SEEDS),
                "--baseline-registry",
                str(temporary / "baseline_registry.json"),
                "--config",
                str(CONFIG),
                "--source-root",
                str(SOURCE),
                "--main-manifest",
                str(temporary / "main.csv"),
                "--sweep-manifest",
                str(temporary / "sweep.csv"),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_expansion_is_exact_unique_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            pairs = [f"pair-{index:03d}" for index in range(50)]
            self._write_manifest(temporary / "main.csv", pairs)
            self._write_manifest(temporary / "sweep.csv", pairs[:10])

            contracts = temporary / "contracts"
            contracts.mkdir()
            for slot in ("B1", "B2"):
                (contracts / f"{slot}.json").write_text(
                    json.dumps(self._approved_contract(slot), indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
            registry = {
                "protocol_id": "FINAL-5J-v1",
                "registry_version": 1,
                "status": "frozen",
                "slots": [
                    {
                        "slot": slot,
                        "role": f"fixture-{slot.lower()}",
                        "contract_path": f"contracts/{slot}.json",
                        "status": "approved",
                        "approved": True,
                    }
                    for slot in ("B1", "B2")
                ],
                "required_common_metrics": ["complete_recovery"],
                "main_run_authorized": True,
                "blockers": [],
            }
            (temporary / "baseline_registry.json").write_text(
                json.dumps(registry, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            first_path = temporary / "plan-first.json"
            second_path = temporary / "plan-second.json"
            first = self._run_builder(temporary, first_path)
            second = self._run_builder(temporary, second_path)
            self.assertEqual(first.returncode, 0, first.stdout)
            self.assertEqual(second.returncode, 0, second.stdout)

            plan = json.loads(first_path.read_text(encoding="utf-8"))
            repeated = json.loads(second_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["plan_id"], repeated["plan_id"])
            self.assertEqual(plan["run_id"], repeated["run_id"])
            self.assertEqual(plan["counts"]["total_embeddings"], 530)
            self.assertEqual(plan["counts"]["total_evaluations"], 8420)
            self.assertEqual(len(plan["embeddings"]), 530)
            self.assertEqual(len(plan["evaluations"]), 8420)
            self.assertEqual(
                len({item["embedding_id"] for item in plan["embeddings"]}),
                530,
            )
            self.assertEqual(
                len({item["evaluation_id"] for item in plan["evaluations"]}),
                8420,
            )

            main = [item for item in plan["embeddings"] if item["component"] == "main"]
            payload = [
                item
                for item in plan["embeddings"]
                if item["component"] == "payload_sweep"
            ]
            psnr = [
                item
                for item in plan["embeddings"]
                if item["component"] == "psnr_sweep"
            ]
            self.assertEqual(len(main), 350)
            self.assertEqual(len(payload), 90)
            self.assertEqual(len(psnr), 90)
            self.assertEqual({item["payload_fraction"] for item in payload}, {0.25, 0.5, 0.75})
            self.assertEqual({item["target_psnr_db"] for item in psnr}, {40.0, 42.5, 47.5})

            gaussian = [
                item
                for item in plan["evaluations"]
                if item["component"] == "main"
                and item["pair_id"] == "pair-000"
                and item["channel_instance_id"] == "gaussian_v5_r1"
            ]
            self.assertEqual(len(gaussian), 7)
            self.assertEqual(len({item["pair_seed"] for item in gaussian}), 1)
            self.assertIsInstance(gaussian[0]["pair_seed"], int)

            c3 = next(
                item
                for item in main
                if item["pair_id"] == "pair-000" and item["method"] == "C3"
            )
            c3_np = next(
                item
                for item in main
                if item["pair_id"] == "pair-000" and item["method"] == "C3_NP"
            )
            self.assertNotEqual(c3["embedding_id"], c3_np["embedding_id"])
            self.assertNotEqual(c3["method_fingerprint"], c3_np["method_fingerprint"])
            for task in (c3, c3_np):
                expected_fingerprint = provenance_sha256_json(
                    {
                        "protocol_id": "FINAL-5J-v1",
                        "payload_format_version": 2,
                        "method": task["method"],
                        "source_fingerprint": plan["created_from"]["source_fingerprint"],
                    }
                )
                self.assertEqual(task["method_fingerprint"], expected_fingerprint)


if __name__ == "__main__":
    unittest.main()
