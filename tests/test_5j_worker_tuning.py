from __future__ import annotations

import json
from pathlib import Path
import unittest

from ctsteg.digital_ad.worker_tuning_5j import (
    GIB,
    WorkerTuningError,
    load_config,
    parse_trial,
    recommend,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/5j/worker_autotune_v1.json"
TASK_HASH = "a" * 64


def trial(
    workers: int,
    *,
    throughput: float,
    cpu: float = 85.0,
    iowait: float = 2.0,
    available_gib: float = 20.0,
    p95_rss_gib: float = 0.5,
    operational_failures: int = 0,
    oom_events: int = 0,
    swap_io_bytes: int = 0,
):
    return parse_trial(
        {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "status": "complete",
            "workers": workers,
            "task_selection_sha256": TASK_HASH,
            "tasks": {
                "planned": 160,
                "completed": 160 - operational_failures,
                "operational_failures": operational_failures,
                "oom_events": oom_events,
            },
            "timing": {
                "wall_seconds": 600.0,
                "combined_tasks_per_hour": throughput,
            },
            "cpu": {
                "mean_busy_percent": cpu,
                "p95_iowait_percent": iowait,
            },
            "memory": {
                "minimum_available_bytes": int(available_gib * GIB),
                "p95_worker_rss_bytes": int(p95_rss_gib * GIB),
                "max_worker_rss_bytes": int((p95_rss_gib + 0.1) * GIB),
            },
            "swap": {
                "io_bytes": swap_io_bytes,
                "maximum_used_bytes": 0,
            },
        }
    )


class WorkerTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG)

    def test_first_trial_is_always_sixteen_workers(self) -> None:
        decision = recommend(self.config, [])
        self.assertEqual(decision["action"], "test")
        self.assertEqual(decision["workers"], 16)

    def test_unsafe_sixteen_workers_falls_back_to_twelve(self) -> None:
        decision = recommend(
            self.config,
            [trial(16, throughput=100.0, swap_io_bytes=4096)],
        )
        self.assertEqual(decision["action"], "test")
        self.assertEqual(decision["workers"], 12)
        self.assertIn("swap_io", decision["unsafe_reasons"])

    def test_stable_sixteen_with_headroom_tests_twenty(self) -> None:
        decision = recommend(
            self.config,
            [trial(16, throughput=100.0)],
        )
        self.assertEqual(decision["action"], "test")
        self.assertEqual(decision["workers"], 20)
        self.assertGreaterEqual(decision["projected_headroom_gib"], 10.0)

    def test_small_gain_at_twenty_stops_and_selects_best_stable(self) -> None:
        trials = [
            trial(16, throughput=100.0),
            trial(20, throughput=103.0),
        ]
        decision = recommend(self.config, trials)
        self.assertEqual(decision["action"], "accept")
        self.assertEqual(decision["selected_workers"], 20)
        self.assertEqual(
            decision["reason"],
            "incremental_throughput_gain_too_small",
        )

    def test_meaningful_twenty_worker_gain_tests_twenty_four(self) -> None:
        trials = [
            trial(16, throughput=100.0),
            trial(20, throughput=110.0),
        ]
        decision = recommend(self.config, trials)
        self.assertEqual(decision["action"], "test")
        self.assertEqual(decision["workers"], 24)

    def test_stable_fallback_is_accepted_without_scaling_back_up(self) -> None:
        trials = [
            trial(16, throughput=100.0, oom_events=1),
            trial(12, throughput=90.0),
        ]
        decision = recommend(self.config, trials)
        self.assertEqual(decision["action"], "accept")
        self.assertEqual(decision["selected_workers"], 12)

    def test_low_memory_blocks_scale_up(self) -> None:
        decision = recommend(
            self.config,
            [
                trial(
                    16,
                    throughput=100.0,
                    available_gib=11.0,
                    p95_rss_gib=1.0,
                )
            ],
        )
        self.assertEqual(decision["action"], "accept")
        self.assertEqual(decision["selected_workers"], 16)
        self.assertEqual(
            decision["reason"],
            "projected_memory_headroom_too_low",
        )

    def test_trial_hash_mismatch_is_rejected(self) -> None:
        payload = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "status": "complete",
            "workers": 16,
            "task_selection_sha256": TASK_HASH,
            "tasks": {
                "planned": 160,
                "completed": 160,
                "operational_failures": 0,
                "oom_events": 0,
            },
            "timing": {
                "wall_seconds": 600.0,
                "combined_tasks_per_hour": 100.0,
            },
            "cpu": {
                "mean_busy_percent": 85.0,
                "p95_iowait_percent": 2.0,
            },
            "memory": {
                "minimum_available_bytes": 20 * GIB,
                "p95_worker_rss_bytes": GIB,
                "max_worker_rss_bytes": GIB,
            },
            "swap": {"io_bytes": 0, "maximum_used_bytes": 0},
            "trial_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(WorkerTuningError, "trial SHA-256"):
            parse_trial(payload)

    def test_config_is_json_serializable_and_frozen(self) -> None:
        encoded = json.dumps(self.config, sort_keys=True)
        self.assertIn("locked_before_performance_results", encoded)


if __name__ == "__main__":
    unittest.main()
