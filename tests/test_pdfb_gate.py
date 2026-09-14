from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ctsteg.cli import main
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.pdfb_gate import (
    PdfbEvidenceError,
    PdfbGateSpec,
    build_matlab_expression,
    deterministic_input_sha256,
    run_pdfb_stage0,
    validate_pdfb_evidence,
    write_pdfb_execution_plan,
    write_pdfb_validation,
)


def _valid_evidence(spec: PdfbGateSpec) -> dict[str, object]:
    eligible = [
        {
            "band_id": f"P4:D{index}",
            "shape": [256, 256],
            "coefficient_count": 65_536,
        }
        for index in range(4)
    ]
    probes = [
        {
            "band_id": f"P4:D{band_index}",
            "row": int(fraction * 255),
            "column": int(fraction * 255),
            "fraction": fraction,
            "self_gain": 0.999,
            "maximum_cross_talk": 0.001,
            "off_target_l2_ratio": 0.005,
        }
        for band_index in range(4)
        for fraction in spec.probe_fractions
    ]
    total_coefficients = 4_096 + 262_144
    return {
        "schema": 1,
        "runtime_verified": True,
        "profile": spec.profile,
        "spec_sha256": spec.spec_sha256,
        "assumption_status": spec.assumption_status,
        "author_equivalence_claimed": False,
        "parameters": {
            "pfilter": spec.pfilter,
            "dfilter": spec.dfilter,
            "nlevels": list(spec.nlevels),
            "eligible_pyramid_level_from_coarse": (
                spec.eligible_pyramid_level_from_coarse
            ),
            "cover_size": spec.cover_size,
            "probe_delta": spec.probe_delta,
            "probe_fractions": list(spec.probe_fractions),
        },
        "input": {
            "generator": "ctsteg_deterministic_audit_v1",
            "shape": [512, 512],
            "uint8_row_major_sha256": deterministic_input_sha256(),
        },
        "runtime": {
            "matlab_version": "fixture-only",
            "matlab_release": "fixture-only",
            "computer": "fixture-only",
        },
        "toolbox": {
            "declared_release": spec.toolbox_release,
            "root": "/fixture",
            "pdfbdec_path": "/fixture/pdfbdec.m",
            "pdfbdec_sha256": "1" * 64,
            "pdfbrec_path": "/fixture/pdfbrec.m",
            "pdfbrec_sha256": "2" * 64,
        },
        "bands": [
            {
                "band_id": "P0:LOWPASS",
                "shape": [64, 64],
                "coefficient_count": 4_096,
            },
            *deepcopy(eligible),
        ],
        "eligible_bands": deepcopy(eligible),
        "total_coefficients": total_coefficients,
        "redundancy_ratio": total_coefficients / (512**2),
        "capacity": {
            "required_slots": spec.required_slots,
            "candidate_coefficients": 262_144,
            "capacity_sufficient": True,
            "unused_candidate_slots": 39_784,
            "candidate_utilization": spec.required_slots / 262_144,
        },
        "perfect_reconstruction": {
            "max_abs_error": 1e-12,
            "mse": 1e-26,
            "rmse": 1e-13,
        },
        "independent_writability": {
            "probe_count": 12,
            "minimum_self_gain": 0.999,
            "maximum_cross_talk": 0.001,
            "maximum_off_target_l2_ratio": 0.005,
            "probes": probes,
        },
    }


class PdfbGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = PdfbGateSpec().validate()

    def test_locked_spec_and_input_are_deterministic(self) -> None:
        self.assertEqual(self.spec.expected_directional_bands, 4)
        self.assertEqual(len(self.spec.spec_sha256), 64)
        self.assertEqual(
            deterministic_input_sha256(),
            deterministic_input_sha256(),
        )

    def test_valid_runtime_evidence_reaches_human_review_only(self) -> None:
        result = validate_pdfb_evidence(
            _valid_evidence(self.spec),
            self.spec,
        )
        self.assertTrue(result["gate_passed"])
        boundary = result["claim_boundary"]
        self.assertEqual(boundary["status"], "eligible_for_human_review")
        self.assertFalse(boundary["author_equivalence_allowed"])
        self.assertFalse(boundary["direct_article_superiority_allowed"])
        self.assertFalse(boundary["embedding_profile_enabled"])
        self.assertTrue(boundary["human_review_required"])

    def test_capacity_failure_is_preserved_as_negative_evidence(self) -> None:
        evidence = _valid_evidence(self.spec)
        evidence["eligible_bands"] = [
            {
                "band_id": "P4:D0",
                "shape": [256, 256],
                "coefficient_count": 65_536,
            }
        ]
        evidence["capacity"]["candidate_coefficients"] = 65_536
        evidence["capacity"]["capacity_sufficient"] = False
        evidence["capacity"]["unused_candidate_slots"] = (
            65_536 - self.spec.required_slots
        )
        evidence["capacity"]["candidate_utilization"] = (
            self.spec.required_slots / 65_536
        )
        evidence["independent_writability"]["probes"] = [
            probe
            for probe in evidence["independent_writability"]["probes"]
            if probe["band_id"] == "P4:D0"
        ]
        evidence["independent_writability"]["probe_count"] = 3
        result = validate_pdfb_evidence(evidence, self.spec)
        self.assertFalse(result["gate_passed"])
        self.assertEqual(
            result["claim_boundary"]["status"],
            "blocked_by_transform_gate",
        )
        by_name = {item["name"]: item for item in result["conditions"]}
        self.assertFalse(by_name["candidate_capacity"]["passed"])
        self.assertFalse(by_name["eligible_direction_count"]["passed"])

    def test_parameter_and_toolbox_identity_mismatches_are_rejected(self) -> None:
        evidence = _valid_evidence(self.spec)
        evidence["parameters"]["pfilter"] = "made-up"
        with self.assertRaisesRegex(PdfbEvidenceError, "parameters.pfilter"):
            validate_pdfb_evidence(evidence, self.spec)

        evidence = _valid_evidence(self.spec)
        evidence["toolbox"]["pdfbdec_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(PdfbEvidenceError, "lowercase SHA-256"):
            validate_pdfb_evidence(evidence, self.spec)

    def test_probe_aggregates_are_recomputed_from_raw_records(self) -> None:
        evidence = _valid_evidence(self.spec)
        evidence["independent_writability"]["maximum_cross_talk"] = 0.0
        with self.assertRaisesRegex(
            PdfbEvidenceError,
            "maximum_cross_talk does not match",
        ):
            validate_pdfb_evidence(evidence, self.spec)

    def test_eligible_band_inventory_must_match_full_inventory(self) -> None:
        evidence = _valid_evidence(self.spec)
        evidence["eligible_bands"][0]["shape"] = [128, 512]
        with self.assertRaisesRegex(
            PdfbEvidenceError,
            "eligible band P4:D0 disagrees with bands",
        ):
            validate_pdfb_evidence(evidence, self.spec)

    def test_probe_coordinates_are_derived_from_locked_fractions(self) -> None:
        evidence = _valid_evidence(self.spec)
        evidence["independent_writability"]["probes"][0]["row"] += 1
        with self.assertRaisesRegex(
            PdfbEvidenceError,
            "location does not match its fraction",
        ):
            validate_pdfb_evidence(evidence, self.spec)

    def test_runtime_and_toolbox_identity_fields_are_required(self) -> None:
        evidence = _valid_evidence(self.spec)
        del evidence["runtime"]["matlab_release"]
        with self.assertRaisesRegex(PdfbEvidenceError, "matlab_release"):
            validate_pdfb_evidence(evidence, self.spec)

        evidence = _valid_evidence(self.spec)
        del evidence["toolbox"]["root"]
        with self.assertRaisesRegex(PdfbEvidenceError, "toolbox.root"):
            validate_pdfb_evidence(evidence, self.spec)

    def test_plan_is_data_not_a_shell_command(self) -> None:
        expression = build_matlab_expression(
            self.spec,
            toolbox_path="/tmp/toolbox with space",
            output_path="/tmp/result's evidence.json",
            matlab_scripts_path="/tmp/matlab",
        )
        self.assertIn("audit_pdfb_stage0(", expression)
        self.assertIn("result''s evidence.json", expression)
        self.assertIn("'NLevels',[2 2 2 2]", expression)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "plan.json"
            plan = write_pdfb_execution_plan(
                output,
                self.spec,
                toolbox_path=root / "toolbox",
                raw_evidence_path=root / "raw.json",
                matlab_scripts_path=root / "matlab",
            )
            self.assertEqual(plan["command"][0], "matlab")
            self.assertEqual(plan["command"][1], "-batch")
            self.assertTrue(output.is_file())

    def test_validation_writes_both_pass_and_fail_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "raw.json"
            raw.write_text(
                json.dumps(_valid_evidence(self.spec)),
                encoding="utf-8",
            )
            output = root / "validated.json"
            result = write_pdfb_validation(output, raw, self.spec)
            self.assertTrue(result["gate_passed"])
            self.assertEqual(len(result["evidence_sha256"]), 64)

    def test_runtime_fails_closed_when_matlab_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            toolbox = root / "toolbox"
            toolbox.mkdir()
            scripts = root / "matlab"
            scripts.mkdir()
            (scripts / "audit_pdfb_stage0.m").write_text(
                "% fixture\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                FileNotFoundError,
                "MATLAB executable not found",
            ):
                run_pdfb_stage0(
                    self.spec,
                    toolbox_path=toolbox,
                    output_dir=root / "output",
                    matlab_scripts_path=scripts,
                    matlab_executable="ctsteg-definitely-missing-matlab",
                )

    def test_cli_routes_timeout_only_to_runtime_audit(self) -> None:
        with (
            patch.object(
                PdfbGateSpec,
                "from_toml",
                return_value=self.spec,
            ),
            patch(
                "ctsteg.digital_ad.pdfb_gate.run_pdfb_stage0",
                return_value={"gate_passed": True},
            ) as runtime,
            redirect_stdout(io.StringIO()),
        ):
            exit_code = main(
                [
                    "pdfb-audit",
                    "--spec",
                    "fixture.toml",
                    "--toolbox-path",
                    "/fixture/toolbox",
                    "--output-dir",
                    "/fixture/output",
                    "--matlab-scripts",
                    "/fixture/matlab",
                    "--timeout-seconds",
                    "17.5",
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertEqual(runtime.call_args.kwargs["timeout_seconds"], 17.5)

    def test_pdfb_is_not_silently_enabled_as_a_python_adapter(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicit external adapter"):
            replace(
                DigitalADConfig(),
                transform_profile="matlab_pdfb_explicit_v1",
            ).validate()


if __name__ == "__main__":
    unittest.main()
