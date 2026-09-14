"""Live resource telemetry and throughput-based ETA for durable research runs.

The monitor is deliberately separate from the scientific worker process.  It
only reads run/cache metadata and Linux ``/proc`` counters, then writes status
under the output root's monitor directory.  Live telemetry therefore cannot
change the content-addressed research objects or their download bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import signal
import socket
import statistics
import time
from typing import Any, Mapping, Sequence

from .runtime import atomic_write_json, read_json, utc_now


MONITOR_SCHEMA = 1
STAGES = (
    ("01_embeddings_and_clean", "digital_embedding", 16),
    ("02_core_channels", "digital_channel_evaluation", 48),
    ("03_conditional_hard_checks", "digital_channel_evaluation", 24),
)


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _boot_id() -> str | None:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(
            encoding="ascii"
        ).strip()
    except OSError:
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def discover_research_run(
    output_root: str | Path,
    *,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the active run, or the newest inactive run when none is active."""

    runs = Path(output_root).resolve() / "runs"
    if run_id is not None:
        candidates = [runs / run_id]
    elif runs.is_dir():
        candidates = [path for path in runs.iterdir() if path.is_dir()]
    else:
        candidates = []
    discovered: list[dict[str, Any]] = []
    current_boot = _boot_id()
    host = socket.gethostname()
    for run_dir in candidates:
        if not (run_dir / "plan.json").is_file():
            continue
        lock = _safe_json(run_dir / "run.lock")
        pid = lock.get("pid")
        active = (
            isinstance(pid, int)
            and _pid_alive(pid)
            and lock.get("host") == host
            and (
                current_boot is None
                or lock.get("boot_id") is None
                or lock.get("boot_id") == current_boot
            )
        )
        timestamps = [
            path.stat().st_mtime
            for path in (
                run_dir / "run.lock",
                run_dir / "state.json",
                run_dir / "run_summary.json",
                run_dir / "plan.json",
            )
            if path.exists()
        ]
        discovered.append(
            {
                "run_id": run_dir.name,
                "run_dir": str(run_dir),
                "active": active,
                "pid": pid if active else None,
                "lock": lock,
                "mtime": max(timestamps, default=0.0),
            }
        )
    if not discovered:
        return None
    active_runs = [item for item in discovered if item["active"]]
    selected = max(active_runs or discovered, key=lambda item: item["mtime"])
    return selected


def _event_window(run_dir: Path, stage: str) -> tuple[datetime | None, int]:
    started: datetime | None = None
    started_sequence = -1
    finished = 0
    events = run_dir / "events"
    if not events.is_dir():
        return None, 0
    parsed_events: list[dict[str, Any]] = []
    for path in sorted(events.glob("*.json")):
        event = _safe_json(path)
        if event:
            parsed_events.append(event)
    for event in parsed_events:
        if event.get("event") == "stage_started" and event.get("stage") == stage:
            candidate = _parse_utc(event.get("recorded_at"))
            if candidate is not None:
                started = candidate
                started_sequence = int(event.get("sequence", -1))
                finished = 0
        elif (
            started is not None
            and int(event.get("sequence", -1)) > started_sequence
            and event.get("event") == "task_finished"
            and event.get("stage") == stage
            and event.get("status") in {"completed", "cached"}
        ):
            finished += 1
    return started, finished


def _task_durations(
    state: Mapping[str, Any],
    *,
    cache_dir: Path | None,
) -> dict[str, list[float]]:
    durations: dict[str, list[float]] = {
        "digital_embedding": [],
        "digital_channel_evaluation": [],
    }
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return durations
    for stage in stages.values():
        if not isinstance(stage, dict):
            continue
        tasks = stage.get("tasks")
        if not isinstance(tasks, dict):
            continue
        for object_id, record in tasks.items():
            if not isinstance(record, dict):
                continue
            kind = str(record.get("kind", ""))
            if kind not in durations:
                continue
            resource = record.get("resource")
            if not isinstance(resource, dict) and cache_dir is not None:
                resource_path = (
                    cache_dir
                    / "objects"
                    / str(object_id)[:2]
                    / str(object_id)[2:]
                    / "resource.json"
                )
                resource = _safe_json(resource_path)
            if isinstance(resource, dict):
                wall = resource.get("wall_seconds")
                if isinstance(wall, (int, float)) and wall > 0:
                    durations[kind].append(float(wall))
    return durations


