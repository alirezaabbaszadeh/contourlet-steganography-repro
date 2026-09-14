"""Deliberately kill and resume the durable runtime before research execution."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
from typing import Any
import uuid

from ctsteg.runtime import ContentStore, atomic_write_json, read_json, utc_now
from ctsteg.runtime_gate_contract import runtime_gate_fingerprint

from .research_runtime import create_download_bundle, verify_download_bundle
from .runtime_probe import probe_tasks


def _completed_ids(state_path: Path) -> set[str]:
    if not state_path.is_file():
        return set()
    try:
        state = read_json(state_path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return set()
    tasks = state.get("stages", {}).get("probe", {}).get("tasks", {})
    return {
        object_id
        for object_id, record in tasks.items()
        if record.get("status") in {"completed", "cached"}
    }


def _wait_for_checkpoints(
    state_path: Path,
    *,
    minimum: int,
    process: subprocess.Popen[bytes],
    timeout_seconds: float,
) -> set[str]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = _completed_ids(state_path)
        if len(completed) >= minimum:
            return completed
        if process.poll() is not None:
            raise RuntimeError(
                "interruption probe exited before enough checkpoints existed"
            )
        time.sleep(0.05)
    raise TimeoutError("timed out waiting for durable probe checkpoints")


def run_runtime_gate(
    output_dir: str | Path,
    *,
    workers: int = 2,
    jobs: int = 8,
    delay_seconds: float = 0.35,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Prove cache reuse after SIGKILL and validate a self-contained bundle."""

    if os.name != "posix":
        raise RuntimeError("the deliberate SIGKILL gate requires a POSIX host")
    if workers < 1:
        raise ValueError("runtime gate workers must be positive")
    if jobs < max(4, workers * 2):
        raise ValueError("runtime gate needs at least two jobs per worker")
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    gate_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    root = destination / f"runtime-gate-{gate_id}"
    root.mkdir()
    run_dir = root / "run"
    cache_dir = root / "cache"
    state_path = run_dir / "state.json"
    command = [
        sys.executable,
        "-m",
        "ctsteg.digital_ad.runtime_probe",
        "--root",
        str(root),
        "--jobs",
        str(jobs),
        "--workers",
        str(workers),
        "--delay-seconds",
        str(delay_seconds),
    ]
    first_stdout_path = root / "first.stdout.log"
    first_stderr_path = root / "first.stderr.log"
    with first_stdout_path.open("wb") as first_stdout, first_stderr_path.open(
        "wb"
    ) as first_stderr:
        first = subprocess.Popen(
            command,
            stdout=first_stdout,
            stderr=first_stderr,
            start_new_session=True,
        )
        checkpoint_ids = _wait_for_checkpoints(
            state_path,
            minimum=max(1, workers),
            process=first,
            timeout_seconds=timeout_seconds,
        )
        os.killpg(first.pid, signal.SIGKILL)
        first.wait(timeout=10)
    store = ContentStore(cache_dir)
    completed_before = {
        object_id: hashlib.sha256(
            (store.object_path(object_id) / "COMPLETED.json").read_bytes()
        ).hexdigest()
        for object_id in checkpoint_ids
        if store.verify(object_id, deep=True).valid
    }
    if not completed_before:
        raise RuntimeError("SIGKILL occurred without a valid committed object")

    second_stdout_path = root / "resume.stdout.log"
    second_stderr_path = root / "resume.stderr.log"
    with second_stdout_path.open("wb") as second_stdout, second_stderr_path.open(
        "wb"
    ) as second_stderr:
        resumed = subprocess.run(
            command,
            stdout=second_stdout,
            stderr=second_stderr,
            check=False,
            timeout=timeout_seconds,
            start_new_session=True,
        )
    if resumed.returncode:
        raise RuntimeError(
            f"resumed runtime probe failed with exit code {resumed.returncode}"
        )
    summary = read_json(run_dir / "probe_summary.json")
    expected_ids = [task.object_id for task in probe_tasks(jobs, delay_seconds)]
    verifications = [store.verify(object_id, deep=True) for object_id in expected_ids]
    invalid = [
        item.object_id + ":" + str(item.reason)
        for item in verifications
        if not item.valid
    ]
    if invalid:
        raise RuntimeError(f"resumed cache contains invalid objects: {invalid}")
    unchanged = {
        object_id: (
            hashlib.sha256(
                (store.object_path(object_id) / "COMPLETED.json").read_bytes()
            ).hexdigest()
            == marker_hash
        )
        for object_id, marker_hash in completed_before.items()
    }
    if not all(unchanged.values()):
        raise RuntimeError("a committed pre-interruption object was overwritten")
    state = read_json(state_path)
    cache_hits = state["stages"]["probe"]["counts"]["cached"]
    if cache_hits < len(completed_before):
        raise RuntimeError("resume did not report every prior object as a cache hit")
    stale_locks = list((run_dir / "locks" / "stale").glob("*.json"))
    if not stale_locks:
        raise RuntimeError("the stale lock from SIGKILL was not preserved")
    bundle = create_download_bundle(
        run_dir,
        cache_dir=cache_dir,
        object_ids=expected_ids,
    )
    archive_check = verify_download_bundle(bundle["archive"])
    report = {
        "schema": 1,
        "gate": "parallel-cache-resume-export",
        "gate_id": gate_id,
        "runtime_gate_fingerprint": runtime_gate_fingerprint(),
        "status": "passed",
        "started_at": started_at,
        "host": platform.node(),
        "platform": platform.platform(),
        "workers": workers,
        "jobs": jobs,
        "interruption": {
            "signal": "SIGKILL",
            "first_exit_code": first.returncode,
            "valid_objects_before_restart": len(completed_before),
            "unchanged_after_restart": sum(unchanged.values()),
            "stale_lock_records": len(stale_locks),
        },
        "resume": {
            "exit_code": resumed.returncode,
            "cache_hits": cache_hits,
            "final_objects": len(verifications),
            "summary": summary,
        },
        "bundle": bundle,
        "archive_validation": archive_check,
        "output_dir": str(root),
        "completed_at": utc_now(),
    }
    atomic_write_json(root / "gate_report.json", report)
    atomic_write_json(destination / "latest_runtime_gate.json", report)
    return report
