"""Deterministic worker-count decisions for the FINAL-5J performance gate."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


PROTOCOL_ID = "FINAL-5J-v1"
GIB = 1024**3
_HEX = set("0123456789abcdef")


class WorkerTuningError(ValueError):
    """Invalid or contradictory worker-tuning evidence."""


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in _HEX for character in value)
    )


def _number(mapping: Mapping[str, Any], key: str, *, minimum: float = 0.0) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WorkerTuningError(f"{key} must be numeric")
    result = float(value)
    if result < minimum:
        raise WorkerTuningError(f"{key} must be at least {minimum}")
    return result


def _integer(mapping: Mapping[str, Any], key: str, *, minimum: int = 0) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkerTuningError(f"{key} must be an integer")
    if value < minimum:
        raise WorkerTuningError(f"{key} must be at least {minimum}")
    return value


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Trial:
    workers: int
    wall_seconds: float
    combined_tasks_per_hour: float
    operational_failures: int
    oom_events: int
    swap_io_bytes: int
    mean_cpu_busy_percent: float
    p95_iowait_percent: float
    maximum_load_one: float
    minimum_available_memory_bytes: int
    p95_worker_rss_bytes: int
    max_worker_rss_bytes: int
    minimum_free_storage_bytes: int
    task_selection_sha256: str
    trial_sha256: str

    @property
    def minimum_available_memory_gib(self) -> float:
        return self.minimum_available_memory_bytes / GIB

    @property
    def p95_worker_rss_gib(self) -> float:
        return self.p95_worker_rss_bytes / GIB

    @property
    def minimum_free_storage_gib(self) -> float:
        return self.minimum_free_storage_bytes / GIB


def load_config(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkerTuningError("worker tuning config root must be an object")
    if payload.get("schema_version") != 1:
        raise WorkerTuningError("worker tuning config schema mismatch")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise WorkerTuningError("worker tuning config protocol mismatch")
    if payload.get("status") != "locked_before_performance_results":
        raise WorkerTuningError("worker tuning thresholds are not frozen")
    if payload.get("profile_id") != "ferdowsi-32c64g-100gb-v1":
        raise WorkerTuningError("unexpected target-host profile")
    if payload.get("initial_workers") != 16:
        raise WorkerTuningError("the first measured trial must use 16 workers")
    if payload.get("maximum_workers") != 29:
        raise WorkerTuningError("the 32-core host profile must cap at 29 workers")
    if payload.get("candidate_order") != [16, 12, 8, 4, 20, 24, 27, 29]:
        raise WorkerTuningError("worker candidate order differs from the frozen 32-core profile")
    if payload.get("fallback_workers") != [12, 8, 4]:
        raise WorkerTuningError("worker fallback ladder is invalid")
    if payload.get("scale_up_workers") != [20, 24, 27, 29]:
        raise WorkerTuningError("worker scale-up ladder is invalid")
    target = payload.get("target_host")
    if not isinstance(target, Mapping):
        raise WorkerTuningError("target_host must be an object")
    if target.get("logical_cpus") != 32 or target.get("memory_gib") != 64:
        raise WorkerTuningError("target_host must describe the 32-logical-CPU/64-GiB server")
    if target.get("storage_gb_decimal") != 100 or target.get("reserved_cpus") != 3:
        raise WorkerTuningError("target_host storage/CPU reservation differs from the frozen profile")
    if int(payload["maximum_workers"]) != int(target["logical_cpus"]) - int(target["reserved_cpus"]):
        raise WorkerTuningError("maximum_workers must preserve exactly three logical CPUs")
    scale = payload.get("scale_up_thresholds")
    if not isinstance(scale, Mapping):
        raise WorkerTuningError("scale_up_thresholds must be an object")
    if "minimum_mean_cpu_busy_percent" in scale:
        raise WorkerTuningError("fixed CPU-busy percentage gates are forbidden for this profile")
    return payload


def parse_trial(payload: Mapping[str, Any]) -> Trial:
    if payload.get("schema_version") != 1:
        raise WorkerTuningError("trial schema mismatch")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise WorkerTuningError("trial protocol mismatch")
    if payload.get("status") != "complete":
        raise WorkerTuningError("incomplete trial cannot guide worker selection")
    task_hash = payload.get("task_selection_sha256")
    if not _is_sha256(task_hash):
        raise WorkerTuningError("trial task-selection hash is invalid")

    tasks = payload.get("tasks")
    timing = payload.get("timing")
    cpu = payload.get("cpu")
    memory = payload.get("memory")
    swap = payload.get("swap")
    storage = payload.get("storage")
    if not all(isinstance(item, Mapping) for item in (tasks, timing, cpu, memory, swap, storage)):
        raise WorkerTuningError("trial metric sections are missing")
    assert isinstance(tasks, Mapping)
    assert isinstance(timing, Mapping)
    assert isinstance(cpu, Mapping)
    assert isinstance(memory, Mapping)
    assert isinstance(swap, Mapping)
    assert isinstance(storage, Mapping)

    workers = _integer(payload, "workers", minimum=1)
    allowed = {4, 8, 12, 16, 20, 24, 27, 29}
    if workers not in allowed:
        raise WorkerTuningError(f"unsupported worker candidate: {workers}")
    planned = _integer(tasks, "planned", minimum=1)
    completed = _integer(tasks, "completed", minimum=0)
    if completed > planned:
        raise WorkerTuningError("completed tasks exceed planned tasks")

    material = dict(payload)
    declared_hash = material.pop("trial_sha256", None)
    computed_hash = canonical_sha256(material)
    if declared_hash is not None and declared_hash != computed_hash:
        raise WorkerTuningError("trial SHA-256 does not match its contents")

    maximum_load_one = cpu.get("maximum_load_one", 0.0)
    if isinstance(maximum_load_one, bool) or not isinstance(maximum_load_one, (int, float)):
        raise WorkerTuningError("maximum_load_one must be numeric")

    return Trial(
        workers=workers,
        wall_seconds=_number(timing, "wall_seconds", minimum=0.001),
        combined_tasks_per_hour=_number(timing, "combined_tasks_per_hour", minimum=0.0),
        operational_failures=_integer(tasks, "operational_failures", minimum=0),
        oom_events=_integer(tasks, "oom_events", minimum=0),
        swap_io_bytes=_integer(swap, "io_bytes", minimum=0),
        mean_cpu_busy_percent=_number(cpu, "mean_busy_percent", minimum=0.0),
        p95_iowait_percent=_number(cpu, "p95_iowait_percent", minimum=0.0),
        maximum_load_one=float(maximum_load_one),
        minimum_available_memory_bytes=_integer(memory, "minimum_available_bytes", minimum=0),
        p95_worker_rss_bytes=_integer(memory, "p95_worker_rss_bytes", minimum=1),
        max_worker_rss_bytes=_integer(memory, "max_worker_rss_bytes", minimum=1),
        minimum_free_storage_bytes=_integer(storage, "minimum_free_bytes", minimum=0),
        task_selection_sha256=str(task_hash),
        trial_sha256=computed_hash,
    )


def load_trials(paths: Sequence[str | Path]) -> list[Trial]:
    trials: list[Trial] = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise WorkerTuningError(f"trial root must be an object: {path}")
        trials.append(parse_trial(payload))
    if not trials:
        return []
    selection_hashes = {trial.task_selection_sha256 for trial in trials}
    if len(selection_hashes) != 1:
        raise WorkerTuningError("worker trials use different task selections")
    counts: dict[int, int] = {}
    for trial in trials:
        counts[trial.workers] = counts.get(trial.workers, 0) + 1
    if any(count > 2 for count in counts.values()):
        raise WorkerTuningError("a worker candidate has more than two measured trials")
    return trials


def _threshold(config: Mapping[str, Any], section: str, key: str) -> float:
    values = config.get(section)
    if not isinstance(values, Mapping):
        raise WorkerTuningError(f"config section {section} is missing")
    return _number(values, key, minimum=0.0)


def unsafe_reasons(trial: Trial, config: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if trial.operational_failures > int(_threshold(config, "rejection_thresholds", "maximum_operational_failures")):
        reasons.append("operational_failures")
    if trial.oom_events > int(_threshold(config, "rejection_thresholds", "maximum_oom_events")):
        reasons.append("oom_events")
    if trial.swap_io_bytes > int(_threshold(config, "rejection_thresholds", "maximum_swap_io_bytes")):
        reasons.append("swap_io")
    if trial.minimum_available_memory_gib < _threshold(config, "rejection_thresholds", "minimum_available_memory_gib"):
        reasons.append("memory_floor")
    if trial.minimum_free_storage_gib < _threshold(config, "rejection_thresholds", "minimum_free_storage_gib"):
        reasons.append("storage_floor")
    if trial.p95_iowait_percent > _threshold(config, "rejection_thresholds", "maximum_sustained_iowait_percent"):
        reasons.append("iowait")
    return reasons


def _mean_trial(trials: Sequence[Trial], workers: int) -> Trial | None:
    selected = [trial for trial in trials if trial.workers == workers]
    if not selected:
        return None
    if len(selected) == 1:
        return selected[0]
    first, second = selected
    return Trial(
        workers=workers,
        wall_seconds=(first.wall_seconds + second.wall_seconds) / 2,
        combined_tasks_per_hour=(first.combined_tasks_per_hour + second.combined_tasks_per_hour) / 2,
        operational_failures=first.operational_failures + second.operational_failures,
        oom_events=first.oom_events + second.oom_events,
        swap_io_bytes=first.swap_io_bytes + second.swap_io_bytes,
        mean_cpu_busy_percent=(first.mean_cpu_busy_percent + second.mean_cpu_busy_percent) / 2,
        p95_iowait_percent=max(first.p95_iowait_percent, second.p95_iowait_percent),
        maximum_load_one=max(first.maximum_load_one, second.maximum_load_one),
        minimum_available_memory_bytes=min(first.minimum_available_memory_bytes, second.minimum_available_memory_bytes),
        p95_worker_rss_bytes=max(first.p95_worker_rss_bytes, second.p95_worker_rss_bytes),
        max_worker_rss_bytes=max(first.max_worker_rss_bytes, second.max_worker_rss_bytes),
        minimum_free_storage_bytes=min(first.minimum_free_storage_bytes, second.minimum_free_storage_bytes),
        task_selection_sha256=first.task_selection_sha256,
        trial_sha256=canonical_sha256([first.trial_sha256, second.trial_sha256]),
    )


def _projected_headroom_gib(current: Trial, candidate_workers: int) -> float:
    additional = max(0, candidate_workers - current.workers)
    projected_extra = additional * current.p95_worker_rss_gib * 1.20
    return current.minimum_available_memory_gib - projected_extra


def _marginal_efficiency(current: Trial, previous: Trial, baseline: Trial) -> float:
    added_workers = current.workers - previous.workers
    if added_workers <= 0 or baseline.workers <= 0 or baseline.combined_tasks_per_hour <= 0:
        return 0.0
    marginal_throughput = (current.combined_tasks_per_hour - previous.combined_tasks_per_hour) / added_workers
    baseline_per_worker = baseline.combined_tasks_per_hour / baseline.workers
    if baseline_per_worker <= 0:
        return 0.0
    return marginal_throughput / baseline_per_worker


def _diagnostics(trial: Trial, config: Mapping[str, Any]) -> dict[str, float]:
    target = config["target_host"]
    logical_cpus = int(target["logical_cpus"])
    busy_equivalents = logical_cpus * trial.mean_cpu_busy_percent / 100.0
    return {
        "mean_busy_cpu_equivalents": busy_equivalents,
        "maximum_load_one": trial.maximum_load_one,
        "configured_reserved_cpus": float(target["reserved_cpus"]),
    }


def _best_stable(trials: Sequence[Trial], config: Mapping[str, Any]) -> Trial | None:
    candidates: list[Trial] = []
    for workers in config["candidate_order"]:
        trial = _mean_trial(trials, int(workers))
        if trial is not None and not unsafe_reasons(trial, config):
            candidates.append(trial)
    return max(candidates, key=lambda item: item.combined_tasks_per_hour, default=None)


def _next_fallback(config: Mapping[str, Any], current_workers: int, measured: set[int]) -> int | None:
    ladder = [int(value) for value in config["fallback_workers"]]
    if current_workers == int(config["initial_workers"]):
        candidates = ladder
    elif current_workers in ladder:
        candidates = ladder[ladder.index(current_workers) + 1 :]
    else:
        candidates = []
    return next((workers for workers in candidates if workers not in measured), None)


def _scale_ladder(config: Mapping[str, Any]) -> list[int]:
    return [int(config["initial_workers"]), *[int(value) for value in config["scale_up_workers"]]]


def recommend(config: Mapping[str, Any], trials: Sequence[Trial]) -> dict[str, Any]:
    """Return the next measured trial or a selected stable worker count for 32c64g."""

    initial = int(config["initial_workers"])
    measured = {trial.workers for trial in trials}
    if not trials:
        return {
            "action": "test",
            "workers": initial,
            "reason": "first_measured_trial",
            "selected_workers": None,
        }
    if initial not in measured:
        raise WorkerTuningError(f"the first measured trial must be {initial} workers")

    latest = trials[-1]
    current = _mean_trial(trials, latest.workers)
    assert current is not None
    unsafe = unsafe_reasons(current, config)
    if unsafe:
        fallback = _next_fallback(config, current.workers, measured)
        if fallback is not None:
            return {
                "action": "test",
                "workers": fallback,
                "reason": "unsafe_current_trial",
                "unsafe_reasons": unsafe,
                "selected_workers": None,
                "diagnostics": _diagnostics(current, config),
            }
        best = _best_stable(trials, config)
        if best is not None:
            return {
                "action": "accept",
                "workers": None,
                "reason": "unsafe_scale_up_reverted_to_best_stable",
                "unsafe_reasons": unsafe,
                "selected_workers": best.workers,
                "diagnostics": _diagnostics(current, config),
            }
        return {
            "action": "stop",
            "workers": None,
            "reason": "unsafe_without_stable_candidate",
            "unsafe_reasons": unsafe,
            "selected_workers": None,
            "diagnostics": _diagnostics(current, config),
        }

    fallback_workers = {int(value) for value in config["fallback_workers"]}
    if current.workers in fallback_workers:
        return {
            "action": "accept",
            "workers": None,
            "reason": "stable_fallback_after_unsafe_higher_trial",
            "selected_workers": current.workers,
            "diagnostics": _diagnostics(current, config),
        }

    ladder = _scale_ladder(config)
    if current.workers not in ladder:
        raise WorkerTuningError(f"unsupported 32-core tuning state: {current.workers}")
    position = ladder.index(current.workers)
    baseline = _mean_trial(trials, initial)
    assert baseline is not None

    marginal_efficiency: float | None = None
    if position > 0:
        previous_workers = ladder[position - 1]
        previous = _mean_trial(trials, previous_workers)
        if previous is None:
            raise WorkerTuningError(
                f"{current.workers}-worker trial requires a prior {previous_workers}-worker trial"
            )
        marginal_efficiency = _marginal_efficiency(current, previous, baseline)
        minimum_efficiency = _threshold(
            config,
            "scale_up_thresholds",
            "minimum_marginal_throughput_efficiency_ratio",
        )
        if marginal_efficiency < minimum_efficiency:
            return {
                "action": "accept",
                "workers": None,
                "reason": "marginal_throughput_gain_is_insufficient",
                "marginal_throughput_efficiency_ratio": marginal_efficiency,
                "selected_workers": previous.workers,
                "diagnostics": _diagnostics(current, config),
            }

    if current.workers == int(config["maximum_workers"]):
        return {
            "action": "accept",
            "workers": None,
            "reason": "maximum_worker_candidate_is_stable",
            "marginal_throughput_efficiency_ratio": marginal_efficiency,
            "selected_workers": current.workers,
            "diagnostics": _diagnostics(current, config),
        }

    next_workers = ladder[position + 1]
    projected_headroom = _projected_headroom_gib(current, next_workers)
    minimum_headroom = _threshold(
        config,
        "scale_up_thresholds",
        "minimum_projected_memory_headroom_gib",
    )
    if projected_headroom < minimum_headroom:
        return {
            "action": "accept",
            "workers": None,
            "reason": "projected_memory_headroom_too_low",
            "projected_headroom_gib": projected_headroom,
            "marginal_throughput_efficiency_ratio": marginal_efficiency,
            "selected_workers": current.workers,
            "diagnostics": _diagnostics(current, config),
        }

    if next_workers in measured:
        return {
            "action": "accept",
            "workers": None,
            "reason": "next_scale_candidate_already_measured",
            "selected_workers": current.workers,
            "diagnostics": _diagnostics(current, config),
        }
    return {
        "action": "test",
        "workers": next_workers,
        "reason": "stable_with_measured_capacity_for_scale_up",
        "projected_headroom_gib": projected_headroom,
        "marginal_throughput_efficiency_ratio": marginal_efficiency,
        "selected_workers": None,
        "diagnostics": _diagnostics(current, config),
    }