def _stage_counts(
    state: Mapping[str, Any],
    stage_name: str,
    default_total: int,
) -> dict[str, int | str]:
    stages = state.get("stages")
    stage = stages.get(stage_name, {}) if isinstance(stages, dict) else {}
    if not isinstance(stage, dict):
        stage = {}
    counts = stage.get("counts")
    if not isinstance(counts, dict):
        counts = {}
    cached = int(counts.get("cached", 0) or 0)
    completed = int(counts.get("completed", 0) or 0)
    failed = int(counts.get("failed", 0) or 0)
    task_count = len(stage.get("tasks", {})) if isinstance(
        stage.get("tasks"), dict
    ) else default_total
    if task_count == 0:
        task_count = default_total
    finished = min(task_count, cached + completed)
    return {
        "status": str(stage.get("status", "not_started")),
        "total": task_count,
        "cached": cached,
        "completed": completed,
        "failed": failed,
        "finished": finished,
        "remaining": max(0, task_count - finished - failed),
    }


def _estimate_group(
    remaining: int,
    *,
    kind: str,
    workers: int,
    duration_medians: Mapping[str, float | None],
) -> float | None:
    if remaining <= 0:
        return 0.0
    median = duration_medians.get(kind)
    if median is None or median <= 0:
        return None
    return remaining * median / max(1, workers)


def _sum_known(values: Sequence[float | None]) -> float | None:
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None)


