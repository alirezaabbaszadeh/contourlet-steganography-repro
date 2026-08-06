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
    minimum_available_memory_bytes: int
    p95_worker_rss_bytes: int
    max_worker_rss_bytes: int
    task_selection_sha256: str
    trial_sha256: str

    @property
    def minimum_available_memory_gib(self) -> float:
        return self.minimum_available_memory_bytes / GIB

    @property
    def p95_worker_rss_gib(self) -> float:
        return self.p95_worker_rss_bytes / GIB


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
    if payload.get("initial_workers") != 16:
        raise WorkerTuningError("the first measured trial must use 16 workers")
    if payload.get("maximum_workers") != 28:
        raise WorkerTuningError("the 64-GiB host profile must cap at 28 workers")
    order = payload.get("candidate_order")
    if order != [16, 12, 8, 20, 24, 28]:
        raise WorkerTuningError("worker candidate order differs from the frozen protocol")
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
    if not all(isinstance(item, Mapping) for item in (tasks, timing, cpu, memory, swap)):
        raise WorkerTuningError("trial metric sections are missing")
    assert isinstance(tasks, Mapping)
    assert isinstance(timing, Mapping)
    assert isinstance(cpu, Mapping)
    assert isinstance(memory, Mapping)
    assert isinstance(swap, Mapping)

    workers = _integer(payload, "workers", minimum=1)
    if workers not in {8, 12, 16, 20, 24, 28}:
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

    return Trial(
        workers=workers,
        wall_seconds=_number(timing, "wall_seconds", minimum=0.001),
        combined_tasks_per_hour=_number(
            timing,
            "combined_tasks_per_hour",
            minimum=0.0,
        ),
        operational_failures=_integer(tasks, "operational_failures", minimum=0),
        oom_events=_integer(tasks, "oom_events", minimum=0),
        swap_io_bytes=_integer(swap, "io_bytes", minimum=0),
        mean_cpu_busy_percent=_number(cpu, "mean_busy_percent", minimum=0.0),
        p95_iowait_percent=_number(cpu, "p95_iowait_percent", minimum=0.0),
        minimum_available_memory_bytes=_integer(
            memory,
            "minimum_available_bytes",
            minimum=0,
        ),
        p95_worker_rss_bytes=_integer(memory, "p95_worker_rss_bytes", minimum=1),
        max_worker_rss_bytes=_integer(memory, "max_worker_rss_bytes", minimum=1),
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
    if trial.operational_failures > int(
        _threshold(config, "rejection_thresholds", "maximum_operational_failures")
    ):
        reasons.append("operational_failures")
    if trial.oom_events > int(
        _threshold(config, "rejection_thresholds", "maximum_oom_events")
    ):
        reasons.append("oom_events")
    if trial.swap_io_bytes > int(
        _threshold(config, "rejection_thresholds", "maximum_swap_io_bytes")
    ):
        reasons.append("swap_io")
    if trial.minimum_available_memory_gib < _threshold(
        config,
        "rejection_thresholds",
        "minimum_available_memory_gib",
    ):
        reasons.append("memory_floor")
    if trial.p95_iowait_percent > _threshold(
        config,
        "rejection_thresholds",
        "maximum_sustained_iowait_percent",
    ):
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
        combined_tasks_per_hour=(
            first.combined_tasks_per_hour + second.combined_tasks_per_hour
        ) / 2,
        operational_failures=first.operational_failures + second.operational_failures,
        oom_events=first.oom_events + second.oom_events,
        swap_io_bytes=first.swap_io_bytes + second.swap_io_bytes,
        mean_cpu_busy_percent=(
            first.mean_cpu_busy_percent + second.mean_cpu_busy_percent
        ) / 2,
        p95_iowait_percent=max(first.p95_iowait_percent, second.p95_iowait_percent),
        minimum_available_memory_bytes=min(
            first.minimum_available_memory_bytes,
            second.minimum_available_memory_bytes,
        ),
        p95_worker_rss_bytes=max(
            first.p95_worker_rss_bytes,
            second.p95_worker_rss_bytes,
        ),
        max_worker_rss_bytes=max(first.max_worker_rss_bytes, second.max_worker_rss_bytes),
        task_selection_sha256=first.task_selection_sha256,
        trial_sha256=canonical_sha256([first.trial_sha256, second.trial_sha256]),
    )


def _gain_percent(new: Trial, old: Trial) -> float:
    if old.combined_tasks_per_hour <= 0:
        return 0.0
    return 100.0 * (
        new.combined_tasks_per_hour - old.combined_tasks_per_hour
    ) / old.combined_tasks_per_hour


def _projected_headroom_gib(current: Trial, candidate_workers: int) -> float:
    additional = max(0, candidate_workers - current.workers)
    # A 20% safety factor covers process variation and shared Octave allocations.
    projected_extra = additional * current.p95_worker_rss_gib * 1.20
    return current.minimum_available_memory_gib - projected_extra


def _best_stable(trials: Sequence[Trial], config: Mapping[str, Any]) -> Trial | None:
    candidates: list[Trial] = []
    for workers in (8, 12, 16, 20, 24, 28):
        trial = _mean_trial(trials, workers)
        if trial is not None and not unsafe_reasons(trial, config):
            candidates.append(trial)
    return max(candidates, key=lambda item: item.combined_tasks_per_hour, default=None)


