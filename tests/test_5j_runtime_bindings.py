from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ctsteg.provenance import sha256_file
from ctsteg.digital_ad.runtime_5j import Runner5JError
from ctsteg.digital_ad.runtime_bindings_5j import (
    STAGE0_PROFILE,
    STAGE0_SCHEME,
    TRANSFORM_PROFILE,
    finalize_execution_plan,
    toolbox_inventory,
    toolbox_tree_sha256,
    validate_runtime_bindings,
    verify_finalized_execution_plan,
)


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/5j/build_execution_plan.py"
STUDY = ROOT / "configs/5j/study_plan_v1.json"
SEEDS = ROOT / "configs/5j/seeds.lock.json"
CONFIG = ROOT / "configs/5j/format_v2_layer_integrity.toml"
SOURCE = ROOT / "src/ctsteg"


class RuntimeBindingTests(unittest.TestCase):
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

    def _write_runtime_bindings(self, temporary: Path) -> tuple[Path, Path]:
        runtime = temporary / "octave-cli-fixture"
        runtime.write_bytes(b"fixture-octave-runtime-v1\n")
        runtime.chmod(0o755)

        toolbox = temporary / "contourlet-toolbox"
        toolbox.mkdir()
        required = (
            "pdfbdec.m",
            "pdfbrec.m",
            "pfilters.m",
            "wfb2dec.m",
            "wfb2rec.m",
            "dfbdec_l.m",
            "dfbrec_l.m",
            "resampc.m",
        )
        for name in required:
            (toolbox / name).write_text(
                f"% synthetic {name}\n",
                encoding="utf-8",
            )

        stage0 = temporary / "stage0.json"
        stage0.write_text(
            json.dumps(
                {
                    "schema": 2,
                    "runtime_verified": True,
                    "passed": True,
                    "profile": STAGE0_PROFILE,
                    "scheme": STAGE0_SCHEME,
                    "exploratory": False,
                    "author_equivalence_claimed": False,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        stability = temporary / "stability.json"
        stability.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "calibration_only": True,
                    "transform_profile": TRANSFORM_PROFILE,
                    "transform_fingerprint": self._digest("fixture-transform"),
                    "stability": {"V:P4:LH": 1.0},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        binding = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "status": "frozen",
            "transform_profile": TRANSFORM_PROFILE,
            "runtime_executable": {
                "path": str(runtime),
                "sha256": sha256_file(runtime),
            },
            "toolbox": {
                "path": str(toolbox),
                "tree_sha256": toolbox_tree_sha256(toolbox_inventory(toolbox)),
            },
            "stage0_evidence": {
                "path": str(stage0),
                "sha256": sha256_file(stage0),
            },
            "stability_profile": {
                "path": str(stability),
                "sha256": sha256_file(stability),
            },
            "science_ready": True,
            "approved_by": "fixture-test",
            "approved_at": "2026-08-06T00:00:00Z",
            "blockers": [],
        }
        binding_path = temporary / "runtime-bindings.json"
        binding_path.write_text(
            json.dumps(binding, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return binding_path, runtime

    def test_finalization_readdresses_every_task_and_is_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            unbound = self._build_plan(temporary)
            binding_path, _runtime = self._write_runtime_bindings(temporary)
            finalized, report = finalize_execution_plan(
                unbound,
                runtime_bindings_path=binding_path,
            )
            self.assertEqual(finalized["base_plan_id"], unbound["plan_id"])
            self.assertNotEqual(finalized["plan_id"], unbound["plan_id"])
            self.assertNotEqual(finalized["run_id"], unbound["run_id"])
            self.assertEqual(finalized["counts"], unbound["counts"])
            self.assertEqual(len(finalized["embeddings"]), 530)
            self.assertEqual(len(finalized["evaluations"]), 8420)
            self.assertEqual(
                len({item["embedding_id"] for item in finalized["embeddings"]}),
                530,
            )
            self.assertEqual(
                len({item["evaluation_id"] for item in finalized["evaluations"]}),
                8420,
            )
            self.assertTrue(
                all(
                    before["embedding_id"] != after["embedding_id"]
                    for before, after in zip(
                        unbound["embeddings"], finalized["embeddings"], strict=True
                    )
                )
            )
            self.assertEqual(
                finalized["created_from"]["runtime_bindings_sha256"],
                report["binding_sha256"],
            )
            verified = verify_finalized_execution_plan(
                finalized,
                runtime_bindings_path=binding_path,
            )
            self.assertEqual(verified["binding_sha256"], report["binding_sha256"])

    def test_tampered_bound_runtime_revokes_finalized_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            unbound = self._build_plan(temporary)
            binding_path, runtime = self._write_runtime_bindings(temporary)
            finalized, _report = finalize_execution_plan(
                unbound,
                runtime_bindings_path=binding_path,
            )
            runtime.write_bytes(b"tampered-runtime\n")
            with self.assertRaisesRegex(Runner5JError, "runtime executable SHA-256 mismatch"):
                verify_finalized_execution_plan(
                    finalized,
                    runtime_bindings_path=binding_path,
                )

    def test_pending_binding_is_rejected_before_file_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pending.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "protocol_id": "FINAL-5J-v1",
                        "status": "pending",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(Runner5JError, "not frozen"):
                validate_runtime_bindings(path)


if __name__ == "__main__":
    unittest.main()
