from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from ctsteg.runtime import atomic_write_json
from ctsteg.runtime_monitor import (
    ResearchSampler,
    _boot_id,
    _resource_snapshot,
    build_progress,
    discover_research_run,
    format_status,
    run_monitor,
)


class RuntimeMonitorTests(unittest.TestCase):
    def _run_fixture(self, root: Path) -> tuple[Path, datetime]:
        output = root / "results"
        run_dir = output / "runs" / "fixture-run"
        run_dir.mkdir(parents=True)
        now = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
        atomic_write_json(
            run_dir / "plan.json",
            {"schema": 1, "run_id": "fixture-run"},
        )
        atomic_write_json(
            run_dir / "runtime_context.json",
            {
                "schema": 1,
                "run_id": "fixture-run",
                "output_root": str(output),
                "cache_dir": str(root / "cache"),
                "workers": 8,
            },
        )
        embedding_tasks = {
            f"{index:064x}": {
                "kind": "digital_embedding",
                "status": "cached",
                "resource": {"wall_seconds": 10.0},
            }
            for index in range(1, 17)
        }
        evaluation_tasks = {
            f"{index:064x}": {
                "kind": "digital_channel_evaluation",
                "status": "completed" if offset < 4 else "pending",
                **(
                    {"resource": {"wall_seconds": 20.0}}
                    if offset < 4
                    else {}
                ),
            }
            for offset, index in enumerate(range(100, 148))
        }
        atomic_write_json(
            run_dir / "state.json",
            {
                "schema": 1,
                "stages": {
                    "01_embeddings_and_clean": {
                        "status": "complete",
                        "counts": {
                            "cached": 16,
                            "completed": 0,
                            "failed": 0,
                            "pending": 0,
                        },
                        "tasks": embedding_tasks,
                    },
                    "02_core_channels": {
                        "status": "running",
                        "counts": {
                            "cached": 0,
                            "completed": 4,
                            "failed": 0,
                            "pending": 44,
                        },
                        "tasks": evaluation_tasks,
                    },
                },
            },
        )
        events = run_dir / "events"
        events.mkdir()
        started = now - timedelta(seconds=100)
        atomic_write_json(
            events / "000001-start.json",
            {
                "schema": 1,
                "sequence": 1,
                "recorded_at": started.isoformat().replace("+00:00", "Z"),
                "event": "stage_started",
                "stage": "02_core_channels",
            },
        )
        for sequence in range(2, 6):
            atomic_write_json(
                events / f"{sequence:06d}-finished.json",
                {
                    "schema": 1,
                    "sequence": sequence,
                    "recorded_at": (
                        started + timedelta(seconds=sequence * 10)
                    ).isoformat().replace("+00:00", "Z"),
                    "event": "task_finished",
                    "stage": "02_core_channels",
                    "status": "completed",
                },
            )
        return run_dir, now

    def test_progress_uses_live_throughput_for_eta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, now = self._run_fixture(Path(temporary))
            progress = build_progress(run_dir, now=now)
            self.assertEqual(progress["current_stage"], "02_core_channels")
            self.assertEqual(progress["mandatory"]["completed"], 20)
            self.assertEqual(
                progress["throughput"]["basis"],
                "live_stage_throughput",
            )
            self.assertAlmostEqual(
                progress["throughput"]["tasks_per_hour"],
                144.0,
            )
            self.assertAlmostEqual(
                progress["eta"]["mandatory_seconds"],
                1100.0,
            )
            self.assertIsNone(progress["eta"]["selected_seconds"])
            self.assertAlmostEqual(
                progress["eta"]["maximum_seconds"],
                1160.0,
            )

    def test_discovery_and_monitor_snapshot_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir, _now = self._run_fixture(root)
            atomic_write_json(
                run_dir / "run.lock",
                {
                    "schema": 1,
                    "pid": os.getpid(),
                    "host": socket.gethostname(),
                    "boot_id": _boot_id(),
                },
            )
            discovered = discover_research_run(root / "results")
            self.assertIsNotNone(discovered)
            assert discovered is not None
            self.assertTrue(discovered["active"])
            sampler = ResearchSampler(output_root=root / "results")
            first = sampler.sample()
            second = sampler.sample()
            self.assertEqual(first["run_id"], "fixture-run")
            self.assertIn("process_tree", second["resources"])
            self.assertIn("algorithm_percent_of_allocated", second["resources"]["cpu"])
            status_dir = root / "status"
            report = run_monitor(
                output_root=root / "results",
                status_dir=status_dir,
                interval_seconds=0.01,
                once=True,
            )
            self.assertEqual(report["run_id"], "fixture-run")
            self.assertNotIn("_counters", report)
            latest = json.loads(
                (status_dir / "latest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(latest["schema"], 1)
            self.assertEqual(
                len(
                    (status_dir / "samples.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ),
                1,
            )
            rendered = format_status(latest)
            self.assertIn("fixture-run", rendered)
            self.assertIn("ETA:", rendered)

    def test_resource_assessment_compares_against_worker_capacity(self) -> None:
        previous = {
            "_counters": {
                "boot_id": "fixture-boot",
                "system_cpu": {
                    "total": 1000,
                    "idle": 500,
                    "iowait": 50,
                },
                "process": {
                    "ticks": 100,
                    "read_bytes": 1000,
                    "write_bytes": 2000,
                },
            }
        }
        current_process = {
            "ticks": 100 + int(os.sysconf("SC_CLK_TCK")) * 8,
            "rss_bytes": 8 * 1024**3,
            "threads": 8,
            "read_bytes": 1000 + 1024**2,
            "write_bytes": 2000 + 2 * 1024**2,
            "processes": 9,
        }
        with (
            patch(
                "ctsteg.runtime_monitor._system_cpu_counters",
                return_value={"total": 2000, "idle": 600, "iowait": 70},
            ),
            patch(
                "ctsteg.runtime_monitor._process_tree_counters",
                return_value=current_process,
            ),
            patch(
                "ctsteg.runtime_monitor._memory_counters",
                return_value={
                    "total": 64 * 1024**3,
                    "available": 32 * 1024**3,
                },
            ),
            patch(
                "ctsteg.runtime_monitor._disk_usage",
                return_value={
                    "path": "/fixture",
                    "total_bytes": 500 * 1024**3,
                    "free_bytes": 400 * 1024**3,
                },
            ),
            patch(
                "ctsteg.runtime_monitor._load_average",
                return_value={"one": 8.0, "five": 7.0, "fifteen": 6.0},
            ),
            patch("ctsteg.runtime_monitor._boot_id", return_value="fixture-boot"),
            patch("ctsteg.runtime_monitor.os.cpu_count", return_value=32),
        ):
            resource, counters = _resource_snapshot(
                root_pid=123,
                workers=8,
                output_root=Path("/fixture"),
                cache_dir=Path("/fixture/cache"),
                previous=previous,
                elapsed=1.0,
            )
        self.assertEqual(resource["assessment"], "using_allocated_cpu")
        self.assertAlmostEqual(
            resource["cpu"]["algorithm_percent_of_allocated"],
            100.0,
        )
        self.assertAlmostEqual(
            resource["cpu"]["algorithm_percent_of_host"],
            25.0,
        )
        self.assertAlmostEqual(
            resource["io"]["read_bytes_per_second"],
            1024**2,
        )
        self.assertEqual(counters["process"], current_process)


if __name__ == "__main__":
    unittest.main()
