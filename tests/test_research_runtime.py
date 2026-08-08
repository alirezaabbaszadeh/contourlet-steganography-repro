from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.preprocessing import load_uint8_grayscale
from ctsteg.digital_ad.research_runtime import (
    ABSOLUTE_MAX_ROWS,
    MANDATORY_EMBEDDINGS,
    MANDATORY_ROWS,
    _parquet_record,
    _write_parquet,
    decide_hard_checks,
    create_download_bundle,
    prepare_research_plan,
    verify_download_bundle,
    write_reports,
)
from ctsteg.digital_ad.runtime_gate import run_runtime_gate
from ctsteg.digital_ad.transform_adapter import make_transform_adapter
from ctsteg.provenance import sha256_array, sha256_file
from ctsteg.runtime import (
    ContentStore,
    RunLock,
    atomic_write_text,
    content_object_id,
    resolve_worker_count,
)
from ctsteg.runtime_gate_contract import validate_runtime_gate_report


class ResearchRuntimeTests(unittest.TestCase):
    def test_parquet_record_has_stable_nullable_types(self) -> None:
        normalized = _parquet_record(
            {
                "attack_value": "",
                "selected_lambda": 1.5,
                "secret_psnr": "inf",
                "decode_success": 1.0,
                "header_valid": False,
                "protected_payload_bits": 222_360,
                "failure_count": 0,
            }
        )
        self.assertIsNone(normalized["attack_value"])
        self.assertEqual(normalized["selected_lambda"], 1.5)
        self.assertEqual(normalized["secret_psnr"], float("inf"))
        self.assertIs(normalized["decode_success"], True)
        self.assertIs(normalized["header_valid"], False)
        self.assertEqual(normalized["protected_payload_bits"], 222_360)
        self.assertEqual(normalized["failure_count"], 0)
        self.assertEqual(normalized["channel_id"], "")

    @unittest.skipUnless(
        importlib.util.find_spec("pyarrow"),
        "PyArrow is an optional research dependency",
    )
    def test_parquet_writer_handles_clean_and_mixed_attack_values(self) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = [
            {
                "channel_id": "clean",
                "attack_value": "",
                "decode_success": 1.0,
                "header_valid": 1.0,
                "payload_crc_valid": 1.0,
                "base_ber": 0.0,
                "selected_lambda": 1.5,
            },
            {
                "channel_id": "jpeg-q70",
                "attack_value": 70,
                "decode_success": False,
                "header_valid": False,
                "payload_crc_valid": False,
                "base_ber": "",
                "selected_lambda": "",
            },
            {
                "channel_id": "gaussian-v10",
                "attack_value": 10.0,
                "decode_success": False,
                "header_valid": False,
                "payload_crc_valid": False,
                "base_ber": "",
                "selected_lambda": "",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "evaluations.parquet"
            result = _write_parquet(rows, destination)
            table = pq.read_table(destination)
        self.assertEqual(result["status"], "written")
        self.assertEqual(
            table.column("attack_value").to_pylist(),
            [None, 70.0, 10.0],
        )
        self.assertEqual(
            table.column("base_ber").to_pylist(),
            [0.0, None, None],
        )
        self.assertEqual(
            table.column("selected_lambda").to_pylist(),
            [1.5, None, None],
        )
        for field in (
            "decode_success",
            "header_valid",
            "payload_crc_valid",
        ):
            self.assertTrue(pa.types.is_boolean(table.schema.field(field).type))

    def test_content_store_commits_atomically_and_quarantines_corruption(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = ContentStore(Path(temporary) / "cache")
            object_id = content_object_id("fixture", {"value": 1})
            first = store.begin_attempt(object_id)
            atomic_write_text(first / "value.txt", "first\n")
            committed = store.commit_attempt(
                object_id,
                first,
                task_material_sha256="a" * 64,
            )
            self.assertTrue(committed.valid)
            (committed.path / "value.txt").write_text(
                "corrupt\n",
                encoding="utf-8",
            )
            self.assertFalse(store.verify(object_id, deep=True).valid)
            second = store.begin_attempt(object_id)
            atomic_write_text(second / "value.txt", "second\n")
            repaired = store.commit_attempt(
                object_id,
                second,
                task_material_sha256="b" * 64,
            )
            self.assertTrue(repaired.valid)
            self.assertEqual(
                (repaired.path / "value.txt").read_text(encoding="utf-8"),
                "second\n",
            )
            quarantined = list((store.root / "quarantine").iterdir())
            self.assertEqual(len(quarantined), 1)
            self.assertTrue(
                (quarantined[0] / "QUARANTINED.json").is_file()
            )
            unexpected = repaired.path / "unexpected.txt"
            unexpected.write_text("not inventoried\n", encoding="utf-8")
            self.assertEqual(
                store.verify(object_id, deep=True).reason,
                "inventory_file_set_mismatch",
            )
            unexpected.unlink()
            self.assertTrue(store.verify(object_id, deep=True).valid)
            run_dir = Path(temporary) / "run"
            run_dir.mkdir()
            atomic_write_text(run_dir / "result.txt", "complete\n")
            with RunLock(run_dir):
                first_bundle = create_download_bundle(
                    run_dir,
                    cache_dir=store.root,
                    object_ids=[object_id],
                )
                second_bundle = create_download_bundle(
                    run_dir,
                    cache_dir=store.root,
                    object_ids=[object_id],
                )
                self.assertNotIn(
                    "experiment/run/run.lock",
                    (run_dir / "checksums.sha256").read_text(
                        encoding="utf-8"
                    ),
                )
            self.assertFalse(first_bundle["reused"])
            self.assertTrue(second_bundle["reused"])
            self.assertEqual(
                verify_download_bundle(first_bundle["archive"])["status"],
                "passed",
            )
            self.assertEqual(
                first_bundle["archive_sha256"],
                second_bundle["archive_sha256"],
            )

    def test_worker_resolution_rejects_insufficient_reserved_memory(
        self,
    ) -> None:
        with patch(
            "ctsteg.runtime.available_memory_bytes",
            return_value=2 * 1024**3,
        ):
            with self.assertRaisesRegex(ValueError, "safe worker bound is zero"):
                resolve_worker_count(
                    0,
                    job_count=4,
                    reserve_cpus=0,
                    reserve_memory_gib=2.0,
                    worker_memory_gib=1.0,
                    hard_cap=4,
                )

    def _locked_fixture(
        self,
        root: Path,
    ) -> tuple[Path, Path, DigitalADConfig]:
        config = replace(DigitalADConfig(), lambda_iterations=2)
        rng = np.random.default_rng(701)
        rows: list[dict[str, str]] = []
        for index in range(4):
            cover_path = root / f"cover-{index}.png"
            secret_path = root / f"secret-{index}.png"
            Image.fromarray(
                rng.integers(0, 256, (512, 512), dtype=np.uint8),
                mode="L",
            ).save(cover_path)
            Image.fromarray(
                rng.integers(0, 256, (128, 128), dtype=np.uint8),
                mode="L",
            ).save(secret_path)
            cover = load_uint8_grayscale(cover_path, size=512)
            secret = load_uint8_grayscale(secret_path, size=128)
            rows.append(
                {
                    "pair_id": f"case-{index}",
                    "cover": cover_path.name,
                    "secret": secret_path.name,
                    "split": "traceability_core",
                    "cover_source_id": f"cover-source-{index}",
                    "secret_source_id": f"secret-source-{index}",
                    "cover_rights": "test-fixture",
                    "secret_rights": "test-fixture",
                    "cover_sha256": sha256_file(cover_path),
                    "secret_sha256": sha256_file(secret_path),
                    "cover_array_sha256": sha256_array(cover),
                    "secret_array_sha256": sha256_array(secret),
                }
            )
        fields = tuple(rows[0])
        lines = [",".join(fields)]
        lines.extend(",".join(row[field] for field in fields) for row in rows)
        manifest = root / "core.csv"
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        adapter = make_transform_adapter(config)
        coefficients = adapter.analyze(
            load_uint8_grayscale(root / "cover-0.png", size=512)
        )
        stability = {
            descriptor.band_id: 1.0
            for descriptor in adapter.descriptors(
                coefficients,
                eligible_only=True,
            )
        }
        stability_path = root / "stability.json"
        stability_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "calibration_only": True,
                    "image_count": 1,
                    "transform_profile": config.transform_profile,
                    "transform_fingerprint": adapter.fingerprint(),
                    "stability": stability,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return manifest, stability_path, config

    def test_plan_is_strictly_64_mandatory_and_88_maximum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest, stability, config = self._locked_fixture(root)
            with self.assertRaisesRegex(ValueError, "engineering control"):
                prepare_research_plan(
                    manifest,
                    config,
                    stability_path=stability,
                )
            plan = prepare_research_plan(
                manifest,
                config,
                stability_path=stability,
                engineering_control=True,
            )
            self.assertEqual(len(plan["embeddings"]), MANDATORY_EMBEDDINGS)
            self.assertEqual(
                len(plan["embeddings"]) + len(plan["core_evaluations"]),
                MANDATORY_ROWS,
            )
            self.assertEqual(
                MANDATORY_ROWS + len(plan["conditional_evaluations"]),
                ABSOLUTE_MAX_ROWS,
            )
            self.assertEqual(
                {
                    task["payload"]["method"]
                    for task in plan["conditional_evaluations"]
                },
                {"C0_FIXED", "C3_A_D"},
            )
            self.assertEqual(
                {
                    family: sum(
                        task["payload"]["channel"]["family"] == family
                        for task in plan["conditional_evaluations"]
                    )
                    for family in ("jpeg", "gaussian", "salt_and_pepper")
                },
                {"jpeg": 8, "gaussian": 8, "salt_and_pepper": 8},
            )
            object_ids = [
                task["object_id"]
                for key in (
                    "embeddings",
                    "core_evaluations",
                    "conditional_evaluations",
                )
                for task in plan[key]
            ]
            self.assertEqual(len(object_ids), len(set(object_ids)))
            first_pair_jpeg = {
                task["payload"]["method"]: task["payload"]["realization_id"]
                for task in plan["core_evaluations"]
                if task["payload"]["pair"]["pair_id"] == "case-0"
                and task["payload"]["channel"]["family"] == "jpeg"
            }
            self.assertEqual(len(set(first_pair_jpeg.values())), 1)
            seeded = root / "seeded.csv"
            lines = manifest.read_text(encoding="utf-8").splitlines()
            seeded.write_text(
                lines[0] + ",seed\n"
                + "\n".join(line + ",2026" for line in lines[1:])
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "seed sweeps"):
                prepare_research_plan(
                    seeded,
                    config,
                    stability_path=stability,
                    engineering_control=True,
                )

    def test_hard_trigger_is_predeclared_and_bounded(self) -> None:
        rows: list[dict[str, object]] = []
        for pair_index in range(4):
            for method in ("C0_FIXED", "C1_A", "C2_D", "C3_A_D"):
                rows.append(
                    {
                        "pair_id": f"case-{pair_index}",
                        "method": method,
                        "channel_id": "clean",
                        "family": "clean",
                        "decode_success": True,
                        "effective_unrecovered_bit_rate": 0.0,
                    }
                )
            for family in ("jpeg", "gaussian", "salt_and_pepper"):
                rows.extend(
                    (
                        {
                            "pair_id": f"case-{pair_index}",
                            "method": "C0_FIXED",
                            "channel_id": family,
                            "family": family,
                            "decode_success": False,
                            "effective_unrecovered_bit_rate": 0.20,
                        },
                        {
                            "pair_id": f"case-{pair_index}",
                            "method": "C3_A_D",
                            "channel_id": family,
                            "family": family,
                            "decode_success": False,
                            "effective_unrecovered_bit_rate": (
                                0.18 if family == "jpeg" else 0.20
                            ),
                        },
                    )
                )
        decisions = decide_hard_checks(rows)
        self.assertEqual(decisions["triggered_families"], ["jpeg"])
        self.assertEqual(
            decisions["families"]["gaussian"]["status"],
            "not_triggered",
        )

    def test_reports_include_factorial_contrasts_and_publication_figures(
        self,
    ) -> None:
        rows: list[dict[str, object]] = []
        for pair_index in range(4):
            for method_index, method in enumerate(
                ("C0_FIXED", "C1_A", "C2_D", "C3_A_D")
            ):
                rows.append(
                    {
                        "pair_id": f"case-{pair_index}",
                        "method": method,
                        "channel_id": "clean",
                        "effective_unrecovered_bit_rate": (
                            0.20 - method_index * 0.02
                        ),
                    }
                )
        with tempfile.TemporaryDirectory() as temporary:
            report = write_reports(
                temporary,
                rows,
                require_parquet=False,
            )
            root = Path(temporary)
            self.assertEqual(report["evaluation_rows"], 16)
            contrasts = json.loads(
                (root / "reports" / "contrasts.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(contrasts), 4)
            figure_names = (
                "mean_eur_by_method.png",
                "mean_eur_by_method.pdf",
                "c0_minus_c3_heatmap.png",
                "c0_minus_c3_heatmap.pdf",
            )
            first_hashes = {}
            for filename in figure_names:
                figure = root / "reports" / "figures" / filename
                self.assertTrue(figure.is_file())
                first_hashes[filename] = sha256_file(figure)
            write_reports(temporary, rows, require_parquet=False)
            self.assertEqual(
                first_hashes,
                {
                    filename: sha256_file(
                        root / "reports" / "figures" / filename
                    )
                    for filename in figure_names
                },
            )

    @unittest.skipUnless(os.name == "posix", "SIGKILL gate requires POSIX")
    def test_real_sigkill_resumes_without_repeating_completed_objects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = run_runtime_gate(
                temporary,
                workers=1,
                jobs=4,
                delay_seconds=0.1,
                timeout_seconds=20,
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["interruption"]["first_exit_code"], -9)
            self.assertGreaterEqual(report["resume"]["cache_hits"], 1)
            self.assertEqual(report["resume"]["final_objects"], 4)
            self.assertEqual(
                report["archive_validation"]["status"],
                "passed",
            )
            validated = validate_runtime_gate_report(
                Path(temporary) / "latest_runtime_gate.json"
            )
            self.assertTrue(all(validated["checks"].values()))
            stale = dict(report)
            stale["runtime_gate_fingerprint"] = "0" * 64
            stale_path = Path(temporary) / "stale-gate.json"
            stale_path.write_text(
                json.dumps(stale) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "runtime_fingerprint"):
                validate_runtime_gate_report(stale_path)


if __name__ == "__main__":
    unittest.main()