def recommend(config: Mapping[str, Any], trials: Sequence[Trial]) -> dict[str, Any]:
    """Return the next trial or the selected stable worker count."""

    if not trials:
        return {
            "action": "test",
            "workers": 16,
            "reason": "first_measured_trial",
            "selected_workers": None,
        }
    if 16 not in {trial.workers for trial in trials}:
        raise WorkerTuningError("the first measured trial must be 16 workers")

    latest = trials[-1]
    current = _mean_trial(trials, latest.workers)
    assert current is not None
    unsafe = unsafe_reasons(current, config)
    if unsafe:
        downward = {16: 12, 12: 8}
        next_workers = downward.get(current.workers)
        if next_workers is not None and next_workers not in {
            trial.workers for trial in trials
        }:
            return {
                "action": "test",
                "workers": next_workers,
                "reason": "unsafe_current_trial",
                "unsafe_reasons": unsafe,
                "selected_workers": None,
            }
        best = _best_stable(trials, config)
        return {
            "action": "stop",
            "workers": None,
            "reason": "unsafe_without_untested_lower_candidate",
            "unsafe_reasons": unsafe,
            "selected_workers": best.workers if best else None,
        }

    # A lower trial is reached only after an unsafe higher trial; do not scale back up
    # without an explicit new protocol decision.
    if current.workers in {8, 12}:
        return {
            "action": "accept",
            "workers": None,
            "reason": "stable_fallback_after_unsafe_higher_trial",
            "selected_workers": current.workers,
        }

    up = {16: 20, 20: 24, 24: 28}
    candidate = up.get(current.workers)
    if candidate is None:
        best = _best_stable(trials, config)
        return {
            "action": "accept",
            "workers": None,
            "reason": "maximum_candidate_measured",
            "selected_workers": best.workers if best else current.workers,
        }

    if candidate in {trial.workers for trial in trials}:
        best = _best_stable(trials, config)
        return {
            "action": "accept",
            "workers": None,
            "reason": "candidate_already_measured",
            "selected_workers": best.workers if best else current.workers,
        }

    if current.mean_cpu_busy_percent < _threshold(
        config,
        "scale_up_thresholds",
        "minimum_mean_cpu_busy_percent",
    ):
        return {
            "action": "accept",
            "workers": None,
            "reason": "cpu_busy_below_scale_up_threshold",
            "selected_workers": current.workers,
        }
    if current.p95_iowait_percent > _threshold(
        config,
        "scale_up_thresholds",
        "maximum_p95_iowait_percent",
    ):
        return {
            "action": "accept",
            "workers": None,
            "reason": "iowait_blocks_scale_up",
            "selected_workers": current.workers,
        }

    headroom = _projected_headroom_gib(current, candidate)
    minimum_headroom = _threshold(
        config,
        "scale_up_thresholds",
        "minimum_projected_memory_headroom_gib",
    )
    if headroom < minimum_headroom:
        return {
            "action": "accept",
            "workers": None,
            "reason": "projected_memory_headroom_too_low",
            "projected_headroom_gib": headroom,
            "selected_workers": current.workers,
        }

    previous = {20: 16, 24: 20, 28: 24}.get(current.workers)
    if previous is not None:
        lower = _mean_trial(trials, previous)
        if lower is not None:
            gain = _gain_percent(current, lower)
            stop_gain = _threshold(
                config,
                "stop_thresholds",
                "minimum_incremental_throughput_gain_percent",
            )
            if gain < stop_gain:
                best = _best_stable(trials, config)
                return {
                    "action": "accept",
                    "workers": None,
                    "reason": "incremental_throughput_gain_too_small",
                    "gain_percent": gain,
                    "selected_workers": best.workers if best else current.workers,
                }

    if current.workers == 20:
        baseline = _mean_trial(trials, 16)
        assert baseline is not None
        gain = _gain_percent(current, baseline)
        if gain < _threshold(
            config,
            "scale_up_thresholds",
            "minimum_gain_percent_for_24",
        ):
            best = _best_stable(trials, config)
            return {
                "action": "accept",
                "workers": None,
                "reason": "gain_is_insufficient_for_24_workers",
                "gain_percent": gain,
                "selected_workers": best.workers if best else current.workers,
            }
    if current.workers == 24:
        baseline = _mean_trial(trials, 20)
        if baseline is None:
            raise WorkerTuningError("24-worker trial requires a 20-worker trial")
        gain = _gain_percent(current, baseline)
        if gain < _threshold(
            config,
            "scale_up_thresholds",
            "minimum_gain_percent_for_28",
        ):
            best = _best_stable(trials, config)
            return {
                "action": "accept",
                "workers": None,
                "reason": "gain_is_insufficient_for_28_workers",
                "gain_percent": gain,
                "selected_workers": best.workers if best else current.workers,
            }

    return {
        "action": "test",
        "workers": candidate,
        "reason": "stable_with_capacity_for_scale_up",
        "projected_headroom_gib": headroom,
        "selected_workers": None,
    }
