"""Fail-closed preflight and status reconstruction for FINAL-5J-v1.

This module deliberately does not extend the historical 64/88 runtime.  It
validates the expanded 530/8,420 execution plan, verifies every referenced
scientific input and fingerprint, reconstructs progress from immutable cache
objects plus the backup ledger, and publishes one durable run preflight.

Numerical task execution is added behind this contract; no unplanned task can
be created here.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from ctsteg.provenance import sha256_file
from ctsteg.runtime import ContentStore, atomic_write_json, read_json, utc_now


PROTOCOL_ID = "FINAL-5J-v1"
PLAN_SCHEMA_VERSION = 1
PAYLOAD_FORMAT_VERSION = 2
EXPECTED_COUNTS = {
    "main_embeddings": 350,
    "main_evaluations": 7700,
    "payload_sweep_embeddings": 90,
    "payload_sweep_evaluations": 360,
    "psnr_sweep_embeddings": 90,
    "psnr_sweep_evaluations": 360,
    "total_embeddings": 530,
    "total_evaluations": 8420,
}
COMPONENTS = {"main", "payload_sweep", "psnr_sweep"}
METHODS = {"C0", "C1", "C2", "C3_NP", "C3", "B1", "B2"}
INTERNAL_METHODS = {"C0", "C1", "C2", "C3_NP", "C3"}
HEX64 = re.compile(r"^[a-f0-9]{64}$")
SAFE_PAIR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

CREATED_FROM_PATHS = {
    "study_plan_sha256": "configs/5j/study_plan_v1.json",
    "seed_lock_sha256": "configs/5j/seeds.lock.json",
    "main_manifest_sha256": "data-manifests/5j/main_50_pairs.csv",
    "sweep_manifest_sha256": "data-manifests/5j/sweep_10_pairs.csv",
    "baseline_registry_sha256": "configs/5j/baseline_registry_v1.json",
    "config_sha256": "configs/5j/format_v2_layer_integrity.toml",
}


class Runner5JError(RuntimeError):
    """Raised when a 5J runtime gate fails closed."""


def canonical_json_bytes(payload: object) -> bytes:
    """Match the execution-plan builder's canonical JSON contract exactly."""

    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_json(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def load_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise Runner5JError(f"missing JSON file: {source}") from error
    except json.JSONDecodeError as error:
        raise Runner5JError(f"invalid JSON in {source}: {error}") from error
    if not isinstance(value, dict):
        raise Runner5JError(f"JSON root must be an object: {source}")
    return value


def _require_hash(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise Runner5JError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _require_number(value: object, *, field: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Runner5JError(f"{field} must be numeric")
    result = float(value)
    if minimum is not None and result < minimum:
        raise Runner5JError(f"{field} must be at least {minimum}")
    return result


def source_tree_fingerprint(source_root: str | Path) -> str:
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise Runner5JError(f"source root missing: {root}")
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*.py"))
        if path.is_file()
    ]
    if not records:
        raise Runner5JError("source tree contains no Python files")
    return sha256_json({"schema": 1, "files": records})


def _embedding_identity(
    task: Mapping[str, Any],
    *,
    common_identity: Mapping[str, str],
) -> str:
    material = {
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
    return sha256_json(material)


def _evaluation_identity(
    task: Mapping[str, Any],
    *,
    common_identity: Mapping[str, str],
) -> str:
    material = {
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
    return sha256_json(material)


def validate_execution_plan(
    plan: Mapping[str, Any],
    *,
    expected_counts: Mapping[str, int] = EXPECTED_COUNTS,
    run_id_prefix: str = "5j",
    expected_plan_kind: str | None = None,
) -> dict[str, Any]:
    """Validate all task identities and return immutable indexes."""

    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise Runner5JError("execution plan schema_version mismatch")
    if plan.get("protocol_id") != PROTOCOL_ID:
        raise Runner5JError("execution plan protocol_id mismatch")
    plan_kind = plan.get("plan_kind")
    if expected_plan_kind is not None and plan_kind != expected_plan_kind:
        raise Runner5JError("execution plan plan_kind mismatch")
    if expected_plan_kind is None and plan_kind is not None:
        raise Runner5JError("scientific execution plan must not declare an engineering plan_kind")
    if not isinstance(run_id_prefix, str) or not run_id_prefix:
        raise Runner5JError("run_id_prefix must be non-empty")

    created_from = plan.get("created_from")
    counts = plan.get("counts")
    embeddings = plan.get("embeddings")
    evaluations = plan.get("evaluations")
    if not isinstance(created_from, dict):
        raise Runner5JError("execution plan created_from must be an object")
    if not isinstance(counts, dict):
        raise Runner5JError("execution plan counts must be an object")
    if not isinstance(embeddings, list) or not isinstance(evaluations, list):
        raise Runner5JError("execution plan task collections must be arrays")

    for field in (*CREATED_FROM_PATHS, "source_fingerprint"):
        _require_hash(created_from.get(field), field=f"created_from.{field}")
    if dict(counts) != dict(expected_counts):
        raise Runner5JError(
            f"execution plan counts differ from locked contract: {counts!r}"
        )
    if len(embeddings) != counts["total_embeddings"]:
        raise Runner5JError("embedding array length differs from locked count")
    if len(evaluations) != counts["total_evaluations"]:
        raise Runner5JError("evaluation array length differs from locked count")

    embedding_by_id: dict[str, dict[str, Any]] = {}
    component_embedding_counts: Counter[str] = Counter()
    for index, raw in enumerate(embeddings):
        if not isinstance(raw, dict):
            raise Runner5JError(f"embedding {index} must be an object")
        task = dict(raw)
        object_id = _require_hash(
            task.get("embedding_id"), field=f"embedding[{index}].embedding_id"
        )
        if object_id in embedding_by_id:
            raise Runner5JError(f"duplicate embedding_id: {object_id}")
        component = str(task.get("component", ""))
        method = str(task.get("method", ""))
        pair_id = str(task.get("pair_id", ""))
        if component not in COMPONENTS:
            raise Runner5JError(f"embedding {object_id} has invalid component")
        if method not in METHODS:
            raise Runner5JError(f"embedding {object_id} has invalid method")
        if not SAFE_PAIR_ID.fullmatch(pair_id):
            raise Runner5JError(f"embedding {object_id} has invalid pair_id")
        _require_hash(task.get("cover_sha256"), field="cover_sha256")
        _require_hash(task.get("secret_sha256"), field="secret_sha256")
        _require_hash(task.get("method_fingerprint"), field="method_fingerprint")
        fraction = _require_number(
            task.get("payload_fraction"), field="payload_fraction", minimum=0.0
        )
        if not 0.0 < fraction <= 1.0:
            raise Runner5JError("payload_fraction must be within (0,1]")
        _require_number(
            task.get("target_psnr_db"), field="target_psnr_db", minimum=0.0
        )
        if task.get("payload_format_version") != PAYLOAD_FORMAT_VERSION:
            raise Runner5JError("5J embeddings require payload format version 2")
        expected_id = _embedding_identity(task, common_identity=created_from)
        if expected_id != object_id:
            raise Runner5JError(
                f"embedding identity mismatch for {pair_id}:{method}:{component}"
            )
        embedding_by_id[object_id] = task
        component_embedding_counts[component] += 1

    evaluation_by_id: dict[str, dict[str, Any]] = {}
    component_evaluation_counts: Counter[str] = Counter()
    for index, raw in enumerate(evaluations):
        if not isinstance(raw, dict):
            raise Runner5JError(f"evaluation {index} must be an object")
        task = dict(raw)
        object_id = _require_hash(
            task.get("evaluation_id"), field=f"evaluation[{index}].evaluation_id"
        )
        if object_id in evaluation_by_id:
            raise Runner5JError(f"duplicate evaluation_id: {object_id}")
        embedding_id = _require_hash(
            task.get("embedding_id"), field="evaluation.embedding_id"
        )
        embedding = embedding_by_id.get(embedding_id)
        if embedding is None:
            raise Runner5JError(
                f"evaluation {object_id} references unknown embedding {embedding_id}"
            )
        for field in ("component", "pair_id", "method"):
            if task.get(field) != embedding.get(field):
                raise Runner5JError(
                    f"evaluation {object_id} disagrees with embedding on {field}"
                )
        if not str(task.get("channel_instance_id", "")).strip():
            raise Runner5JError(f"evaluation {object_id} has no channel instance")
        if task.get("family") not in {"clean", "jpeg", "gaussian", "salt_pepper"}:
            raise Runner5JError(f"evaluation {object_id} has invalid channel family")
        realization = task.get("realization")
        if not isinstance(realization, int) or not 1 <= realization <= 3:
            raise Runner5JError(f"evaluation {object_id} has invalid realization")
        pair_seed = task.get("pair_seed")
        if pair_seed is not None and (
            not isinstance(pair_seed, int) or not 0 <= pair_seed < 2**32
        ):
            raise Runner5JError(f"evaluation {object_id} has invalid pair seed")
        expected_id = _evaluation_identity(task, common_identity=created_from)
        if expected_id != object_id:
            raise Runner5JError(
                f"evaluation identity mismatch for {task.get('pair_id')}:"
                f"{task.get('method')}:{task.get('channel_instance_id')}"
            )
        evaluation_by_id[object_id] = task
        component_evaluation_counts[str(task["component"])] += 1

    observed_counts = {
        "main_embeddings": component_embedding_counts["main"],
        "main_evaluations": component_evaluation_counts["main"],
        "payload_sweep_embeddings": component_embedding_counts["payload_sweep"],
        "payload_sweep_evaluations": component_evaluation_counts["payload_sweep"],
        "psnr_sweep_embeddings": component_embedding_counts["psnr_sweep"],
        "psnr_sweep_evaluations": component_evaluation_counts["psnr_sweep"],
        "total_embeddings": len(embedding_by_id),
        "total_evaluations": len(evaluation_by_id),
    }
    if observed_counts != dict(expected_counts):
        raise Runner5JError(
            f"task component counts differ from locked contract: {observed_counts!r}"
        )

    material = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "created_from": dict(created_from),
        "counts": dict(counts),
        "embeddings": embeddings,
        "evaluations": evaluations,
    }
    if plan_kind is not None:
        material["plan_kind"] = plan_kind
    expected_plan_id = sha256_json(material)
    if plan.get("plan_id") != expected_plan_id:
        raise Runner5JError("execution plan plan_id mismatch")
    expected_run_id = f"{run_id_prefix}-{expected_plan_id[:20]}"
    if plan.get("run_id") != expected_run_id:
        raise Runner5JError("execution plan run_id mismatch")

    return {
        "plan_id": expected_plan_id,
        "run_id": expected_run_id,
        "created_from": dict(created_from),
        "counts": observed_counts,
        "embedding_by_id": embedding_by_id,
        "evaluation_by_id": evaluation_by_id,
    }


def verify_created_from(
    plan: Mapping[str, Any],
    *,
    repository_root: str | Path,
) -> dict[str, str]:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise Runner5JError(f"repository root missing: {root}")
    created_from = plan["created_from"]
    verified: dict[str, str] = {}
    for field, relative in CREATED_FROM_PATHS.items():
        path = root / relative
        actual = sha256_file(path)
        expected = str(created_from[field])
        if actual != expected:
            raise Runner5JError(
                f"fingerprint mismatch for {relative}: {actual} != {expected}"
            )
        verified[field] = actual
    source = source_tree_fingerprint(root / "src/ctsteg")
    expected_source = str(created_from["source_fingerprint"])
    if source != expected_source:
        raise Runner5JError(
            f"source fingerprint mismatch: {source} != {expected_source}"
        )
    verified["source_fingerprint"] = source
    return verified


def _manifest_rows(path: Path) -> dict[str, dict[str, str]]:
    try:
        stream = path.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise Runner5JError(f"manifest missing: {path}") from error
    with stream:
        reader = csv.DictReader(stream)
        required = {
            "pair_id",
            "cover",
            "secret",
            "cover_sha256",
            "secret_sha256",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise Runner5JError(f"manifest lacks runtime fields: {path}")
        rows: dict[str, dict[str, str]] = {}
        for line, raw in enumerate(reader, start=2):
            pair_id = (raw.get("pair_id") or "").strip()
            if not SAFE_PAIR_ID.fullmatch(pair_id) or pair_id in rows:
                raise Runner5JError(
                    f"manifest {path} line {line} has invalid or duplicate pair_id"
                )
            row = {key: (value or "").strip() for key, value in raw.items()}
            _require_hash(row["cover_sha256"], field=f"{pair_id}.cover_sha256")
            _require_hash(row["secret_sha256"], field=f"{pair_id}.secret_sha256")
            rows[pair_id] = row
    return rows


def _resolve_manifest_file(manifest: Path, declared: str, *, role: str) -> Path:
    if not declared:
        raise Runner5JError(f"empty {role} path in {manifest}")
    candidate = Path(declared).expanduser()
    if not candidate.is_absolute():
        candidate = manifest.parent / candidate
    resolved = candidate.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise Runner5JError(f"{role} is not a regular file: {resolved}")
    return resolved


def resolve_pair_inputs(
    plan: Mapping[str, Any],
    *,
    repository_root: str | Path,
) -> dict[str, dict[str, str]]:
    """Resolve only plan-declared pair IDs and verify every input hash."""

    root = Path(repository_root).resolve()
    main_manifest = root / CREATED_FROM_PATHS["main_manifest_sha256"]
    sweep_manifest = root / CREATED_FROM_PATHS["sweep_manifest_sha256"]
    main_rows = _manifest_rows(main_manifest)
    sweep_rows = _manifest_rows(sweep_manifest)
    for pair_id, row in sweep_rows.items():
        main = main_rows.get(pair_id)
        if main is None or (
            main["cover_sha256"], main["secret_sha256"]
        ) != (row["cover_sha256"], row["secret_sha256"]):
            raise Runner5JError(
                f"sweep pair {pair_id} is not an exact-byte subset of main"
            )

    resolved: dict[str, dict[str, str]] = {}
    checked_files: dict[tuple[str, str], str] = {}
    for task in plan["embeddings"]:
        pair_id = str(task["pair_id"])
        row = main_rows.get(pair_id)
        if row is None:
            raise Runner5JError(f"plan pair is absent from main manifest: {pair_id}")
        if task["component"] in {"payload_sweep", "psnr_sweep"} and pair_id not in sweep_rows:
            raise Runner5JError(f"sweep task uses non-sweep pair: {pair_id}")
        if (
            task["cover_sha256"] != row["cover_sha256"]
            or task["secret_sha256"] != row["secret_sha256"]
        ):
            raise Runner5JError(f"plan/manifest hash mismatch for pair {pair_id}")
        if pair_id in resolved:
            continue
        cover = _resolve_manifest_file(main_manifest, row["cover"], role="cover")
        secret = _resolve_manifest_file(main_manifest, row["secret"], role="secret")
        for role, path in (("cover", cover), ("secret", secret)):
            cache_key = (str(path), role)
            actual = checked_files.get(cache_key)
            if actual is None:
                actual = sha256_file(path)
                checked_files[cache_key] = actual
            expected = row[f"{role}_sha256"]
            if actual != expected:
                raise Runner5JError(
                    f"{role} SHA-256 mismatch for {pair_id}: {actual} != {expected}"
                )
        resolved[pair_id] = {
            "pair_id": pair_id,
            "cover": str(cover),
            "secret": str(secret),
            "cover_sha256": row["cover_sha256"],
            "secret_sha256": row["secret_sha256"],
        }
    return resolved


def validate_science_ready_report(path: str | Path) -> dict[str, Any]:
    report = load_json_object(path)
    if report.get("protocol_id") != PROTOCOL_ID:
        raise Runner5JError("input-readiness report protocol mismatch")
    if report.get("valid_scaffolding") is not True:
        raise Runner5JError("input-readiness scaffolding is invalid")
    if report.get("science_ready") is not True:
        blockers = report.get("blockers", [])
        raise Runner5JError(f"scientific execution is blocked: {blockers!r}")
    if report.get("errors") not in ([], None):
        raise Runner5JError("science-ready report still contains errors")
    return report


def _load_ledger_states(
    ledger_path: str | Path | None,
    *,
    run_id: str,
) -> dict[str, str]:
    if ledger_path is None:
        return {}
    ledger = load_json_object(ledger_path)
    if ledger.get("protocol_id") != PROTOCOL_ID:
        raise Runner5JError("backup ledger protocol mismatch")
    if ledger.get("run_id") != run_id:
        raise Runner5JError("backup ledger run_id mismatch")
    objects = ledger.get("objects")
    if not isinstance(objects, list):
        raise Runner5JError("backup ledger objects must be an array")
    states: dict[str, str] = {}
    for item in objects:
        if not isinstance(item, dict):
            raise Runner5JError("backup ledger object entry is invalid")
        object_id = str(item.get("object_id", ""))
        if object_id in states:
            raise Runner5JError(f"backup ledger duplicates object_id {object_id}")
        states[object_id] = str(item.get("state", ""))
    return states


def _attempt_failure_count(store: ContentStore, object_id: str) -> int:
    parent = store.attempt_parent(object_id)
    if not parent.is_dir():
        return 0
    return sum(
        (attempt / "FAILED.json").is_file()
        for attempt in parent.iterdir()
        if attempt.is_dir()
    )


def _scientific_status(object_path: Path, kind: str) -> str | None:
    filename = "embedding.json" if kind == "embedding" else "evaluation.json"
    candidate = object_path / filename
    if not candidate.is_file():
        return None
    try:
        payload = read_json(candidate)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    status = payload.get("status") if isinstance(payload, dict) else None
    return status if status in {"complete", "scientific_failure", "operational_failure"} else None


def reconstruct_status(
    plan: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Rebuild progress from immutable objects and verified remote state."""

    index = validate_execution_plan(plan)
    store = ContentStore(cache_dir)
    ledger_states = _load_ledger_states(ledger_path, run_id=index["run_id"])
    state_counts: Counter[str] = Counter()
    kind_counts: dict[str, Counter[str]] = {
        "embedding": Counter(),
        "evaluation": Counter(),
    }
    component_counts: dict[str, Counter[str]] = defaultdict(Counter)
    method_counts: dict[str, Counter[str]] = defaultdict(Counter)
    records: list[dict[str, Any]] = []

    task_groups: Sequence[tuple[str, Mapping[str, dict[str, Any]], str]] = (
        ("embedding", index["embedding_by_id"], "embedding_id"),
        ("evaluation", index["evaluation_by_id"], "evaluation_id"),
    )
    for kind, tasks, id_field in task_groups:
        for object_id, task in tasks.items():
            verification = store.verify(object_id, deep=True)
            backup_state = ledger_states.get(object_id)
            failure_attempts = _attempt_failure_count(store, object_id)
            scientific_status = (
                _scientific_status(verification.path, kind)
                if verification.valid
                else None
            )
            if verification.valid and backup_state == "committed_complete":
                state = "committed_complete"
            elif verification.valid:
                state = "backup_pending"
            elif failure_attempts:
                state = "operational_failure"
            else:
                state = "planned"
            state_counts[state] += 1
            kind_counts[kind][state] += 1
            component_counts[str(task["component"])][state] += 1
            method_counts[str(task["method"])][state] += 1
            records.append(
                {
                    "object_id": object_id,
                    "kind": kind,
                    "id_field": id_field,
                    "component": task["component"],
                    "pair_id": task["pair_id"],
                    "method": task["method"],
                    "state": state,
                    "local_valid": verification.valid,
                    "local_validation_reason": verification.reason,
                    "backup_state": backup_state,
                    "scientific_status": scientific_status,
                    "failed_attempts": failure_attempts,
                }
            )

    total = index["counts"]["total_embeddings"] + index["counts"]["total_evaluations"]
    committed = state_counts["committed_complete"]
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": index["run_id"],
        "plan_id": index["plan_id"],
        "recorded_at": utc_now(),
        "total_tasks": total,
        "committed_complete": committed,
        "progress_fraction": committed / total,
        "state_counts": dict(sorted(state_counts.items())),
        "kind_counts": {
            key: dict(sorted(value.items())) for key, value in kind_counts.items()
        },
        "component_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(component_counts.items())
        },
        "method_counts": {
            key: dict(sorted(value.items()))
            for key, value in sorted(method_counts.items())
        },
        "records": records,
    }


def prepare_run(
    plan_path: str | Path,
    *,
    repository_root: str | Path,
    science_ready_report: str | Path,
    output_root: str | Path,
    cache_dir: str | Path,
    ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate all gates and publish an immutable preflight directory."""

    source_plan = Path(plan_path).resolve()
    plan = load_json_object(source_plan)
    index = validate_execution_plan(plan)
    fingerprints = verify_created_from(plan, repository_root=repository_root)
    pairs = resolve_pair_inputs(plan, repository_root=repository_root)
    readiness = validate_science_ready_report(science_ready_report)
    status = reconstruct_status(plan, cache_dir=cache_dir, ledger_path=ledger_path)

    root = Path(output_root).resolve()
    run_dir = root / "runs" / index["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    frozen_plan_path = run_dir / "execution_plan.json"
    if frozen_plan_path.is_file():
        existing = load_json_object(frozen_plan_path)
        if existing != plan:
            raise Runner5JError("existing run directory contains a different plan")
    else:
        atomic_write_json(frozen_plan_path, plan)

    context = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": index["run_id"],
        "plan_id": index["plan_id"],
        "prepared_at": utc_now(),
        "plan_path": str(source_plan),
        "repository_root": str(Path(repository_root).resolve()),
        "output_root": str(root),
        "cache_dir": str(Path(cache_dir).resolve()),
        "ledger_path": None if ledger_path is None else str(Path(ledger_path).resolve()),
        "verified_fingerprints": fingerprints,
        "resolved_pair_count": len(pairs),
        "science_ready_report": readiness,
        "execution_backend": "not_yet_authorized",
        "execution_blocker": (
            "Numerical worker and approved B1/B2 adapter dispatch are not yet "
            "wired behind this preflight contract."
        ),
    }
    atomic_write_json(run_dir / "preflight.json", context)
    atomic_write_json(run_dir / "status.json", status)
    summary = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": index["run_id"],
        "plan_id": index["plan_id"],
        "status": "preflight_passed_execution_blocked",
        "counts": index["counts"],
        "resolved_pair_count": len(pairs),
        "committed_complete": status["committed_complete"],
        "total_tasks": status["total_tasks"],
        "run_dir": str(run_dir),
        "updated_at": utc_now(),
    }
    atomic_write_json(run_dir / "run_summary.json", summary)
    return summary
