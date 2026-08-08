"""Simple local-cache dispatcher for all seven FINAL-5J-v1 methods.

Execution is intentionally two-stage and local-only:

1. all embedding tasks;
2. all evaluation tasks whose embedding objects are locally valid.

The module reuses the repository's DurableTaskRunner, ContentStore, RunLock,
spawn-based ProcessPoolExecutor, state reconstruction, and single-threaded
BLAS/OpenMP worker environment. Remote backup is not part of scheduling and is
performed only once after the full study, analysis, and manuscript are done.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ctsteg.runtime import (
    ContentStore,
    DurableTask,
    DurableTaskRunner,
    RunLock,
    atomic_write_json,
    read_json,
    resolve_worker_count,
    utc_now,
)

from .runtime_5j import Runner5JError, validate_execution_plan
from .runtime_baseline_worker_5j import execute_baseline_task
from .runtime_tasks_5j import bind_evaluation_task
from .runtime_worker_5j import execute_internal_task


PROTOCOL_ID = "FINAL-5J-v1"
INTERNAL_METHODS = {"C0", "C1", "C2", "C3_NP", "C3"}
BASELINE_METHODS = {"B1", "B2"}


class Dispatch5JError(RuntimeError):
    """Raised when the local-only research dispatcher cannot proceed."""


def _dispatch_worker(
    durable_payload: Mapping[str, Any],
    cache_dir: str,
) -> Mapping[str, Any]:
    """Spawn-safe adapter from DurableTaskRunner to the seven-method workers."""

    payload = durable_payload.get("payload")
    if not isinstance(payload, Mapping):
        return {
            "status": "failed",
            "error_type": "Dispatch5JError",
            "error": "durable task payload is invalid",
        }
    kind = str(payload.get("kind", ""))
    task = payload.get("task")
    context = payload.get("context")
    if kind not in {"embedding", "evaluation"}:
        return {
            "status": "failed",
            "error_type": "Dispatch5JError",
            "error": f"invalid task kind: {kind!r}",
        }
    if not isinstance(task, Mapping) or not isinstance(context, Mapping):
        return {
            "status": "failed",
            "error_type": "Dispatch5JError",
            "error": "task or context is invalid",
        }
    method = str(task.get("method", ""))
    if method in INTERNAL_METHODS:
        return execute_internal_task(
            task,
            kind=kind,
            context=context,
            cache_dir=cache_dir,
        )
    if method in BASELINE_METHODS:
        return execute_baseline_task(
            task,
            kind=kind,
            context=context,
            cache_dir=cache_dir,
        )
    return {
        "status": "failed",
        "error_type": "Dispatch5JError",
        "error": f"unknown method: {method!r}",
    }


def _baseline_fingerprints(plan: Mapping[str, Any]) -> dict[str, str]:
    values: dict[str, set[str]] = {"B1": set(), "B2": set()}
    for raw in plan.get("embeddings", []):
        if not isinstance(raw, Mapping):
            continue
        method = str(raw.get("method", ""))
        if method in values:
            values[method].add(str(raw.get("method_fingerprint", "")))
    output: dict[str, str] = {}
    for method, fingerprints in values.items():
        if len(fingerprints) != 1 or "" in fingerprints:
            raise Dispatch5JError(
                f"plan has inconsistent {method} method fingerprints"
            )
        output[method] = next(iter(fingerprints))
    return output


def build_worker_context(
    plan: Mapping[str, Any],
    *,
    runtime_report: Mapping[str, Any],
    pair_inputs: Mapping[str, Mapping[str, str]],
    config_path: str | Path,
) -> dict[str, Any]:
    """Build one JSON-serializable immutable context shared by all tasks."""

    index = validate_execution_plan(plan)
    created_from = plan.get("created_from")
    if not isinstance(created_from, Mapping):
        raise Dispatch5JError("plan created_from is invalid")
    required_runtime = (
        "stability_profile",
        "stability_profile_sha256",
    )
    for field in required_runtime:
        if not isinstance(runtime_report.get(field), str) or not runtime_report[field]:
            raise Dispatch5JError(f"runtime report is missing {field}")
    return {
        "run_id": index["run_id"],
        "source_fingerprint": created_from["source_fingerprint"],
        "config_path": str(Path(config_path).resolve()),
        "base_config_sha256": created_from["config_sha256"],
        "stability_path": runtime_report["stability_profile"],
        "stability_sha256": runtime_report["stability_profile_sha256"],
        "runtime_binding_report": dict(runtime_report),
        "pair_inputs": {
            key: dict(value) for key, value in pair_inputs.items()
        },
        "baseline_method_fingerprints": _baseline_fingerprints(plan),
        "backup_policy": "final_only_after_run_completion",
    }


def _durable_task(
    task: Mapping[str, Any],
    *,
    kind: str,
    context: Mapping[str, Any],
) -> DurableTask:
    id_field = "embedding_id" if kind == "embedding" else "evaluation_id"
    object_id = str(task.get(id_field, ""))
    if not object_id:
        raise Dispatch5JError(f"{kind} task has no {id_field}")
    label = (
        f"{task.get('component')}:{task.get('pair_id')}:"
        f"{task.get('method')}"
    )
    if kind == "evaluation":
        label += f":{task.get('channel_instance_id')}"
    return DurableTask(
        object_id=object_id,
        kind=kind,
        label=label,
        payload={
            "kind": kind,
            "task": dict(task),
            "context": dict(context),
        },
    )


def build_embedding_tasks(
    plan: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
) -> list[DurableTask]:
    index = validate_execution_plan(plan)
    return [
        _durable_task(task, kind="embedding", context=context)
        for task in index["embedding_by_id"].values()
    ]


def build_evaluation_tasks(
    plan: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
) -> list[DurableTask]:
    index = validate_execution_plan(plan)
    output: list[DurableTask] = []
    for evaluation in index["evaluation_by_id"].values():
        embedding = index["embedding_by_id"].get(evaluation["embedding_id"])
        if embedding is None:
            raise Dispatch5JError("evaluation references unknown embedding")
        bound = bind_evaluation_task(evaluation, embedding)
        output.append(
            _durable_task(bound, kind="evaluation", context=context)
        )
    return output


def _stage_failed(summary: Mapping[str, Any]) -> bool:
    return int(summary.get("failed", 0)) > 0


def _verify_embedding_acceptance(
    tasks: Sequence[DurableTask],
    *,
    cache_dir: str | Path,
) -> dict[str, int]:
    """Require all embeddings to be locally valid and clean-complete."""

    store = ContentStore(cache_dir)
    counts = {"complete": 0, "scientific_failure": 0, "invalid": 0}
    failures: list[str] = []
    for task in tasks:
        verification = store.verify(task.object_id, deep=True)
        if not verification.valid:
            counts["invalid"] += 1
            failures.append(
                f"{task.label}: invalid object ({verification.reason})"
            )
            continue
        try:
            record = read_json(verification.path / "embedding.json")
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            counts["invalid"] += 1
            failures.append(f"{task.label}: unreadable embedding.json: {error}")
            continue
        status = str(record.get("status", ""))
        if status == "complete":
            counts["complete"] += 1
        else:
            counts["scientific_failure"] += 1
            failures.append(f"{task.label}: clean embedding status={status}")
    if failures:
        preview = "; ".join(failures[:10])
        raise Dispatch5JError(
            "embedding acceptance failed; evaluations were not started: "
            f"{preview}"
        )
    return counts


def run_local_study(
    plan: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    cache_dir: str | Path,
    run_dir: str | Path,
    workers: int = 16,
    reserve_cpus: int = 4,
    reserve_memory_gib: float = 10.0,
    worker_memory_gib: float = 3.0,
    hard_cap: int = 28,
    stop_after: str | None = None,
) -> dict[str, Any]:
    """Execute embeddings then evaluations, resuming solely from local cache."""

    if stop_after not in {None, "embeddings"}:
        raise Dispatch5JError("stop_after must be omitted or 'embeddings'")
    index = validate_execution_plan(plan)
    output = Path(run_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = Path(cache_dir).resolve()
    embedding_tasks = build_embedding_tasks(plan, context=context)
    evaluation_tasks = build_evaluation_tasks(plan, context=context)
    largest_stage = max(len(embedding_tasks), len(evaluation_tasks))
    resolved_workers, worker_facts = resolve_worker_count(
        workers,
        job_count=largest_stage,
        reserve_cpus=reserve_cpus,
        reserve_memory_gib=reserve_memory_gib,
        worker_memory_gib=worker_memory_gib,
        hard_cap=hard_cap,
    )

    frozen = output / "execution_plan.json"
    if frozen.is_file():
        existing = read_json(frozen)
        if existing != plan:
            raise Dispatch5JError("run directory contains a different plan")
    else:
        atomic_write_json(frozen, plan)
    atomic_write_json(
        output / "dispatcher_config.json",
        {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "run_id": index["run_id"],
            "plan_id": index["plan_id"],
            "created_at": utc_now(),
            "backup_policy": "final_only_after_run_completion",
            "workers": worker_facts,
            "stage_order": ["embeddings", "evaluations"],
        },
    )

    runner = DurableTaskRunner(
        cache_dir=cache,
        run_dir=output,
        workers=resolved_workers,
    )
    with RunLock(output):
        embedding_summary = runner.run(
            embedding_tasks,
            stage="embeddings",
            worker=_dispatch_worker,
        )
        if _stage_failed(embedding_summary):
            raise Dispatch5JError(
                f"embedding stage has {embedding_summary['failed']} failed tasks"
            )
        embedding_acceptance = _verify_embedding_acceptance(
            embedding_tasks,
            cache_dir=cache,
        )
        if stop_after == "embeddings":
            final = {
                "schema_version": 1,
                "protocol_id": PROTOCOL_ID,
                "run_id": index["run_id"],
                "status": "embeddings_complete_local",
                "workers": resolved_workers,
                "embedding_stage": embedding_summary,
                "embedding_acceptance": embedding_acceptance,
                "evaluation_stage": None,
                "backup_policy": "final_only_after_run_completion",
                "updated_at": utc_now(),
            }
            atomic_write_json(output / "dispatch_summary.json", final)
            return final

        evaluation_summary = runner.run(
            evaluation_tasks,
            stage="evaluations",
            worker=_dispatch_worker,
        )
        final_status = (
            "run_complete_local"
            if not _stage_failed(evaluation_summary)
            else "run_incomplete_operational_failures"
        )
        final = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "run_id": index["run_id"],
            "status": final_status,
            "workers": resolved_workers,
            "worker_facts": worker_facts,
            "embedding_stage": embedding_summary,
            "embedding_acceptance": embedding_acceptance,
            "evaluation_stage": evaluation_summary,
            "backup_policy": "final_only_after_run_completion",
            "updated_at": utc_now(),
        }
        atomic_write_json(output / "dispatch_summary.json", final)
        return final
