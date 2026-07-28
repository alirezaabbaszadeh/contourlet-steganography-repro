"""Fail-closed Stage-0 gate for an external MATLAB PDFB implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import Any, Mapping, Sequence

import numpy as np

from ctsteg.provenance import sha256_file, sha256_json

from .transform_audit import deterministic_audit_image


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_FILTER_PATTERN = re.compile(r"^[A-Za-z0-9_.+-]+$")


class PdfbEvidenceError(ValueError):
    """Raised when an evidence artifact violates the Stage-0 schema."""


@dataclass(frozen=True)
class PdfbGateSpec:
    """Explicit assumptions and quantitative gates for one PDFB interpretation."""

    schema: int = 1
    profile: str = "matlab_pdfb_explicit_v1"
    assumption_status: str = "unverified_interpretation"
    toolbox_release: str = "Minh Do Contourlet Toolbox 1.0.0.0"
    pfilter: str = "9-7"
    dfilter: str = "pkva"
    nlevels: tuple[int, ...] = (2, 2, 2, 2)
    eligible_pyramid_level_from_coarse: int = 4
    cover_size: int = 512
    required_slots: int = 222_360
    probe_delta: float = 1.0
    probe_fractions: tuple[float, ...] = (0.25, 0.5, 0.75)
    reconstruction_max_abs_tolerance: float = 1e-8
    coefficient_self_gain_min: float = 0.99
    coefficient_cross_talk_max: float = 0.01
    coefficient_off_target_l2_ratio_max: float = 0.05
    min_probes_per_band: int = 3

    def validate(self) -> "PdfbGateSpec":
        if self.schema != 1:
            raise ValueError("only PDFB gate schema 1 is supported")
        if self.profile != "matlab_pdfb_explicit_v1":
            raise ValueError("PDFB gate profile must be matlab_pdfb_explicit_v1")
        if self.assumption_status != "unverified_interpretation":
            raise ValueError(
                "PDFB assumptions must remain marked unverified_interpretation"
            )
        if not self.toolbox_release.strip():
            raise ValueError("toolbox_release must be explicit")
        for name, value in (
            ("pfilter", self.pfilter),
            ("dfilter", self.dfilter),
        ):
            if not value or _FILTER_PATTERN.fullmatch(value) is None:
                raise ValueError(f"{name} contains unsupported characters")
        if not self.nlevels or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 8
            for value in self.nlevels
        ):
            raise ValueError("nlevels must contain integers from 0 through 8")
        if not 1 <= self.eligible_pyramid_level_from_coarse <= len(
            self.nlevels
        ):
            raise ValueError(
                "eligible_pyramid_level_from_coarse must identify nlevels"
            )
        if self.cover_size != 512:
            raise ValueError("digital format v1 requires a 512x512 audit image")
        if self.required_slots != 222_360:
            raise ValueError("digital format v1 requires exactly 222,360 slots")
        if not math.isfinite(self.probe_delta) or self.probe_delta <= 0:
            raise ValueError("probe_delta must be finite and positive")
        if (
            len(self.probe_fractions) < self.min_probes_per_band
            or len(set(self.probe_fractions)) != len(self.probe_fractions)
            or any(
                not math.isfinite(value) or not 0 < value < 1
                for value in self.probe_fractions
            )
        ):
            raise ValueError(
                "probe_fractions must be unique interior locations and meet "
                "min_probes_per_band"
            )
        if self.min_probes_per_band < 1:
            raise ValueError("min_probes_per_band must be positive")
        thresholds = (
            self.reconstruction_max_abs_tolerance,
            self.coefficient_self_gain_min,
            self.coefficient_cross_talk_max,
            self.coefficient_off_target_l2_ratio_max,
        )
        if (
            not all(math.isfinite(value) for value in thresholds)
            or self.reconstruction_max_abs_tolerance <= 0
            or not 0 < self.coefficient_self_gain_min <= 1
            or self.coefficient_cross_talk_max < 0
            or self.coefficient_off_target_l2_ratio_max < 0
        ):
            raise ValueError("PDFB gate thresholds are invalid")
        return self

    @property
    def expected_directional_bands(self) -> int:
        depth = self.nlevels[self.eligible_pyramid_level_from_coarse - 1]
        return 3 if depth == 0 else 2**depth

    @property
    def spec_sha256(self) -> str:
        return sha256_json(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["nlevels"] = list(self.nlevels)
        payload["probe_fractions"] = list(self.probe_fractions)
        return payload

    @classmethod
    def from_toml(cls, path: str | Path) -> "PdfbGateSpec":
        with Path(path).open("rb") as stream:
            payload = tomllib.load(stream)
        values = dict(payload.get("pdfb_gate", payload))
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown PDFB gate keys: {sorted(unknown)}")
        if "nlevels" in values:
            values["nlevels"] = tuple(values["nlevels"])
        if "probe_fractions" in values:
            values["probe_fractions"] = tuple(values["probe_fractions"])
        return cls(**values).validate()


def deterministic_input_sha256(size: int = 512) -> str:
    image = deterministic_audit_image(size).astype(np.uint8)
    return hashlib.sha256(image.tobytes(order="C")).hexdigest()


def _require_mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PdfbEvidenceError(f"{name} must be a JSON object")
    return value


def _require_sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PdfbEvidenceError(f"{name} must be a JSON array")
    return value


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PdfbEvidenceError(f"{name} must be numeric")
    output = float(value)
    if not math.isfinite(output):
        raise PdfbEvidenceError(f"{name} must be finite")
    return output


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PdfbEvidenceError(f"{name} must be an integer >= {minimum}")
    return value


def _check_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise PdfbEvidenceError(f"{name} must be a lowercase SHA-256")
    return value


def _validate_band_records(
    records: object,
    *,
    name: str,
) -> tuple[tuple[str, tuple[int, int], int], ...]:
    output: list[tuple[str, tuple[int, int], int]] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(_require_sequence(records, name)):
        record = _require_mapping(raw, f"{name}[{index}]")
        band_id = record.get("band_id")
        if not isinstance(band_id, str) or not band_id:
            raise PdfbEvidenceError(f"{name}[{index}].band_id is invalid")
        if band_id in identifiers:
            raise PdfbEvidenceError(f"duplicate band ID: {band_id}")
        identifiers.add(band_id)
        shape_values = _require_sequence(
            record.get("shape"),
            f"{name}[{index}].shape",
        )
        if len(shape_values) != 2:
            raise PdfbEvidenceError(f"{name}[{index}].shape must have 2 values")
        shape = (
            _integer(shape_values[0], f"{name}[{index}].shape[0]", minimum=1),
            _integer(shape_values[1], f"{name}[{index}].shape[1]", minimum=1),
        )
        count = _integer(
            record.get("coefficient_count"),
            f"{name}[{index}].coefficient_count",
            minimum=1,
        )
        if count != shape[0] * shape[1]:
            raise PdfbEvidenceError(
                f"{name}[{index}] coefficient count does not match shape"
            )
        output.append((band_id, shape, count))
    if not output:
        raise PdfbEvidenceError(f"{name} must not be empty")
    return tuple(output)


def _condition(
    name: str,
    observed: int | float,
    comparator: str,
    threshold: int | float,
    passed: bool,
) -> dict[str, object]:
    return {
        "name": name,
        "observed": observed,
        "comparator": comparator,
        "threshold": threshold,
        "passed": bool(passed),
    }


def validate_pdfb_evidence(
    evidence: Mapping[str, Any],
    spec: PdfbGateSpec,
    *,
    evidence_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate external evidence and return a non-destructive gate decision."""

    cfg = spec.validate()
    if evidence.get("schema") != 1:
        raise PdfbEvidenceError("evidence schema must be 1")
    if evidence.get("runtime_verified") is not True:
        raise PdfbEvidenceError("evidence is not marked runtime_verified")
    if evidence.get("profile") != cfg.profile:
        raise PdfbEvidenceError("evidence profile does not match the gate spec")
    if evidence.get("spec_sha256") != cfg.spec_sha256:
        raise PdfbEvidenceError("evidence spec SHA-256 does not match")
    if evidence.get("assumption_status") != cfg.assumption_status:
        raise PdfbEvidenceError("evidence assumption status changed")
    if evidence.get("author_equivalence_claimed") is not False:
        raise PdfbEvidenceError(
            "evidence must explicitly reject author-equivalence claims"
        )

    parameters = _require_mapping(evidence.get("parameters"), "parameters")
    expected_parameters = {
        "pfilter": cfg.pfilter,
        "dfilter": cfg.dfilter,
        "nlevels": list(cfg.nlevels),
        "eligible_pyramid_level_from_coarse": (
            cfg.eligible_pyramid_level_from_coarse
        ),
        "cover_size": cfg.cover_size,
        "probe_delta": cfg.probe_delta,
        "probe_fractions": list(cfg.probe_fractions),
    }
    for key, expected in expected_parameters.items():
        if parameters.get(key) != expected:
            raise PdfbEvidenceError(f"parameters.{key} does not match the spec")

    input_record = _require_mapping(evidence.get("input"), "input")
    if input_record.get("generator") != "ctsteg_deterministic_audit_v1":
        raise PdfbEvidenceError("unexpected audit input generator")
    if input_record.get("shape") != [cfg.cover_size, cfg.cover_size]:
        raise PdfbEvidenceError("audit input shape does not match the spec")
    expected_input_sha = deterministic_input_sha256(cfg.cover_size)
    if input_record.get("uint8_row_major_sha256") != expected_input_sha:
        raise PdfbEvidenceError("audit input SHA-256 does not match")

    toolbox = _require_mapping(evidence.get("toolbox"), "toolbox")
    if toolbox.get("declared_release") != cfg.toolbox_release:
        raise PdfbEvidenceError("toolbox release does not match the spec")
    if not isinstance(toolbox.get("root"), str) or not toolbox["root"]:
        raise PdfbEvidenceError("toolbox.root is missing")
    for function_name in ("pdfbdec", "pdfbrec"):
        path = toolbox.get(f"{function_name}_path")
        if not isinstance(path, str) or not path:
            raise PdfbEvidenceError(f"toolbox.{function_name}_path is missing")
        _check_sha256(
            toolbox.get(f"{function_name}_sha256"),
            f"toolbox.{function_name}_sha256",
        )

    runtime = _require_mapping(evidence.get("runtime"), "runtime")
    for key in ("matlab_version", "matlab_release", "computer"):
        if not isinstance(runtime.get(key), str) or not runtime[key]:
            raise PdfbEvidenceError(f"runtime.{key} is missing")

    all_bands = _validate_band_records(evidence.get("bands"), name="bands")
    eligible_bands = _validate_band_records(
        evidence.get("eligible_bands"),
        name="eligible_bands",
    )
    all_by_id = {
        band_id: (shape, count)
        for band_id, shape, count in all_bands
    }
    for band_id, shape, count in eligible_bands:
        if band_id not in all_by_id:
            raise PdfbEvidenceError(
                "eligible_bands contains an unknown band ID"
            )
        if all_by_id[band_id] != (shape, count):
            raise PdfbEvidenceError(
                f"eligible band {band_id} disagrees with bands"
            )
    expected_eligible_ids = tuple(
        f"P{cfg.eligible_pyramid_level_from_coarse}:D{index}"
        for index in range(len(eligible_bands))
    )
    if tuple(item[0] for item in eligible_bands) != expected_eligible_ids:
        raise PdfbEvidenceError(
            "eligible band IDs must be contiguous and ordered"
        )
    total_coefficient_count = sum(item[2] for item in all_bands)
    if evidence.get("total_coefficients") != total_coefficient_count:
        raise PdfbEvidenceError("total_coefficients is inconsistent")
    redundancy_ratio = _finite_number(
        evidence.get("redundancy_ratio"),
        "redundancy_ratio",
    )
    expected_redundancy = total_coefficient_count / (cfg.cover_size**2)
    if not math.isclose(
        redundancy_ratio,
        expected_redundancy,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise PdfbEvidenceError("redundancy_ratio is inconsistent")

    capacity = _require_mapping(evidence.get("capacity"), "capacity")
    candidate_count = _integer(
        capacity.get("candidate_coefficients"),
        "capacity.candidate_coefficients",
    )
    if candidate_count != sum(item[2] for item in eligible_bands):
        raise PdfbEvidenceError("candidate coefficient count is inconsistent")
    if capacity.get("required_slots") != cfg.required_slots:
        raise PdfbEvidenceError("capacity.required_slots does not match the spec")
    expected_capacity = candidate_count >= cfg.required_slots
    if capacity.get("capacity_sufficient") is not expected_capacity:
        raise PdfbEvidenceError("capacity.capacity_sufficient is inconsistent")
    if (
        capacity.get("unused_candidate_slots")
        != candidate_count - cfg.required_slots
    ):
        raise PdfbEvidenceError(
            "capacity.unused_candidate_slots is inconsistent"
        )
    candidate_utilization = _finite_number(
        capacity.get("candidate_utilization"),
        "capacity.candidate_utilization",
    )
    expected_utilization = cfg.required_slots / candidate_count
    if not math.isclose(
        candidate_utilization,
        expected_utilization,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise PdfbEvidenceError("capacity.candidate_utilization is inconsistent")

    reconstruction = _require_mapping(
        evidence.get("perfect_reconstruction"),
        "perfect_reconstruction",
    )
    reconstruction_max_abs = _finite_number(
        reconstruction.get("max_abs_error"),
        "perfect_reconstruction.max_abs_error",
    )
    reconstruction_rmse = _finite_number(
        reconstruction.get("rmse"),
        "perfect_reconstruction.rmse",
    )
    reconstruction_mse = _finite_number(
        reconstruction.get("mse"),
        "perfect_reconstruction.mse",
    )
    if (
        reconstruction_max_abs < 0
        or reconstruction_mse < 0
        or reconstruction_rmse < 0
    ):
        raise PdfbEvidenceError("reconstruction errors must be non-negative")
    if not math.isclose(
        reconstruction_rmse,
        math.sqrt(reconstruction_mse),
        rel_tol=1e-10,
        abs_tol=1e-15,
    ):
        raise PdfbEvidenceError("reconstruction MSE and RMSE are inconsistent")

    writability = _require_mapping(
        evidence.get("independent_writability"),
        "independent_writability",
    )
    probe_count = _integer(
        writability.get("probe_count"),
        "independent_writability.probe_count",
    )
    minimum_self_gain = _finite_number(
        writability.get("minimum_self_gain"),
        "independent_writability.minimum_self_gain",
    )
    maximum_cross_talk = _finite_number(
        writability.get("maximum_cross_talk"),
        "independent_writability.maximum_cross_talk",
    )
    maximum_off_target_ratio = _finite_number(
        writability.get("maximum_off_target_l2_ratio"),
        "independent_writability.maximum_off_target_l2_ratio",
    )
    if maximum_cross_talk < 0 or maximum_off_target_ratio < 0:
        raise PdfbEvidenceError("writability error metrics must be non-negative")

    eligible_by_id = {
        band_id: (shape, count)
        for band_id, shape, count in eligible_bands
    }
    raw_probes = _require_sequence(
        writability.get("probes"),
        "independent_writability.probes",
    )
    if len(raw_probes) != probe_count:
        raise PdfbEvidenceError("probe_count does not match the probe records")
    probe_band_counts = {band_id: 0 for band_id in eligible_by_id}
    probe_self_gains: list[float] = []
    probe_cross_talk: list[float] = []
    probe_off_target: list[float] = []
    probe_locations: set[tuple[str, int, int]] = set()
    probe_fraction_indices: set[tuple[str, int]] = set()
    for index, raw_probe in enumerate(raw_probes):
        probe = _require_mapping(
            raw_probe,
            f"independent_writability.probes[{index}]",
        )
        band_id = probe.get("band_id")
        if band_id not in eligible_by_id:
            raise PdfbEvidenceError(f"probe {index} has an unknown band ID")
        shape = eligible_by_id[band_id][0]
        row = _integer(probe.get("row"), f"probe {index}.row")
        column = _integer(probe.get("column"), f"probe {index}.column")
        if row >= shape[0] or column >= shape[1]:
            raise PdfbEvidenceError(f"probe {index} is outside its band")
        location = (str(band_id), row, column)
        if location in probe_locations:
            raise PdfbEvidenceError(f"probe {index} duplicates a location")
        probe_locations.add(location)
        fraction = _finite_number(
            probe.get("fraction"),
            f"probe {index}.fraction",
        )
        matching_fraction_indices = [
            fraction_index
            for fraction_index, expected in enumerate(cfg.probe_fractions)
            if math.isclose(
                fraction,
                expected,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        ]
        if len(matching_fraction_indices) != 1:
            raise PdfbEvidenceError(f"probe {index} has an unknown fraction")
        fraction_index = matching_fraction_indices[0]
        fraction_key = (str(band_id), fraction_index)
        if fraction_key in probe_fraction_indices:
            raise PdfbEvidenceError(
                f"probe {index} duplicates a band/fraction pair"
            )
        probe_fraction_indices.add(fraction_key)
        expected_row = math.floor(
            cfg.probe_fractions[fraction_index] * (shape[0] - 1)
        )
        expected_column = math.floor(
            cfg.probe_fractions[fraction_index] * (shape[1] - 1)
        )
        if row != expected_row or column != expected_column:
            raise PdfbEvidenceError(
                f"probe {index} location does not match its fraction"
            )
        self_gain = _finite_number(
            probe.get("self_gain"),
            f"probe {index}.self_gain",
        )
        cross_talk = _finite_number(
            probe.get("maximum_cross_talk"),
            f"probe {index}.maximum_cross_talk",
        )
        off_target = _finite_number(
            probe.get("off_target_l2_ratio"),
            f"probe {index}.off_target_l2_ratio",
        )
        if cross_talk < 0 or off_target < 0:
            raise PdfbEvidenceError(
                f"probe {index} error metrics must be non-negative"
            )
        probe_band_counts[str(band_id)] += 1
        probe_self_gains.append(self_gain)
        probe_cross_talk.append(cross_talk)
        probe_off_target.append(off_target)
    if not raw_probes:
        raise PdfbEvidenceError("independent writability probes are empty")
    calculated_aggregates = (
        (minimum_self_gain, min(probe_self_gains), "minimum_self_gain"),
        (maximum_cross_talk, max(probe_cross_talk), "maximum_cross_talk"),
        (
            maximum_off_target_ratio,
            max(probe_off_target),
            "maximum_off_target_l2_ratio",
        ),
    )
    for observed, calculated, name in calculated_aggregates:
        if not math.isclose(
            observed,
            calculated,
            rel_tol=1e-12,
            abs_tol=1e-15,
        ):
            raise PdfbEvidenceError(f"{name} does not match probe records")
    minimum_probes_in_any_band = min(probe_band_counts.values())
    expected_probe_count = len(eligible_bands) * cfg.min_probes_per_band
    conditions = [
        _condition(
            "eligible_direction_count",
            len(eligible_bands),
            "==",
            cfg.expected_directional_bands,
            len(eligible_bands) == cfg.expected_directional_bands,
        ),
        _condition(
            "candidate_capacity",
            candidate_count,
            ">=",
            cfg.required_slots,
            candidate_count >= cfg.required_slots,
        ),
        _condition(
            "perfect_reconstruction",
            reconstruction_max_abs,
            "<=",
            cfg.reconstruction_max_abs_tolerance,
            reconstruction_max_abs
            <= cfg.reconstruction_max_abs_tolerance,
        ),
        _condition(
            "probe_coverage",
            minimum_probes_in_any_band,
            ">=",
            cfg.min_probes_per_band,
            minimum_probes_in_any_band >= cfg.min_probes_per_band
            and probe_count >= expected_probe_count,
        ),
        _condition(
            "coefficient_self_gain",
            minimum_self_gain,
            ">=",
            cfg.coefficient_self_gain_min,
            minimum_self_gain >= cfg.coefficient_self_gain_min,
        ),
        _condition(
            "coefficient_cross_talk",
            maximum_cross_talk,
            "<=",
            cfg.coefficient_cross_talk_max,
            maximum_cross_talk <= cfg.coefficient_cross_talk_max,
        ),
        _condition(
            "coefficient_off_target_l2_ratio",
            maximum_off_target_ratio,
            "<=",
            cfg.coefficient_off_target_l2_ratio_max,
            maximum_off_target_ratio
            <= cfg.coefficient_off_target_l2_ratio_max,
        ),
    ]
    gate_passed = all(bool(item["passed"]) for item in conditions)
    return {
        "schema": 1,
        "profile": cfg.profile,
        "spec_sha256": cfg.spec_sha256,
        "evidence_sha256": evidence_sha256,
        "runtime_verified": True,
        "gate_passed": gate_passed,
        "conditions": conditions,
        "observations": {
            "total_coefficients": total_coefficient_count,
            "candidate_coefficients": candidate_count,
            "candidate_utilization": candidate_utilization,
            "eligible_band_count": len(eligible_bands),
            "probe_count": probe_count,
            "minimum_probes_in_any_band": minimum_probes_in_any_band,
            "reconstruction_max_abs_error": reconstruction_max_abs,
            "reconstruction_rmse": reconstruction_rmse,
            "minimum_self_gain": minimum_self_gain,
            "maximum_cross_talk": maximum_cross_talk,
            "maximum_off_target_l2_ratio": maximum_off_target_ratio,
        },
        "claim_boundary": {
            "author_equivalence_allowed": False,
            "direct_article_superiority_allowed": False,
            "embedding_profile_enabled": False,
            "human_review_required": True,
            "status": (
                "eligible_for_human_review"
                if gate_passed
                else "blocked_by_transform_gate"
            ),
            "reason": (
                "Passing Stage 0 validates this explicit PDFB interpretation "
                "only. It neither identifies the authors' undisclosed "
                "parameters nor enables embedding without a separate review."
            ),
        },
    }


def load_and_validate_pdfb_evidence(
    evidence_path: str | Path,
    spec: PdfbGateSpec,
) -> dict[str, Any]:
    path = Path(evidence_path)
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, Mapping):
        raise PdfbEvidenceError("PDFB evidence root must be a JSON object")
    return validate_pdfb_evidence(
        payload,
        spec,
        evidence_sha256=sha256_file(path),
    )


def _write_json(path: Path, payload: object) -> None:
    if path.exists() and path.stat().st_size:
        raise FileExistsError(f"refusing to replace non-empty file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_pdfb_validation(
    output: str | Path,
    evidence_path: str | Path,
    spec: PdfbGateSpec,
) -> dict[str, Any]:
    result = load_and_validate_pdfb_evidence(evidence_path, spec)
    _write_json(Path(output), result)
    return result


def _matlab_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def build_matlab_expression(
    spec: PdfbGateSpec,
    *,
    toolbox_path: str | Path,
    output_path: str | Path,
    matlab_scripts_path: str | Path,
) -> str:
    cfg = spec.validate()
    nlevels = " ".join(str(value) for value in cfg.nlevels)
    fractions = " ".join(f"{value:.17g}" for value in cfg.probe_fractions)
    return (
        f"addpath({_matlab_quote(Path(matlab_scripts_path).resolve())}); "
        "audit_pdfb_stage0("
        f"'ToolboxPath',{_matlab_quote(Path(toolbox_path).resolve())},"
        f"'OutputPath',{_matlab_quote(Path(output_path).resolve())},"
        f"'Profile',{_matlab_quote(cfg.profile)},"
        f"'AssumptionStatus',{_matlab_quote(cfg.assumption_status)},"
        f"'ToolboxRelease',{_matlab_quote(cfg.toolbox_release)},"
        f"'PFilter',{_matlab_quote(cfg.pfilter)},"
        f"'DFilter',{_matlab_quote(cfg.dfilter)},"
        f"'NLevels',[{nlevels}],"
        "'EligiblePyramidLevelFromCoarse',"
        f"{cfg.eligible_pyramid_level_from_coarse},"
        f"'CoverSize',{cfg.cover_size},"
        f"'RequiredSlots',{cfg.required_slots},"
        f"'ProbeDelta',{cfg.probe_delta:.17g},"
        f"'ProbeFractions',[{fractions}],"
        f"'SpecSHA256',{_matlab_quote(cfg.spec_sha256)}"
        ");"
    )


def pdfb_execution_plan(
    spec: PdfbGateSpec,
    *,
    toolbox_path: str | Path,
    raw_evidence_path: str | Path,
    matlab_scripts_path: str | Path,
    matlab_executable: str = "matlab",
) -> dict[str, Any]:
    cfg = spec.validate()
    expression = build_matlab_expression(
        cfg,
        toolbox_path=toolbox_path,
        output_path=raw_evidence_path,
        matlab_scripts_path=matlab_scripts_path,
    )
    return {
        "schema": 1,
        "profile": cfg.profile,
        "spec": cfg.to_dict(),
        "spec_sha256": cfg.spec_sha256,
        "command": [matlab_executable, "-batch", expression],
        "raw_evidence_path": str(Path(raw_evidence_path).resolve()),
        "claim_boundary": {
            "this_is_an_unverified_interpretation": True,
            "author_equivalence_allowed": False,
            "bulk_benchmark_allowed": False,
        },
    }


def write_pdfb_execution_plan(
    output: str | Path,
    spec: PdfbGateSpec,
    *,
    toolbox_path: str | Path,
    raw_evidence_path: str | Path,
    matlab_scripts_path: str | Path,
    matlab_executable: str = "matlab",
) -> dict[str, Any]:
    plan = pdfb_execution_plan(
        spec,
        toolbox_path=toolbox_path,
        raw_evidence_path=raw_evidence_path,
        matlab_scripts_path=matlab_scripts_path,
        matlab_executable=matlab_executable,
    )
    _write_json(Path(output), plan)
    return plan


def run_pdfb_stage0(
    spec: PdfbGateSpec,
    *,
    toolbox_path: str | Path,
    output_dir: str | Path,
    matlab_scripts_path: str | Path,
    matlab_executable: str = "matlab",
    timeout_seconds: float = 1_800.0,
) -> dict[str, Any]:
    """Execute MATLAB without a shell and retain evidence even when gates fail."""

    cfg = spec.validate()
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"output directory is not empty: {destination}")
    toolbox = Path(toolbox_path).resolve()
    if not toolbox.is_dir():
        raise FileNotFoundError(f"Contourlet Toolbox directory not found: {toolbox}")
    scripts = Path(matlab_scripts_path).resolve()
    audit_script = scripts / "audit_pdfb_stage0.m"
    if not audit_script.is_file():
        raise FileNotFoundError(f"MATLAB audit script not found: {audit_script}")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    executable = shutil.which(matlab_executable)
    if executable is None:
        candidate = Path(matlab_executable)
        if not candidate.is_file():
            raise FileNotFoundError(
                f"MATLAB executable not found: {matlab_executable}"
            )
        executable = str(candidate.resolve())
    destination.mkdir(parents=True, exist_ok=True)
    raw_evidence = destination / "pdfb-audit-raw.json"
    plan = pdfb_execution_plan(
        cfg,
        toolbox_path=toolbox,
        raw_evidence_path=raw_evidence,
        matlab_scripts_path=scripts,
        matlab_executable=executable,
    )
    _write_json(destination / "execution-plan.json", plan)
    _write_json(destination / "gate-spec.json", cfg.to_dict())
    try:
        completed = subprocess.run(
            plan["command"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        (destination / "stdout.log").write_text(stdout, encoding="utf-8")
        (destination / "stderr.log").write_text(stderr, encoding="utf-8")
        _write_json(
            destination / "runtime-status.json",
            {
                "timed_out": True,
                "timeout_seconds": timeout_seconds,
                "raw_evidence_exists": raw_evidence.is_file(),
            },
        )
        raise RuntimeError(
            f"MATLAB PDFB audit exceeded {timeout_seconds:g} seconds"
        ) from error
    (destination / "stdout.log").write_text(
        completed.stdout,
        encoding="utf-8",
    )
    (destination / "stderr.log").write_text(
        completed.stderr,
        encoding="utf-8",
    )
    runtime_status = {
        "returncode": completed.returncode,
        "timed_out": False,
        "timeout_seconds": timeout_seconds,
        "raw_evidence_exists": raw_evidence.is_file(),
    }
    _write_json(destination / "runtime-status.json", runtime_status)
    if completed.returncode != 0:
        raise RuntimeError(
            f"MATLAB PDFB audit failed with exit code {completed.returncode}; "
            f"see {destination / 'stderr.log'}"
        )
    if not raw_evidence.is_file():
        raise RuntimeError("MATLAB completed without writing PDFB evidence")
    validation = load_and_validate_pdfb_evidence(raw_evidence, cfg)
    _write_json(destination / "pdfb-gate-validation.json", validation)
    return validation
