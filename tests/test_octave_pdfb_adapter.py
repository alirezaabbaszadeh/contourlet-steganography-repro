from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.io import loadmat, savemat

from ctsteg.digital_ad.config import DigitalADConfig, OCTAVE_PDFB_PROFILE
from ctsteg.digital_ad.research_runtime import (
    ABSOLUTE_MAX_ROWS,
    MANDATORY_EMBEDDINGS,
    MANDATORY_ROWS,
    MAX_CONDITIONAL_ROWS,
    _ensure_transform_boundary,
    execute_research_plan,
)
from ctsteg.digital_ad.transform_adapter import (
    OctavePdfbTransformAdapter,
    _OCTAVE_BRIDGE_SOURCE,
)
from ctsteg.digital_ad.transform_audit import _filter_inventory
from ctsteg.transform import PyramidCoefficients


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory_tree_sha256(inventory: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for item in inventory:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


class OctavePdfbAdapterTests(unittest.TestCase):
    def _fixture(
        self,
        root: Path,
    ) -> tuple[DigitalADConfig, dict[str, str], str]:
        toolbox = root / "toolbox"
        toolbox.mkdir()
        function_names = (
            "pdfbdec",
            "pdfbrec",
            "pfilters",
            "wfb2dec",
            "wfb2rec",
            "dfbdec_l",
            "dfbrec_l",
        )
        for name in function_names:
            (toolbox / f"{name}.m").write_text(
                f"% {name} fixture\n",
                encoding="utf-8",
            )
        (toolbox / "resampc.mex").write_bytes(b"octave fixture")
        inventory = [
            {
                "path": path.relative_to(toolbox).as_posix(),
                "sha256": _sha256(path),
            }
            for path in sorted(
                path.resolve()
                for path in toolbox.rglob("*")
                if path.is_file()
            )
        ]
        inventory_tree = _inventory_tree_sha256(inventory)
        band_records = [
            ("V:P4:LH", (256, 256)),
            ("V:P4:HL", (256, 256)),
            ("V:P4:HH", (256, 256)),
            ("V:P3:LH", (128, 128)),
            ("V:P3:HL", (128, 128)),
            ("V:P3:HH", (128, 128)),
        ]
        probes = [
            {
                "band_id": band_id,
                "row": int(fraction * (shape[0] - 1)),
                "column": int(fraction * (shape[1] - 1)),
                "fraction": fraction,
                "self_gain": 1.0,
                "maximum_cross_talk": 0.0,
                "off_target_l2_ratio": 0.0,
            }
            for band_id, shape in band_records
            for fraction in (0.25, 0.5, 0.75)
        ]
        boundary_probes = [
            {
                "band_id": band_id,
                "position": position,
                "row": 0 if position == "first" else shape[0] - 1,
                "column": 0 if position == "first" else shape[1] - 1,
                "self_gain": 1.0,
                "maximum_cross_talk": 0.0,
                "off_target_l2_ratio": 0.0,
            }
            for band_id, shape in band_records
            for position in ("first", "last")
        ]
        runtime_path = str(Path(sys.executable).resolve())
        function_inventory = [
            {
                "name": name,
                "path": str((toolbox / f"{name}.m").resolve()),
                "sha256": _sha256(toolbox / f"{name}.m"),
            }
            for name in function_names
        ]
        gate = {
            name: True
            for name in (
                "reconstruction_passed",
                "capacity_passed",
                "rank_passed",
                "probe_coverage_passed",
                "self_gain_passed",
                "cross_talk_passed",
                "off_target_passed",
                "boundary_probes_passed",
                "valid_range_leakage_passed",
                "dense_sign_trial_passed",
                "full_candidate_dense_trial_passed",
                "passed",
            )
        }
        evidence = root / "stage0.json"
        evidence.write_text(
            json.dumps(
                {
                    "schema": 2,
                    "runtime_verified": True,
                    "profile": "octave_pdfb_range_coordinates_v2",
                    "scheme": (
                        "pdfb_9_7_pkva_multiscale_range_coordinates_p3_p4_v2"
                    ),
                    "exploratory": False,
                    "passed": True,
                    "author_equivalence_claimed": False,
                    "source": {
                        "script_sha256": (
                            "5e6569a12407d321cd6ad2e12f43cda63dc6e58b64501e"
                            "7fe2f3de28497efc4c"
                        )
                    },
                    "parameters": {
                        "pfilter": "9-7",
                        "dfilter": "pkva",
                        "nlevels": [2, 2, 2, 2],
                        "eligible_pyramid_levels_from_coarse": [3, 4],
                        "cover_size": 512,
                        "required_slots": 222_360,
                        "probe_delta": 1,
                        "probe_fractions": [0.25, 0.5, 0.75],
                        "coordinate_order": [
                            band_id for band_id, _shape in band_records
                        ],
                    },
                    "runtime": {
                        "engine": "gnu_octave",
                        "version": "fixture",
                        "platform": "x86_64-pc-linux-gnu",
                        "executable": runtime_path,
                    },
                    "toolbox": {
                        "root": str(toolbox.resolve()),
                        "function_inventory": function_inventory,
                        "inventory": inventory,
                        "inventory_policy": "all_regular_files_recursive_v1",
                        "inventory_count": len(inventory),
                        "tree_sha256": inventory_tree,
                        "resampc_mex": {
                            "name": "resampc.mex",
                            "path": str((toolbox / "resampc.mex").resolve()),
                            "sha256": _sha256(toolbox / "resampc.mex"),
                        },
                        "resampc_resolved_path": str(
                            (toolbox / "resampc.mex").resolve()
                        ),
                    },
                    "toolbox_inventory": inventory,
                    "toolbox_inventory_count": len(inventory),
                    "toolbox_tree_sha256": inventory_tree,
                    "virtual_bands": [
                        {
                            "band_id": band_id,
                            "shape": list(shape),
                            "coordinate_count": shape[0] * shape[1],
                        }
                        for band_id, shape in band_records
                    ],
                    "rank_certificate": {
                        "p4_raw_directional_values": 262_144,
                        "p4_independent_coordinates": 196_608,
                        "p3_raw_directional_values": 65_536,
                        "p3_independent_coordinates": 49_152,
                        "p3_p4_independent_coordinates": 245_760,
                    },
                    "capacity": {
                        "required_slots": 222_360,
                        "candidate_coefficients": 245_760,
                        "candidate_coordinates": 245_760,
                        "coordinate_basis_rank": 245_760,
                        "capacity_sufficient": True,
                        "unused_candidate_slots": 23_400,
                        "candidate_utilization": 222_360 / 245_760,
                    },
                    "perfect_reconstruction": {
                        "max_abs_error": 1e-12,
                        "rmse": 1e-13,
                    },
                    "valid_range_leakage": {
                        "baseline_p4_lowpass_max_abs": 0.0,
                        "baseline_p3_lowpass_max_abs": 0.0,
                        "baseline_readback_p4_lowpass_max_abs": 0.0,
                        "baseline_readback_p3_lowpass_max_abs": 0.0,
                        "dense_readback_p4_lowpass_max_abs": 0.0,
                        "dense_readback_p3_lowpass_max_abs": 0.0,
                        "full_dense_readback_p4_lowpass_max_abs": 0.0,
                        "full_dense_readback_p3_lowpass_max_abs": 0.0,
                        "maximum_observed": 0.0,
                        "threshold": 1e-8,
                        "gate_passed": True,
                    },
                    "independent_writability": {
                        "probe_count": 18,
                        "probes_per_band": 3,
                        "minimum_self_gain": 1.0,
                        "maximum_cross_talk": 0.0,
                        "maximum_off_target_l2_ratio": 0.0,
                        "probes": probes,
                    },
                    "boundary_writability": {
                        "probe_count": 12,
                        "positions_per_band": 2,
                        "minimum_self_gain": 1.0,
                        "maximum_cross_talk": 0.0,
                        "maximum_off_target_l2_ratio": 0.0,
                        "gate_passed": True,
                        "probes": boundary_probes,
                    },
                    "dense_222360_sign_trial": {
                        "slot_count": 222_360,
                        "selection": (
                            "all P4 coordinates plus first 8584 coordinates "
                            "of each P3 band"
                        ),
                        "sign_generator": "park_miller_48271_thresholded_v1",
                        "sign_errors": 0,
                        "maximum_absolute_coordinate_error": 0.0,
                        "selected_l2_error_ratio": 0.0,
                        "unselected_l2_ratio": 0.0,
                    },
                    "dense_245760_full_candidate_trial": {
                        "slot_count": 245_760,
                        "selection": "all independent P3+P4 coordinates",
                        "sign_generator": (
                            "park_miller_48271_thresholded_offset_20260730_v1"
                        ),
                        "sign_errors": 0,
                        "maximum_absolute_coordinate_error": 0.0,
                        "selected_l2_error_ratio": 0.0,
                        "maximum_valid_range_lowpass_abs": 0.0,
                        "gate_passed": True,
                    },
                    "locked_thresholds": {
                        "reconstruction_max_abs": 1e-8,
                        "minimum_self_gain": 0.99,
                        "maximum_cross_talk": 0.01,
                        "maximum_off_target_l2_ratio": 0.05,
                        "valid_range_lowpass_max_abs": 1e-8,
                        "dense_maximum_absolute_coordinate_error": 1e-8,
                        "dense_relative_l2_error": 1e-10,
                        "minimum_probes_per_band": 3,
                        "required_slots": 222_360,
                    },
                    "gate": gate,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        config = replace(
            DigitalADConfig(),
            transform_profile=OCTAVE_PDFB_PROFILE,
            levels=4,
            directions=4,
            eligible_level=0,
        ).validate()
        environment = {
            "CTSTEG_PDFB_TOOLBOX_PATH": str(toolbox),
            "CTSTEG_PDFB_RUNTIME": sys.executable,
            "CTSTEG_PDFB_STAGE0_EVIDENCE": str(evidence),
        }
        return config, environment, inventory_tree

    def test_profile_fixes_scientific_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixes levels=4"):
            replace(
                DigitalADConfig(),
                transform_profile=OCTAVE_PDFB_PROFILE,
            ).validate()
        valid = replace(
            DigitalADConfig(),
            transform_profile=OCTAVE_PDFB_PROFILE,
            levels=4,
            directions=4,
            eligible_level=0,
        ).validate()
        self.assertEqual(valid.transform_profile, OCTAVE_PDFB_PROFILE)
        self.assertEqual(
            _ensure_transform_boundary(valid, engineering_control=False),
            "final_pdfb_range_multiscale_coordinates_not_author_equivalent",
        )
        with self.assertRaisesRegex(ValueError, "final research interpretation"):
            _ensure_transform_boundary(valid, engineering_control=True)

    def test_adapter_fails_closed_without_stage0_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config, _environment, _tree = self._fixture(Path(temporary))
            with (
                patch.dict(os.environ, {}, clear=True),
                self.assertRaisesRegex(RuntimeError, "TOOLBOX_PATH"),
            ):
                OctavePdfbTransformAdapter(config)

    def test_adapter_rejects_failed_stage0_writability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, environment, _tree = self._fixture(root)
            evidence = Path(environment["CTSTEG_PDFB_STAGE0_EVIDENCE"])
            payload = json.loads(evidence.read_text(encoding="utf-8"))
            payload["independent_writability"]["minimum_self_gain"] = 0.7176
            payload["independent_writability"]["maximum_cross_talk"] = 0.145
            payload["independent_writability"][
                "maximum_off_target_l2_ratio"
            ] = 0.6034
            evidence.write_text(
                json.dumps(payload) + "\n",
                encoding="utf-8",
            )
            with (
                patch.dict(os.environ, environment, clear=False),
                self.assertRaisesRegex(ValueError, "writability"),
            ):
                OctavePdfbTransformAdapter(config)

    def test_numeric_bridge_preserves_pdfb_level_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config, environment, tree = self._fixture(Path(temporary))
            with (
                patch.dict(os.environ, environment, clear=False),
                patch(
                    "ctsteg.digital_ad.transform_adapter."
                    "_PDFB_TOOLBOX_TREE_SHA256",
                    tree,
                ),
                patch(
                    "ctsteg.digital_ad.transform_adapter._octave_version",
                    return_value="GNU Octave fixture",
                ),
            ):
                adapter = OctavePdfbTransformAdapter(config)
            captured: dict[str, np.ndarray] = {}

            def bridge(
                operation: str,
                input_path: Path,
                output_path: Path,
                bridge_path: Path,
            ) -> None:
                self.assertTrue(bridge_path.is_file())
                if operation == "analyze":
                    counts = (4, 4, 3, 3)
                    shapes = np.asarray(
                        [
                            *([(4, 4)] * 4),
                            *([(8, 8)] * 4),
                            *([(128, 128)] * 3),
                            *([(256, 256)] * 3),
                        ],
                        dtype=np.float64,
                    )
                    sizes = [int(np.prod(shape)) for shape in shapes]
                    offsets = np.asarray(
                        [0, *np.cumsum(sizes)],
                        dtype=np.float64,
                    )
                    values = np.concatenate(
                        [
                            np.full(size, slot + 1, dtype=np.float64)
                            for slot, size in enumerate(sizes)
                        ]
                    )
                    savemat(
                        output_path,
                        {
                            "lowpass_values": np.arange(4, dtype=np.float64),
                            "lowpass_shape": np.asarray([2, 2]),
                            "detail_values": values,
                            "detail_counts": np.asarray(counts),
                            "detail_shapes": shapes,
                            "detail_offsets": offsets,
                        },
                    )
                    return
                payload = loadmat(input_path)
                captured["detail_values"] = np.asarray(
                    payload["detail_values"]
                ).reshape(-1)
                savemat(
                    output_path,
                    {"image": np.zeros((512, 512), dtype=np.float64)},
                )

            with patch.object(adapter, "_run_bridge", side_effect=bridge):
                coefficients = adapter.analyze(
                    np.zeros((512, 512), dtype=np.float64)
                )
                self.assertEqual(float(coefficients.details[0][0][0, 0]), 12.0)
                self.assertEqual(float(coefficients.details[1][0][0, 0]), 9.0)
                self.assertEqual(float(coefficients.details[3][0][0, 0]), 1.0)
                self.assertEqual(
                    tuple(len(level) for level in coefficients.details),
                    (3, 3, 4, 4),
                )
                descriptors = adapter.descriptors(
                    coefficients,
                    eligible_only=True,
                )
                self.assertEqual(
                    [item.band_id for item in descriptors],
                    [
                        "V:P4:LH",
                        "V:P4:HL",
                        "V:P4:HH",
                        "V:P3:LH",
                        "V:P3:HL",
                        "V:P3:HH",
                    ],
                )
                self.assertEqual(len(adapter.eligible_bands(coefficients)), 6)
                perturbation = tuple(
                    np.ones_like(band)
                    for band in adapter.eligible_bands(coefficients)
                )
                modified = adapter.apply_eligible_perturbation(
                    coefficients,
                    perturbation,
                    strength=2.0,
                )
                np.testing.assert_allclose(
                    modified.details[0][0],
                    coefficients.details[0][0] + 2.0,
                )
                np.testing.assert_array_equal(
                    modified.details[2][0],
                    coefficients.details[2][0],
                )
                all_ids = [
                    band_id
                    for band_id, _band in adapter.iter_all_bands(coefficients)
                ]
                self.assertEqual(all_ids[0], "P0:LOWPASS")
                self.assertEqual(all_ids[1], "P1:D0")
                self.assertEqual(all_ids[-1], "V:P4:HH")
                reconstructed = adapter.synthesize(coefficients)
            self.assertEqual(reconstructed.shape, (512, 512))
            self.assertEqual(float(captured["detail_values"][0]), 1.0)
            self.assertEqual(float(captured["detail_values"][-1]), 14.0)

    def test_fingerprint_binds_runtime_toolbox_evidence_and_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config, environment, tree = self._fixture(Path(temporary))
            with (
                patch.dict(os.environ, environment, clear=False),
                patch(
                    "ctsteg.digital_ad.transform_adapter."
                    "_PDFB_TOOLBOX_TREE_SHA256",
                    tree,
                ),
                patch(
                    "ctsteg.digital_ad.transform_adapter._octave_version",
                    return_value="GNU Octave fixture",
                ),
            ):
                first = OctavePdfbTransformAdapter(config).fingerprint()
                second = OctavePdfbTransformAdapter(config).fingerprint()
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)

    def test_transform_audit_inventory_is_pdfb_not_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config, _environment, _tree = self._fixture(Path(temporary))
        inventory = _filter_inventory(config, OCTAVE_PDFB_PROFILE)
        self.assertEqual(
            inventory["family"],
            "minh_do_pyramidal_directional_filter_bank",
        )
        self.assertEqual(inventory["nlevels_coarse_to_fine"], [2, 2, 2, 2])
        self.assertEqual(
            inventory["adapter_bands_per_level_coarse_to_fine"],
            [4, 4, 3, 3],
        )

    def test_research_execution_requires_one_worker(self) -> None:
        plan = {
            "material": {
                "budget": {
                    "embeddings": MANDATORY_EMBEDDINGS,
                    "mandatory_rows": MANDATORY_ROWS,
                    "max_conditional_rows": MAX_CONDITIONAL_ROWS,
                    "absolute_max_rows": ABSOLUTE_MAX_ROWS,
                }
            },
            "embeddings": [
                {
                    "payload": {
                        "config": {"transform_profile": OCTAVE_PDFB_PROFILE}
                    }
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "explicit --workers 1"):
            execute_research_plan(
                plan,
                output_root="unused",
                runtime_gate_report="unused",
                workers=0,
            )

    def test_pyramid_container_remains_compatible(self) -> None:
        coefficients = PyramidCoefficients(
            lowpass=np.zeros((2, 2)),
            details=[
                [np.zeros((2, 3)) for _ in range(4)]
                for _ in range(4)
            ],
        )
        self.assertEqual(coefficients.coefficient_count, 100)


if __name__ == "__main__":
    unittest.main()
