"""Monitored multi-process worker trials for FINAL-5J host tuning."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Mapping, Sequence

from ctsteg.runtime import ContentStore, DurableTask, DurableTaskRunner, atomic_write_json

from .runtime_5j import Runner5JError
from .runtime_tasks_5j import bind_evaluation_task
from .runtime_worker_5j import execute_internal_task
from .worker_tuning_5j import GIB, PROTOCOL_ID, canonical_sha256


class WorkerTrialError(Runner5JError):
    """Invalid benchmark selection or host measurement."""


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkerTrialError(f"{label} must be an object")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise WorkerTrialError(f"{label} must be a non-empty array")
    output = [str(item) for item in value]
    if any(not item for item in output) or len(output) != len(set(output)):
        raise WorkerTrialError(f"{label} contains empty or duplicate IDs")
    return output


def validate_selection(
    payload: Mapping[str, Any],
    *,
    index: Mapping[str, Any],
    minimum_embeddings: int = 32,
    minimum_evaluations: int = 128,
) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise WorkerTrialError("worker trial selection schema mismatch")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise WorkerTrialError("worker trial selection protocol mismatch")
    if payload.get("status") != "frozen_before_trial":
        raise WorkerTrialError("worker trial selection is not frozen")
    material = dict(payload)
    declared = material.pop("selection_sha256", None)
    computed = canonical_sha256(material)
    if declared != computed:
        raise WorkerTrialError("worker trial selection SHA-256 mismatch")

    embedding_ids = _string_list(payload.get("embedding_ids"), "embedding_ids")
    evaluation_ids = _string_list(payload.get("evaluation_ids"), "evaluation_ids")
    if len(embedding_ids) < minimum_embeddings:
        raise WorkerTrialError(
            f"worker trial requires at least {minimum_embeddings} embeddings"
        )
    if len(evaluation_ids) < minimum_evaluations:
        raise WorkerTrialError(
            f"worker trial requires at least {minimum_evaluations} evaluations"
        )

    embedding_by_id = _mapping(index.get("embedding_by_id"), "embedding index")
    evaluation_by_id = _mapping(index.get("evaluation_by_id"), "evaluation index")
    embeddings: list[dict[str, Any]] = []
    methods: set[str] = set()
    fractions: set[float] = set()
    for object_id in embedding_ids:
        raw = embedding_by_id.get(object_id)
        if not isinstance(raw, Mapping):
            raise WorkerTrialError(f"unknown embedding ID in trial: {object_id}")
        method = str(raw.get("method", ""))
        if method in {"B1", "B2"}:
            raise WorkerTrialError("worker trial cannot include unapproved B1/B2 workers")
        methods.add(method)
        fractions.add(float(raw.get("payload_fraction", 0.0)))
        embeddings.append(dict(raw))
    if methods != {"C0", "C1", "C2", "C3_NP", "C3"}:
        raise WorkerTrialError(
            "worker trial must represent all five internal methods exactly"
        )
    if len(fractions) < 2:
        raise WorkerTrialError("worker trial must include at least two payload fractions")

    selected_embedding_ids = set(embedding_ids)
    evaluations: list[dict[str, Any]] = []
    families: set[str] = set()
    for object_id in evaluation_ids:
        raw = evaluation_by_id.get(object_id)
        if not isinstance(raw, Mapping):
            raise WorkerTrialError(f"unknown evaluation ID in trial: {object_id}")
        embedding_id = str(raw.get("embedding_id", ""))
        if embedding_id not in selected_embedding_ids:
            raise WorkerTrialError(
                f"evaluation {object_id} depends on an unselected embedding"
            )
        embedding = embedding_by_id[embedding_id]
        assert isinstance(embedding, Mapping)
        bound = bind_evaluation_task(raw, embedding)
        families.add(str(bound.get("family", "")))
        evaluations.append(bound)
    required = {"clean", "jpeg", "gaussian", "salt_pepper"}
    if families != required:
        raise WorkerTrialError(
            f"worker trial attack families are {sorted(families)}; expected {sorted(required)}"
        )
    return {
        "selection_sha256": computed,
        "embedding_ids": embedding_ids,
        "evaluation_ids": evaluation_ids,
        "embeddings": embeddings,
        "evaluations": evaluations,
    }


def execute_trial_envelope(envelope: Mapping[str, Any], cache_dir: str) -> Mapping[str, Any]:
    """Picklable DurableTaskRunner adapter for one internal worker task."""

    payload = _mapping(envelope.get("payload"), "durable task payload")
    kind = str(payload.get("kind", ""))
    task = _mapping(payload.get("task"), "worker task")
    context = _mapping(payload.get("context"), "worker context")
    return execute_internal_task(
        task,
        kind=kind,
        context=context,
        cache_dir=cache_dir,
    )


def _read_key_values(path: Path) -> dict[str, int]:
    output: dict[str, int] = {}
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError:
        return output
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0].rstrip(":")
        try:
            output[key] = int(parts[1])
        except ValueError:
            continue
    return output


def _cpu_counters() -> tuple[int, int, int] | None:
    try:
        line = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0]
    except (OSError, IndexError):
        return None
    parts = line.split()
    if not parts or parts[0] != "cpu":
        return None
    try:
        values = [int(value) for value in parts[1:]]
    except ValueError:
        return None
    if len(values) < 5:
        return None
    total = sum(values)
    idle = values[3]
    iowait = values[4]
    return total, idle, iowait


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return float(ordered[index])


@dataclass
class HostSamples:
    cpu_busy: list[float]
    iowait: list[float]
    available_memory: list[int]
    swap_used: list[int]
    load_one: list[float]
    disk_free: list[int]
    initial_vmstat: dict[str, int]
    final_vmstat: dict[str, int]


class HostSampler:
    def __init__(self, *, path: Path, interval_seconds: float = 2.0):
        if interval_seconds <= 0:
            raise ValueError("sampling interval must be positive")
        self.path = path.resolve()
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.samples = HostSamples([], [], [], [], [], [], {}, {})
        self._previous_cpu: tuple[int, int, int] | None = None

    def _sample(self) -> None:
        current = _cpu_counters()
        if current is not None and self._previous_cpu is not None:
            total_delta = current[0] - self._previous_cpu[0]
            idle_delta = current[1] - self._previous_cpu[1]
            iowait_delta = current[2] - self._previous_cpu[2]
            if total_delta > 0:
                busy = 100.0 * max(0, total_delta - idle_delta - iowait_delta) / total_delta
                wait = 100.0 * max(0, iowait_delta) / total_delta
                self.samples.cpu_busy.append(busy)
                self.samples.iowait.append(wait)
        self._previous_cpu = current

        memory = _read_key_values(Path("/proc/meminfo"))
        if memory:
            available = memory.get("MemAvailable", memory.get("MemFree", 0)) * 1024
            swap_used = max(
                0,
                (memory.get("SwapTotal", 0) - memory.get("SwapFree", 0)) * 1024,
            )
            self.samples.available_memory.append(available)
            self.samples.swap_used.append(swap_used)
        try:
            self.samples.load_one.append(float(os.getloadavg()[0]))
        except (AttributeError, OSError):
            pass
        try:
            self.samples.disk_free.append(shutil.disk_usage(self.path).free)
        except OSError:
            pass

    def _run(self) -> None:
        while not self.stop_event.is_set():
            self._sample()
            self.stop_event.wait(self.interval_seconds)
        self._sample()

    def start(self) -> None:
        self.samples.initial_vmstat = _read_key_values(Path("/proc/vmstat"))
        self.thread = threading.Thread(target=self._run, name="5j-host-sampler", daemon=True)
        self.thread.start()

    def stop(self) -> HostSamples:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=max(5.0, self.interval_seconds * 3))
        self.samples.final_vmstat = _read_key_values(Path("/proc/vmstat"))
        return self.samples


def _task(kind: str, raw: Mapping[str, Any], context: Mapping[str, Any]) -> DurableTask:
    object_id = str(raw["embedding_id"] if kind == "embedding" else raw["evaluation_id"])
    return DurableTask(
        object_id=object_id,
        kind=kind,
        label=f"{kind}:{raw.get('pair_id')}:{raw.get('method')}",
        payload={"kind": kind, "task": dict(raw), "context": dict(context)},
    )


def _rss_values(cache_dir: Path, selection: Mapping[str, Any]) -> list[int]:
    store = ContentStore(cache_dir)
    output: list[int] = []
    for kind, identifiers, filename in (
        ("embedding", selection["embedding_ids"], "embedding.json"),
        ("evaluation", selection["evaluation_ids"], "evaluation.json"),
    ):
        del kind
        for object_id in identifiers:
            verification = store.verify(str(object_id), deep=True)
            if not verification.valid:
                continue
            try:
                record = json.loads(
                    (verification.path / filename).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            timing = record.get("timing")
            if isinstance(timing, Mapping):
                value = timing.get("peak_rss_bytes")
                if isinstance(value, int) and value > 0:
                    output.append(value)
    return output


def _vmstat_delta(samples: HostSamples, key: str) -> int:
    return max(
        0,
        int(samples.final_vmstat.get(key, 0))
        - int(samples.initial_vmstat.get(key, 0)),
    )


def run_worker_trial(
    *,
    index: Mapping[str, Any],
    selection_payload: Mapping[str, Any],
    context: Mapping[str, Any],
    cache_dir: str | Path,
    run_dir: str | Path,
    workers: int,
    sampling_interval_seconds: float = 2.0,
) -> dict[str, Any]:
    if workers not in {8, 12, 16, 20, 24, 28}:
        raise WorkerTrialError("workers must be one of 8, 12, 16, 20, 24, 28")
    selection = validate_selection(selection_payload, index=index)
    cache = Path(cache_dir).resolve()
    run = Path(run_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    run.mkdir(parents=True, exist_ok=True)

    store = ContentStore(cache)
    preexisting = [
        object_id
        for object_id in selection["embedding_ids"] + selection["evaluation_ids"]
        if store.verify(str(object_id), deep=True).valid
    ]
    if preexisting:
        raise WorkerTrialError(
            "worker trial cache contains selected completed objects; use a fresh cache"
        )

    runner = DurableTaskRunner(cache_dir=cache, run_dir=run, workers=workers)
    embedding_tasks = [
        _task("embedding", item, context) for item in selection["embeddings"]
    ]
    evaluation_tasks = [
        _task("evaluation", item, context) for item in selection["evaluations"]
    ]

    sampler = HostSampler(path=cache, interval_seconds=sampling_interval_seconds)
    started = time.perf_counter()
    sampler.start()
    try:
        embedding_result = runner.run(
            embedding_tasks,
            stage="worker_trial_embeddings",
            worker=execute_trial_envelope,
        )
        if int(embedding_result["failed"]) > 0:
            evaluation_result = {
                "stage": "worker_trial_evaluations",
                "task_count": len(evaluation_tasks),
                "cached": 0,
                "completed": 0,
                "failed": len(evaluation_tasks),
                "blocked": True,
            }
        else:
            evaluation_result = runner.run(
                evaluation_tasks,
                stage="worker_trial_evaluations",
                worker=execute_trial_envelope,
            )
    finally:
        samples = sampler.stop()
    wall_seconds = time.perf_counter() - started

    completed = int(embedding_result["completed"]) + int(evaluation_result["completed"])
    operational_failures = int(embedding_result["failed"]) + int(
        evaluation_result["failed"]
    )
    planned = len(embedding_tasks) + len(evaluation_tasks)
    rss = _rss_values(cache, selection)
    page_size = int(os.sysconf("SC_PAGE_SIZE")) if hasattr(os, "sysconf") else 4096
    swap_pages = _vmstat_delta(samples, "pswpin") + _vmstat_delta(samples, "pswpout")
    oom_events = _vmstat_delta(samples, "oom_kill")

    material = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": "complete",
        "workers": workers,
        "task_selection_sha256": selection["selection_sha256"],
        "tasks": {
            "planned": planned,
            "completed": completed,
            "operational_failures": operational_failures,
            "oom_events": oom_events,
            "embedding": {
                "planned": len(embedding_tasks),
                "completed": int(embedding_result["completed"]),
                "failed": int(embedding_result["failed"]),
            },
            "evaluation": {
                "planned": len(evaluation_tasks),
                "completed": int(evaluation_result["completed"]),
                "failed": int(evaluation_result["failed"]),
            },
        },
        "timing": {
            "wall_seconds": wall_seconds,
            "combined_tasks_per_hour": 3600.0 * completed / wall_seconds,
            "embedding_tasks_per_hour": (
                3600.0 * int(embedding_result["completed"]) / wall_seconds
            ),
            "evaluation_tasks_per_hour": (
                3600.0 * int(evaluation_result["completed"]) / wall_seconds
            ),
        },
        "cpu": {
            "mean_busy_percent": (
                sum(samples.cpu_busy) / len(samples.cpu_busy)
                if samples.cpu_busy
                else 0.0
            ),
            "p95_busy_percent": _percentile(samples.cpu_busy, 0.95),
            "mean_iowait_percent": (
                sum(samples.iowait) / len(samples.iowait)
                if samples.iowait
                else 0.0
            ),
            "p95_iowait_percent": _percentile(samples.iowait, 0.95),
            "maximum_load_one": max(samples.load_one, default=0.0),
        },
        "memory": {
            "minimum_available_bytes": min(samples.available_memory, default=0),
            "p95_worker_rss_bytes": int(_percentile([float(value) for value in rss], 0.95)),
            "max_worker_rss_bytes": max(rss, default=1),
            "rss_observation_count": len(rss),
        },
        "swap": {
            "io_bytes": swap_pages * page_size,
            "maximum_used_bytes": max(samples.swap_used, default=0),
        },
        "storage": {
            "minimum_free_bytes": min(samples.disk_free, default=0),
            "cache_dir": str(cache),
            "run_dir": str(run),
        },
        "host": {
            "logical_cpus": os.cpu_count() or 1,
            "sampling_interval_seconds": sampling_interval_seconds,
        },
    }
    material["trial_sha256"] = canonical_sha256(material)
    atomic_write_json(run / "worker_trial.json", material)
    return material
