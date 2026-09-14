"""Subprocess helper used by the deliberate interruption runtime gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ctsteg.runtime import (
    DurableTask,
    DurableTaskRunner,
    RunLock,
    atomic_write_json,
    content_object_id,
)

from .research_runtime import worker_execute_task


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--delay-seconds", type=float, default=0.35)
    return parser


def probe_tasks(job_count: int, delay_seconds: float) -> list[DurableTask]:
    if job_count < 4:
        raise ValueError("runtime probe requires at least four jobs")
    if delay_seconds <= 0:
        raise ValueError("runtime probe delay must be positive")
    tasks: list[DurableTask] = []
    for index in range(job_count):
        material = {
            "schema": 1,
            "probe_version": "runtime-interruption-v1",
            "probe_index": index,
            "probe_value": f"durable-{index:04d}",
            "delay_seconds": delay_seconds,
        }
        tasks.append(
            DurableTask(
                object_id=content_object_id("runtime_probe", material),
                kind="runtime_probe",
                label=f"probe-{index:04d}",
                payload={
                    "probe_index": index,
                    "probe_value": material["probe_value"],
                    "delay_seconds": delay_seconds,
                },
            )
        )
    return tasks


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    run_dir = root / "run"
    cache_dir = root / "cache"
    tasks = probe_tasks(args.jobs, args.delay_seconds)
    with RunLock(run_dir):
        runner = DurableTaskRunner(
            cache_dir=cache_dir,
            run_dir=run_dir,
            workers=args.workers,
        )
        result = runner.run(
            tasks,
            stage="probe",
            worker=worker_execute_task,
        )
        summary = {
            "schema": 1,
            "status": "complete" if not result["failed"] else "failed",
            "job_count": len(tasks),
            "object_ids": [task.object_id for task in tasks],
            "stage": {
                key: value for key, value in result.items() if key != "records"
            },
        }
        atomic_write_json(run_dir / "probe_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
