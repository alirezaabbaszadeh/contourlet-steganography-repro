from __future__ import annotations

import csv
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ctsteg.digital_ad.runtime_5j import (
    Runner5JError,
    reconstruct_status,
    validate_execution_plan,
    validate_science_ready_report,
)


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/5j/build_execution_plan.py"
STUDY = ROOT / "configs/5j/study_plan_v1.json"
SEEDS = ROOT / "configs/5j/seeds.lock.json"
CONFIG = ROOT / "configs/5j/format_v2_layer_integrity.toml"
SOURCE = ROOT / "src/ctsteg"


class RunnerPreflightTests(unittest.TestCase):
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

    @classmethod
    def _approved_contract(cls, slot: str) -> dict[str, object]:
        return {
            "protocol_id": "FINAL-5J-v1",
            "slot": slot,
            "status": "approved",
            "method_name": f"Fixture {slot}",
            "paper_citation": f"Fixture citation {slot}",
            "source_repository": f"https://example.invalid/{slot.lower()}",
            "source_commit": cls._digest(f"source:{slot}"),
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
            "adapter_fingerprint": cls._digest(f"adapter:{slot}"),
            "approved_by": "fixture-test",
            "approved_at": "2026-08-06T00:00:00Z",
            "limitations": ["Synthetic contract used only by unit tests."],
        }

    def _build_plan(self, temporary: Path) -> dict[str, object]:
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
        registry_path = temporary / "baseline_registry.json"
        registry_path.write_text(
            json.dumps(registry, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output = temporary / "plan.json"
        process = subprocess.run(
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
                str(registry_path),
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
        self.assertEqual(process.returncode, 0, process.stdout)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_full_plan_identity_and_empty_status_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            plan = self._build_plan(temporary)
            index = validate_execution_plan(plan)
            self.assertEqual(index["counts"]["total_embeddings"], 530)
            self.assertEqual(index["counts"]["total_evaluations"], 8420)

            status = reconstruct_status(
                plan,
                cache_dir=temporary / "cache",
            )
            self.assertEqual(status["total_tasks"], 8950)
            self.assertEqual(status["committed_complete"], 0)
            self.assertEqual(status["progress_fraction"], 0.0)
            self.assertEqual(status["state_counts"], {"planned": 8950})
            self.assertEqual(status["kind_counts"]["embedding"], {"planned": 530})
            self.assertEqual(status["kind_counts"]["evaluation"], {"planned": 8420})

    def test_tampered_evaluation_material_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = self._build_plan(Path(directory))
            tampered = deepcopy(plan)
            evaluation = tampered["evaluations"][0]
            original = evaluation["pair_seed"]
            evaluation["pair_seed"] = 1 if original != 1 else 2
            with self.assertRaisesRegex(Runner5JError, "evaluation identity mismatch"):
                validate_execution_plan(tampered)

    def test_science_ready_report_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked = root / "blocked.json"
            blocked.write_text(
                json.dumps(
                    {
                        "protocol_id": "FINAL-5J-v1",
                        "valid_scaffolding": True,
                        "science_ready": False,
                        "blockers": ["B1 is not approved"],
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Runner5JError, "scientific execution is blocked"):
                validate_science_ready_report(blocked)

            ready = root / "ready.json"
            ready.write_text(
                json.dumps(
                    {
                        "protocol_id": "FINAL-5J-v1",
                        "valid_scaffolding": True,
                        "science_ready": True,
                        "blockers": [],
                        "errors": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(validate_science_ready_report(ready)["science_ready"])


if __name__ == "__main__":
    unittest.main()