def build_progress(
    run_dir: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build progress and ETA from durable state and observed task durations."""

    destination = Path(run_dir).resolve()
    state = _safe_json(destination / "state.json")
    context = _safe_json(destination / "runtime_context.json")
    resource_plan = _safe_json(destination / "resource_plan.json")
    decisions = _safe_json(destination / "trigger_decisions.json")
    workers = int(
        context.get("workers")
        or resource_plan.get("resolved")
        or 1
    )
    cache_value = context.get("cache_dir")
    cache_dir = (
        Path(str(cache_value)).resolve()
        if isinstance(cache_value, str) and cache_value
        else None
    )
    triggered = decisions.get("triggered_families")
    triggered_families = (
        [str(item) for item in triggered]
        if isinstance(triggered, list)
        else None
    )
    conditional_total = (
        8 * len(triggered_families)
        if triggered_families is not None
        else 24
    )
    stage_counts = {
        name: _stage_counts(
            state,
            name,
            conditional_total if index == 2 else default_total,
        )
        for index, (name, _kind, default_total) in enumerate(STAGES)
    }
    current_stage: str | None = None
    for name, _kind, _default_total in STAGES:
        if stage_counts[name]["status"] == "running":
            current_stage = name
            break
    if current_stage is None:
        for name, _kind, _default_total in STAGES:
            if int(stage_counts[name]["remaining"]) > 0:
                current_stage = name
                break

    durations = _task_durations(state, cache_dir=cache_dir)
    duration_medians: dict[str, float | None] = {
        kind: statistics.median(values) if values else None
        for kind, values in durations.items()
    }
    current_time = now or datetime.now(timezone.utc)
    observed_rate: float | None = None
    observed_finished = 0
    observed_elapsed: float | None = None
    if current_stage is not None:
        started, observed_finished = _event_window(destination, current_stage)
        if started is not None:
            observed_elapsed = max(
                0.001,
                (current_time - started).total_seconds(),
            )
            if observed_finished >= 2:
                observed_rate = observed_finished / observed_elapsed

    estimates: dict[str, float | None] = {}
    for name, kind, _default_total in STAGES:
        remaining = int(stage_counts[name]["remaining"])
        estimates[name] = _estimate_group(
            remaining,
            kind=kind,
            workers=workers,
            duration_medians=duration_medians,
        )
    eta_basis = "historical_task_durations"
    confidence = "warming_up"
    if current_stage is not None and observed_rate is not None:
        estimates[current_stage] = (
            int(stage_counts[current_stage]["remaining"]) / observed_rate
        )
        eta_basis = "live_stage_throughput"
        confidence = "medium" if observed_finished < 6 else "high"
    elif any(value is not None for value in duration_medians.values()):
        confidence = "low"

    mandatory_eta = _sum_known(
        [
            estimates["01_embeddings_and_clean"],
            estimates["02_core_channels"],
        ]
    )
    conditional_selected_eta = (
        estimates["03_conditional_hard_checks"]
        if triggered_families is not None
        else None
    )
    selected_eta = (
        _sum_known([mandatory_eta, conditional_selected_eta])
        if triggered_families is not None
        else None
    )
    maximum_eta = _sum_known(
        [
            mandatory_eta,
            estimates["03_conditional_hard_checks"],
        ]
    )
    mandatory_finished = min(
        64,
        int(stage_counts["01_embeddings_and_clean"]["finished"])
        + int(stage_counts["02_core_channels"]["finished"]),
    )
    conditional_finished = int(
        stage_counts["03_conditional_hard_checks"]["finished"]
    )
    all_finished = mandatory_finished + conditional_finished
    selected_total = (
        64 + conditional_total
        if triggered_families is not None
        else None
    )

    def completion_at(seconds: float | None) -> str | None:
        if seconds is None or not math.isfinite(seconds):
            return None
        return (
            current_time + timedelta(seconds=max(0.0, seconds))
        ).isoformat().replace("+00:00", "Z")

    return {
        "current_stage": current_stage,
        "workers": workers,
        "stages": stage_counts,
        "completed_rows": all_finished,
        "mandatory": {
            "completed": mandatory_finished,
            "total": 64,
            "percent": 100.0 * mandatory_finished / 64,
        },
        "selected": {
            "completed": all_finished,
            "total": selected_total,
            "percent": (
                None
                if selected_total is None
                else 100.0 * all_finished / selected_total
            ),
            "triggered_families": triggered_families,
        },
        "maximum": {
            "completed": all_finished,
            "total": 88,
            "percent": 100.0 * all_finished / 88,
        },
        "throughput": {
            "basis": eta_basis,
            "confidence": confidence,
            "observed_completions": observed_finished,
            "observed_elapsed_seconds": observed_elapsed,
            "tasks_per_hour": (
                None if observed_rate is None else observed_rate * 3600.0
            ),
            "median_wall_seconds": duration_medians,
            "samples_by_kind": {
                kind: len(values) for kind, values in durations.items()
            },
        },
        "eta": {
            "mandatory_seconds": mandatory_eta,
            "mandatory_completion_at": completion_at(mandatory_eta),
            "selected_seconds": selected_eta,
            "selected_completion_at": completion_at(selected_eta),
            "maximum_seconds": maximum_eta,
            "maximum_completion_at": completion_at(maximum_eta),
        },
    }


def _system_cpu_counters() -> dict[str, int] | None:
    try:
        line = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0]
    except (OSError, IndexError):
        return None
    fields = line.split()
    if not fields or fields[0] != "cpu":
        return None
    values = [int(value) for value in fields[1:]]
    values.extend([0] * max(0, 8 - len(values)))
    return {
        "total": sum(values),
        "idle": values[3] + values[4],
        "iowait": values[4],
    }


def _memory_counters() -> dict[str, int] | None:
    values: dict[str, int] = {}
    try:
        lines = Path("/proc/meminfo").read_text(encoding="ascii").splitlines()
    except OSError:
        return None
    for line in lines:
        key, separator, value = line.partition(":")
        if not separator:
            continue
        first = value.strip().split()[0]
        if first.isdigit():
            values[key] = int(first) * 1024
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if total is None or available is None:
        return None
    return {"total": total, "available": available}


@dataclass(frozen=True)
class _ProcessCounter:
    pid: int
    ppid: int
    ticks: int
    rss_bytes: int
    threads: int
    read_bytes: int
    write_bytes: int


def _one_process(pid: int) -> _ProcessCounter | None:
    root = Path("/proc") / str(pid)
    try:
        stat = (root / "stat").read_text(encoding="ascii")
        tail = stat.rsplit(")", 1)[1].strip().split()
        ppid = int(tail[1])
        ticks = int(tail[11]) + int(tail[12])
        threads = int(tail[17])
        rss_bytes = int(tail[21]) * int(os.sysconf("SC_PAGE_SIZE"))
    except (OSError, IndexError, ValueError):
        return None
    io_values = {"read_bytes": 0, "write_bytes": 0}
    try:
        for line in (root / "io").read_text(encoding="ascii").splitlines():
            key, separator, value = line.partition(":")
            if separator and key in io_values:
                io_values[key] = int(value.strip())
    except (OSError, ValueError):
        pass
    return _ProcessCounter(
        pid=pid,
        ppid=ppid,
        ticks=ticks,
        rss_bytes=rss_bytes,
        threads=threads,
        read_bytes=io_values["read_bytes"],
        write_bytes=io_values["write_bytes"],
    )


def _process_tree_counters(root_pid: int) -> dict[str, int] | None:
    processes: dict[int, _ProcessCounter] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        counter = _one_process(int(entry.name))
        if counter is not None:
            processes[counter.pid] = counter
    if root_pid not in processes:
        return None
    selected = {root_pid}
    changed = True
    while changed:
        changed = False
        for process in processes.values():
            if process.ppid in selected and process.pid not in selected:
                selected.add(process.pid)
                changed = True
    counters = [processes[pid] for pid in selected]
    return {
        "ticks": sum(item.ticks for item in counters),
        "rss_bytes": sum(item.rss_bytes for item in counters),
        "threads": sum(item.threads for item in counters),
        "read_bytes": sum(item.read_bytes for item in counters),
        "write_bytes": sum(item.write_bytes for item in counters),
        "processes": len(counters),
    }


def _load_average() -> dict[str, float] | None:
    try:
        first = Path("/proc/loadavg").read_text(encoding="ascii").split()[:3]
        one, five, fifteen = (float(value) for value in first)
    except (OSError, ValueError):
        return None
    return {"one": one, "five": five, "fifteen": fifteen}


def _disk_usage(path: Path) -> dict[str, int | str] | None:
    try:
        usage = os.statvfs(path)
    except OSError:
        return None
    return {
        "path": str(path),
        "total_bytes": usage.f_frsize * usage.f_blocks,
        "free_bytes": usage.f_frsize * usage.f_bavail,
    }


def _resource_snapshot(
    *,
    root_pid: int | None,
    workers: int,
    output_root: Path,
    cache_dir: Path | None,
    previous: Mapping[str, Any] | None,
    elapsed: float | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    system_cpu = _system_cpu_counters()
    process = (
        _process_tree_counters(root_pid)
        if root_pid is not None
        else None
    )
    counters = {
        "boot_id": _boot_id(),
        "system_cpu": system_cpu,
        "process": process,
    }
    prior_counters = previous.get("_counters") if isinstance(previous, dict) else None
    system_percent: float | None = None
    iowait_percent: float | None = None
    algorithm_one_core: float | None = None
    read_rate: float | None = None
    write_rate: float | None = None
    if (
        elapsed is not None
        and elapsed > 0
        and isinstance(prior_counters, dict)
        and prior_counters.get("boot_id") == counters["boot_id"]
    ):
        prior_system = prior_counters.get("system_cpu")
        if isinstance(system_cpu, dict) and isinstance(prior_system, dict):
            total_delta = system_cpu["total"] - int(prior_system.get("total", 0))
            idle_delta = system_cpu["idle"] - int(prior_system.get("idle", 0))
            iowait_delta = system_cpu["iowait"] - int(
                prior_system.get("iowait", 0)
            )
            if total_delta > 0:
                system_percent = 100.0 * (total_delta - idle_delta) / total_delta
                iowait_percent = 100.0 * iowait_delta / total_delta
        prior_process = prior_counters.get("process")
        if isinstance(process, dict) and isinstance(prior_process, dict):
            ticks_delta = process["ticks"] - int(prior_process.get("ticks", 0))
            clock_ticks = int(os.sysconf("SC_CLK_TCK"))
            algorithm_one_core = (
                100.0 * max(0, ticks_delta) / clock_ticks / elapsed
            )
            read_rate = max(
                0.0,
                (
                    process["read_bytes"]
                    - int(prior_process.get("read_bytes", 0))
                )
                / elapsed,
            )
            write_rate = max(
                0.0,
                (
                    process["write_bytes"]
                    - int(prior_process.get("write_bytes", 0))
                )
                / elapsed,
            )
    cpu_total = os.cpu_count() or 1
    allocated_capacity = max(1, workers) * 100.0
    allocated_percent = (
        None
        if algorithm_one_core is None
        else 100.0 * algorithm_one_core / allocated_capacity
    )
    host_capacity_percent = (
        None
        if algorithm_one_core is None
        else algorithm_one_core / cpu_total
    )
    memory = _memory_counters()
    memory_payload: dict[str, Any] | None = None
    if memory is not None:
        used = memory["total"] - memory["available"]
        memory_payload = {
            **memory,
            "used_bytes": used,
            "system_used_percent": 100.0 * used / memory["total"],
            "algorithm_rss_bytes": (
                None if process is None else process["rss_bytes"]
            ),
            "algorithm_rss_percent": (
                None
                if process is None
                else 100.0 * process["rss_bytes"] / memory["total"]
            ),
        }
    assessment = "warming_up"
    if memory_payload is not None and memory_payload["system_used_percent"] >= 92:
        assessment = "memory_pressure"
    elif iowait_percent is not None and iowait_percent >= 10:
        assessment = "io_wait_limited"
    elif allocated_percent is not None and allocated_percent >= 85:
        assessment = "using_allocated_cpu"
    elif allocated_percent is not None:
        assessment = "below_allocated_cpu"
    storage: dict[str, Any] = {
        "output_root": _disk_usage(output_root),
    }
    if cache_dir is not None:
        storage["cache"] = _disk_usage(cache_dir)
    resource = {
        "cpu": {
            "logical_cpus": cpu_total,
            "allocated_workers": workers,
            "algorithm_percent_one_core": algorithm_one_core,
            "algorithm_percent_of_allocated": allocated_percent,
            "algorithm_percent_of_host": host_capacity_percent,
            "system_busy_percent": system_percent,
            "system_iowait_percent": iowait_percent,
            "load_average": _load_average(),
        },
        "memory": memory_payload,
        "process_tree": (
            None
            if process is None
            else {
                key: value
                for key, value in process.items()
                if key not in {"ticks"}
            }
        ),
        "io": {
            "read_bytes_per_second": read_rate,
            "write_bytes_per_second": write_rate,
        },
        "storage": storage,
        "assessment": assessment,
    }
    return resource, counters


class ResearchSampler:
    """Stateful sampler used by the daemon and interactive watch command."""

    def __init__(
        self,
        *,
        output_root: str | Path,
        run_id: str | None = None,
    ):
        self.output_root = Path(output_root).resolve()
        self.run_id = run_id
        self._previous: dict[str, Any] | None = None
        self._previous_monotonic: float | None = None

    def sample(self) -> dict[str, Any]:
        now_monotonic = time.monotonic()
        elapsed = (
            None
            if self._previous_monotonic is None
            else now_monotonic - self._previous_monotonic
        )
        discovered = discover_research_run(
            self.output_root,
            run_id=self.run_id,
        )
        if discovered is None:
            snapshot = {
                "schema": MONITOR_SCHEMA,
                "sampled_at": utc_now(),
                "lifecycle": "idle_no_run",
                "active": False,
                "run_id": None,
                "run_dir": None,
                "progress": None,
                "resources": None,
                "_counters": {
                    "boot_id": _boot_id(),
                    "system_cpu": _system_cpu_counters(),
                    "process": None,
                },
            }
        else:
            run_dir = Path(discovered["run_dir"])
            progress = build_progress(run_dir)
            context = _safe_json(run_dir / "runtime_context.json")
            cache_value = context.get("cache_dir")
            cache_dir = (
                Path(str(cache_value)).resolve()
                if isinstance(cache_value, str) and cache_value
                else None
            )
            resources, counters = _resource_snapshot(
                root_pid=discovered["pid"],
                workers=int(progress["workers"]),
                output_root=self.output_root,
                cache_dir=cache_dir,
                previous=self._previous,
                elapsed=elapsed,
            )
            summary = _safe_json(run_dir / "run_summary.json")
            lifecycle = (
                "running"
                if discovered["active"]
                else str(summary.get("status", "inactive"))
            )
            snapshot = {
                "schema": MONITOR_SCHEMA,
                "sampled_at": utc_now(),
                "lifecycle": lifecycle,
                "active": bool(discovered["active"]),
                "run_id": discovered["run_id"],
                "run_dir": discovered["run_dir"],
                "root_pid": discovered["pid"],
                "progress": progress,
                "resources": resources,
                "_counters": counters,
            }
        self._previous = snapshot
        self._previous_monotonic = now_monotonic
        return snapshot


def _append_json_line(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o640,
    )
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def public_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Remove private delta counters before display or persistence."""

    return {
        key: value
        for key, value in snapshot.items()
        if key != "_counters"
    }


def write_snapshot(
    status_dir: str | Path,
    snapshot: Mapping[str, Any],
) -> Path:
    destination = Path(status_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    public = public_snapshot(snapshot)
    atomic_write_json(destination / "latest.json", public)
    _append_json_line(destination / "samples.jsonl", public)
    return destination / "latest.json"


def run_monitor(
    *,
    output_root: str | Path,
    status_dir: str | Path,
    interval_seconds: float = 5.0,
    run_id: str | None = None,
    once: bool = False,
) -> dict[str, Any]:
    if interval_seconds <= 0:
        raise ValueError("monitor interval must be positive")
    sampler = ResearchSampler(output_root=output_root, run_id=run_id)
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    prior_handlers: dict[int, Any] = {}
    if not once:
        for signum in (signal.SIGINT, signal.SIGTERM):
            prior_handlers[signum] = signal.signal(signum, stop)
    try:
        latest: dict[str, Any] = {}
        while True:
            raw = sampler.sample()
            write_snapshot(status_dir, raw)
            latest = public_snapshot(raw)
            if once or stopping:
                return latest
            deadline = time.monotonic() + interval_seconds
            while not stopping and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    finally:
        for signum, handler in prior_handlers.items():
            signal.signal(signum, handler)


def _duration(value: object) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "warming up"
    seconds = max(0, int(round(float(value))))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def _percent(value: object) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    return f"{float(value):.1f}%"


def _gib(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{float(value) / 1024**3:.2f} GiB"


def _byte_rate(value: object) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        return "n/a"
    amount = max(0.0, float(value))
    units = ("B/s", "KiB/s", "MiB/s", "GiB/s")
    for unit in units[:-1]:
        if amount < 1024:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.2f} {units[-1]}"


def format_status(snapshot: Mapping[str, Any]) -> str:
    if snapshot.get("run_id") is None:
        return (
            f"Lifecycle: {snapshot.get('lifecycle', 'idle')}\n"
            f"Updated:   {snapshot.get('sampled_at', 'unknown')}"
        )
    progress = snapshot.get("progress")
    resources = snapshot.get("resources")
    if not isinstance(progress, dict):
        progress = {}
    if not isinstance(resources, dict):
        resources = {}
    mandatory = progress.get("mandatory", {})
    selected = progress.get("selected", {})
    maximum = progress.get("maximum", {})
    eta = progress.get("eta", {})
    throughput = progress.get("throughput", {})
    cpu = resources.get("cpu", {})
    memory = resources.get("memory")
    io_payload = resources.get("io", {})
    if not isinstance(memory, dict):
        memory = {}
    selected_total = selected.get("total")
    selected_text = (
        "pending trigger decision"
        if selected_total is None
        else (
            f"{selected.get('completed', 0)}/{selected_total} "
            f"({_percent(selected.get('percent'))})"
        )
    )
    tasks_per_hour = throughput.get("tasks_per_hour")
    rate_text = (
        "warming up"
        if not isinstance(tasks_per_hour, (int, float))
        else f"{tasks_per_hour:.2f} tasks/hour"
    )
    return "\n".join(
        (
            (
                f"Run:       {snapshot.get('run_id')} "
                f"[{str(snapshot.get('lifecycle', '')).upper()}]"
            ),
            f"Stage:     {progress.get('current_stage') or 'finished'}",
            (
                f"Progress:  mandatory {mandatory.get('completed', 0)}/"
                f"{mandatory.get('total', 64)} "
                f"({_percent(mandatory.get('percent'))}); "
                f"selected {selected_text}; "
                f"max {maximum.get('completed', 0)}/88"
            ),
            (
                f"ETA:       mandatory {_duration(eta.get('mandatory_seconds'))}; "
                f"selected {_duration(eta.get('selected_seconds'))}; "
                f"max {_duration(eta.get('maximum_seconds'))}"
            ),
            (
                f"Rate:      {rate_text} "
                f"({throughput.get('basis', 'unknown')}, "
                f"{throughput.get('confidence', 'warming_up')})"
            ),
            (
                f"CPU:       algorithm "
                f"{_percent(cpu.get('algorithm_percent_one_core'))} of one core; "
                f"{_percent(cpu.get('algorithm_percent_of_allocated'))} "
                f"of {cpu.get('allocated_workers', '?')}-worker capacity; "
                f"system {_percent(cpu.get('system_busy_percent'))}; "
                f"iowait {_percent(cpu.get('system_iowait_percent'))}"
            ),
            (
                f"RAM:       algorithm {_gib(memory.get('algorithm_rss_bytes'))}; "
                f"system {_percent(memory.get('system_used_percent'))}; "
                f"available {_gib(memory.get('available'))}"
            ),
            (
                f"I/O:       read "
                f"{_byte_rate(io_payload.get('read_bytes_per_second'))}; "
                f"write {_byte_rate(io_payload.get('write_bytes_per_second'))}"
            ),
            f"Assessment: {resources.get('assessment', 'unavailable')}",
            f"Updated:    {snapshot.get('sampled_at', 'unknown')}",
        )
    )
