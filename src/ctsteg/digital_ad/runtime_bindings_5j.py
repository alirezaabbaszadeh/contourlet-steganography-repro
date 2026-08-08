"""Freeze external PDFB/calibration bindings into FINAL-5J task identities."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from ctsteg.provenance import sha256_file
from ctsteg.runtime import atomic_write_json, utc_now

from .runtime_5j import (
    PLAN_SCHEMA_VERSION,
    PROTOCOL_ID,
    Runner5JError,
    sha256_json,
    validate_execution_plan,
)


RUNTIME_BINDING_SCHEMA_VERSION = 1
TRANSFORM_PROFILE = "octave_pdfb_9_7_pkva_nlev_2222_p3p4_range_v2"
STAGE0_PROFILE = "octave_pdfb_range_coordinates_v2"
STAGE0_SCHEME = "pdfb_9_7_pkva_multiscale_range_coordinates_p3_p4_v2"
HEX64 = set("0123456789abcdef")
REQUIRED_TOOLBOX_FILES = (
    "pdfbdec.m",
    "pdfbrec.m",
    "pfilters.m",
    "wfb2dec.m",
    "wfb2rec.m",
    "dfbdec_l.m",
    "dfbrec_l.m",
)


def _valid_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in HEX64 for character in value)
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise Runner5JError(f"missing runtime binding JSON: {path}") from error
    except json.JSONDecodeError as error:
        raise Runner5JError(f"invalid runtime binding JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise Runner5JError("runtime binding root must be an object")
    return value


def _resolve_file(binding_path: Path, declared: object, *, label: str) -> Path:
    if not isinstance(declared, str) or not declared.strip():
        raise Runner5JError(f"runtime binding {label}.path is missing")
    candidate = Path(declared).expanduser()
    if not candidate.is_absolute():
        candidate = binding_path.parent / candidate
    resolved = candidate.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise Runner5JError(f"runtime binding {label} is not a regular file: {resolved}")
    return resolved


def _resolve_directory(binding_path: Path, declared: object, *, label: str) -> Path:
    if not isinstance(declared, str) or not declared.strip():
        raise Runner5JError(f"runtime binding {label}.path is missing")
    candidate = Path(declared).expanduser()
    if not candidate.is_absolute():
        candidate = binding_path.parent / candidate
    resolved = candidate.resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise Runner5JError(f"runtime binding {label} is not a directory: {resolved}")
    return resolved


def toolbox_inventory(root: str | Path) -> tuple[dict[str, str], ...]:
    directory = Path(root).resolve()
    if not directory.is_dir():
        raise Runner5JError(f"toolbox directory missing: {directory}")
    for required in REQUIRED_TOOLBOX_FILES:
        matches = [path for path in directory.rglob(required) if path.is_file()]
        if len(matches) != 1:
            raise Runner5JError(
                f"toolbox must contain exactly one {required}; found {len(matches)}"
            )
    if not any(path.is_file() for path in directory.rglob("resampc.*")):
        raise Runner5JError("toolbox contains no resampc implementation")
    return tuple(
        {
            "path": path.relative_to(directory).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    )


def toolbox_tree_sha256(inventory: Iterable[Mapping[str, str]]) -> str:
    digest = hashlib.sha256()
    for item in inventory:
        digest.update(str(item["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _binding_object(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, Mapping):
        raise Runner5JError(f"runtime binding {name} must be an object")
    return value


def validate_runtime_bindings(
    path: str | Path,
    *,
    check_files: bool = True,
) -> dict[str, Any]:
    """Validate a frozen binding file and optionally verify all bound bytes."""

    source = Path(path).resolve()
    payload = _load_json(source)
    if payload.get("schema_version") != RUNTIME_BINDING_SCHEMA_VERSION:
        raise Runner5JError("runtime binding schema_version mismatch")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise Runner5JError("runtime binding protocol_id mismatch")
    if payload.get("status") != "frozen":
        raise Runner5JError("runtime bindings are not frozen")
    if payload.get("transform_profile") != TRANSFORM_PROFILE:
        raise Runner5JError("runtime binding transform profile mismatch")
    if payload.get("science_ready") is not True:
        raise Runner5JError("runtime bindings are not science-ready")
    blockers = payload.get("blockers")
    if blockers not in ([], None):
        raise Runner5JError(f"runtime bindings still contain blockers: {blockers!r}")
    if not str(payload.get("approved_by", "")).strip():
        raise Runner5JError("runtime bindings have no approver")
    if not str(payload.get("approved_at", "")).strip():
        raise Runner5JError("runtime bindings have no approval timestamp")

    runtime = _binding_object(payload, "runtime_executable")
    toolbox = _binding_object(payload, "toolbox")
    stage0 = _binding_object(payload, "stage0_evidence")
    stability = _binding_object(payload, "stability_profile")
    for label, item, field in (
        ("runtime_executable", runtime, "sha256"),
        ("toolbox", toolbox, "tree_sha256"),
        ("stage0_evidence", stage0, "sha256"),
        ("stability_profile", stability, "sha256"),
    ):
        if not _valid_hash(item.get(field)):
            raise Runner5JError(f"runtime binding {label}.{field} is not frozen")

    report: dict[str, Any] = {
        "schema_version": RUNTIME_BINDING_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "binding_path": str(source),
        "binding_sha256": sha256_file(source),
        "transform_profile": TRANSFORM_PROFILE,
        "checked_files": check_files,
    }
    if not check_files:
        return report

    runtime_path = _resolve_file(
        source,
        runtime.get("path"),
        label="runtime_executable",
    )
    if not os.access(runtime_path, os.X_OK):
        raise Runner5JError(f"runtime executable is not executable: {runtime_path}")
    toolbox_path = _resolve_directory(source, toolbox.get("path"), label="toolbox")
    stage0_path = _resolve_file(source, stage0.get("path"), label="stage0_evidence")
    stability_path = _resolve_file(
        source,
        stability.get("path"),
        label="stability_profile",
    )

    runtime_hash = sha256_file(runtime_path)
    if runtime_hash != runtime["sha256"]:
        raise Runner5JError("runtime executable SHA-256 mismatch")
    inventory = toolbox_inventory(toolbox_path)
    tree_hash = toolbox_tree_sha256(inventory)
    if tree_hash != toolbox["tree_sha256"]:
        raise Runner5JError("Contourlet toolbox tree SHA-256 mismatch")
    stage0_hash = sha256_file(stage0_path)
    if stage0_hash != stage0["sha256"]:
        raise Runner5JError("Stage-0 evidence SHA-256 mismatch")
    stability_hash = sha256_file(stability_path)
    if stability_hash != stability["sha256"]:
        raise Runner5JError("stability profile SHA-256 mismatch")

    stage0_payload = _load_json(stage0_path)
    expected_stage0 = {
        "runtime_verified": True,
        "passed": True,
        "profile": STAGE0_PROFILE,
        "scheme": STAGE0_SCHEME,
        "exploratory": False,
        "author_equivalence_claimed": False,
    }
    for key, expected in expected_stage0.items():
        if stage0_payload.get(key) != expected:
            raise Runner5JError(
                f"Stage-0 evidence {key} does not match the locked PDFB contract"
            )

    stability_payload = _load_json(stability_path)
    if stability_payload.get("calibration_only") is not True:
        raise Runner5JError("stability profile is not marked calibration-only")
    if stability_payload.get("transform_profile") != TRANSFORM_PROFILE:
        raise Runner5JError("stability profile transform profile mismatch")
    if not _valid_hash(stability_payload.get("transform_fingerprint")):
        raise Runner5JError("stability profile transform fingerprint is invalid")
    if not isinstance(stability_payload.get("stability"), dict) or not stability_payload["stability"]:
        raise Runner5JError("stability profile contains no band values")

    report.update(
        {
            "runtime_executable": str(runtime_path),
            "runtime_executable_sha256": runtime_hash,
            "toolbox": str(toolbox_path),
            "toolbox_tree_sha256": tree_hash,
            "toolbox_file_count": len(inventory),
            "stage0_evidence": str(stage0_path),
            "stage0_evidence_sha256": stage0_hash,
            "stage0_profile": STAGE0_PROFILE,
            "stage0_scheme": STAGE0_SCHEME,
            "stability_profile": str(stability_path),
            "stability_profile_sha256": stability_hash,
            "stability_transform_fingerprint": stability_payload[
                "transform_fingerprint"
            ],
        }
    )
    return report


def _embedding_identity(
    task: Mapping[str, Any],
    common_identity: Mapping[str, Any],
) -> str:
    return sha256_json(
        {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "component": task["component"],
            "pair_id": task["pair_id"],
            "cover_sha256": task["cover_sha256"],
            "secret_sha256": task["secret_sha256"],
            "method": task["method"],
            "method_fingerprint": task["method_fingerprint"],
            "payload_fraction": task["payload_fraction"],
            "target_psnr_db": task["target_psnr_db"],
            "payload_format_version": task["payload_format_version"],
            **dict(common_identity),
        }
    )


def _evaluation_identity(
    task: Mapping[str, Any],
    common_identity: Mapping[str, Any],
) -> str:
    return sha256_json(
        {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "embedding_id": task["embedding_id"],
            "channel_instance_id": task["channel_instance_id"],
            "family": task["family"],
            "severity": task["severity"],
            "realization": task["realization"],
            "pair_seed": task["pair_seed"],
            **dict(common_identity),
        }
    )


def finalize_execution_plan(
    unbound_plan: Mapping[str, Any],
    *,
    runtime_bindings_path: str | Path,
    check_files: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Re-address every task after freezing external runtime bindings."""

    base = validate_execution_plan(unbound_plan)
    if "runtime_bindings_sha256" in unbound_plan["created_from"]:
        raise Runner5JError("execution plan is already runtime-bound")
    binding_report = validate_runtime_bindings(
        runtime_bindings_path,
        check_files=check_files,
    )
    common_identity = {
        **dict(unbound_plan["created_from"]),
        "runtime_bindings_sha256": binding_report["binding_sha256"],
    }

    embedding_id_map: dict[str, str] = {}
    embeddings: list[dict[str, Any]] = []
    for raw in unbound_plan["embeddings"]:
        item = dict(raw)
        previous = str(item["embedding_id"])
        item["embedding_id"] = _embedding_identity(item, common_identity)
        embedding_id_map[previous] = item["embedding_id"]
        embeddings.append(item)

    evaluations: list[dict[str, Any]] = []
    for raw in unbound_plan["evaluations"]:
        item = dict(raw)
        previous_embedding = str(item["embedding_id"])
        try:
            item["embedding_id"] = embedding_id_map[previous_embedding]
        except KeyError as error:
            raise Runner5JError(
                f"evaluation references unknown unbound embedding {previous_embedding}"
            ) from error
        item["evaluation_id"] = _evaluation_identity(item, common_identity)
        evaluations.append(item)

    material = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "created_from": common_identity,
        "counts": dict(unbound_plan["counts"]),
        "embeddings": embeddings,
        "evaluations": evaluations,
    }
    plan_id = sha256_json(material)
    finalized = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "plan_id": plan_id,
        "run_id": f"5j-{plan_id[:20]}",
        "base_plan_id": base["plan_id"],
        "created_from": common_identity,
        "counts": dict(unbound_plan["counts"]),
        "embeddings": embeddings,
        "evaluations": evaluations,
    }
    validate_execution_plan(finalized)
    return finalized, binding_report


def verify_finalized_execution_plan(
    plan: Mapping[str, Any],
    *,
    runtime_bindings_path: str | Path,
    check_files: bool = True,
) -> dict[str, Any]:
    validate_execution_plan(plan)
    expected = plan.get("created_from", {}).get("runtime_bindings_sha256")
    if not _valid_hash(expected):
        raise Runner5JError("execution plan is not finalized with runtime bindings")
    report = validate_runtime_bindings(
        runtime_bindings_path,
        check_files=check_files,
    )
    if report["binding_sha256"] != expected:
        raise Runner5JError("execution plan/runtime binding SHA-256 mismatch")
    return report


def record_runtime_binding_verification(
    run_dir: str | Path,
    report: Mapping[str, Any],
) -> Path:
    destination = Path(run_dir).resolve() / "runtime_binding_verification.json"
    atomic_write_json(
        destination,
        {
            **dict(report),
            "verified_at": utc_now(),
        },
    )
    return destination
