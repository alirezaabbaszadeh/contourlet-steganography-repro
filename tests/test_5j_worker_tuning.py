from __future__ import annotations

import json
from pathlib import Path
import unittest

from ctsteg.digital_ad.worker_tuning_5j import (
    GIB, WorkerTuningError, load_config, parse_trial, recommend
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/5j/worker_autotune_v1.json"
TASK_HASH = "a" * 64


def trial(workers: int, *, throughput: float, cpu: float = 85.0, iowait: float = 2.0,
          available_gib: float = 8.0, p95_rss_gib: float = 0.75,
          free_storage_gib: float = 60.0, operational_failures: int = 0,
          oom_events: int = 0, swap_io_bytes: int = 0):
    return parse_trial({
        "schema_version": 1, "protocol_id": "FINAL-5J-v1", "status": "complete",
        "workers": workers, "task_selection_sha256": TASK_HASH,
        "tasks": {"planned": 160, "completed": 160 - operational_failures,
                  "operational_failures": operational_failures, "oom_events": oom_events},
        "timing": {"wall_seconds": 600.0, "combined_tasks_per_hour": throughput},
        "cpu": {"mean_busy_percent": cpu, "p95_iowait_percent": iowait},
        "memory": {"minimum_available_bytes": int(available_gib * GIB),
                   "p95_worker_rss_bytes": int(p95_rss_gib * GIB),
                   "max_worker_rss_bytes": int((p95_rss_gib + 0.1) * GIB)},
        "swap": {"io_bytes": swap_io_bytes, "maximum_used_bytes": 0},
        "storage": {"minimum_free_bytes": int(free_storage_gib * GIB)},
    })


class WorkerTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG)

    def test_profile_is_8core_16g_100gb_v2(self) -> None:
        target = self.config["target_host"]
        self.assertEqual(self.config["profile_id"], "ferdowsi-8c16g-100gb-v2")
        self.assertEqual(target["logical_cpus"], 8)
        self.assertEqual(target["memory_gib"], 16)
        self.assertEqual(target["storage_gb_decimal"], 100)
        self.assertEqual(target["reserved_cpus"], 1)
        self.assertEqual(self.config["maximum_workers"], 7)

    def test_first_trial_is_four_workers(self) -> None:
        decision = recommend(self.config, [])
        self.assertEqual((decision["action"], decision["workers"]), ("test", 4))

    def test_unsafe_four_falls_back_to_two(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0, swap_io_bytes=4096)])
        self.assertEqual(decision["workers"], 2)
        self.assertIn("swap_io", decision["unsafe_reasons"])

    def test_stable_four_with_headroom_tests_six(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0)])
        self.assertEqual((decision["action"], decision["workers"]), ("test", 6))
        self.assertGreaterEqual(decision["projected_headroom_gib"], 3.5)

    def test_low_memory_keeps_four(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0, available_gib=4.6, p95_rss_gib=0.75)])
        self.assertEqual(decision["selected_workers"], 4)
        self.assertEqual(decision["reason"], "projected_memory_headroom_too_low")

    def test_storage_floor_makes_trial_unsafe(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0, free_storage_gib=20.0)])
        self.assertEqual(decision["workers"], 2)
        self.assertIn("storage_floor", decision["unsafe_reasons"])

    def test_six_requires_meaningful_gain_before_seven(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0), trial(6, throughput=105.0)])
        self.assertEqual(decision["selected_workers"], 4)
        self.assertEqual(decision["reason"], "gain_is_insufficient_for_6_workers")
        decision = recommend(self.config, [trial(4, throughput=100.0), trial(6, throughput=110.0)])
        self.assertEqual((decision["action"], decision["workers"]), ("test", 7))

    def test_seven_requires_incremental_gain(self) -> None:
        decision = recommend(self.config, [
            trial(4, throughput=100.0), trial(6, throughput=110.0), trial(7, throughput=113.0)
        ])
        self.assertEqual(decision["selected_workers"], 6)
        self.assertEqual(decision["reason"], "gain_is_insufficient_for_7_workers")
        decision = recommend(self.config, [
            trial(4, throughput=100.0), trial(6, throughput=110.0), trial(7, throughput=117.0)
        ])
        self.assertEqual(decision["selected_workers"], 7)
        self.assertEqual(decision["reason"], "seven_worker_gain_accepted")

    def test_unsafe_seven_retains_best_stable_lower_candidate(self) -> None:
        decision = recommend(self.config, [
            trial(4, throughput=100.0), trial(6, throughput=110.0),
            trial(7, throughput=118.0, swap_io_bytes=4096)
        ])
        self.assertEqual(decision["action"], "stop")
        self.assertEqual(decision["selected_workers"], 6)

    def test_stable_fallback_is_accepted(self) -> None:
        decision = recommend(self.config, [trial(4, throughput=100.0, oom_events=1), trial(2, throughput=80.0)])
        self.assertEqual(decision["selected_workers"], 2)

    def test_trial_hash_mismatch_is_rejected(self) -> None:
        payload = {
            "schema_version": 1, "protocol_id": "FINAL-5J-v1", "status": "complete",
            "workers": 4, "task_selection_sha256": TASK_HASH,
            "tasks": {"planned": 160, "completed": 160, "operational_failures": 0, "oom_events": 0},
            "timing": {"wall_seconds": 600.0, "combined_tasks_per_hour": 100.0},
            "cpu": {"mean_busy_percent": 85.0, "p95_iowait_percent": 2.0},
            "memory": {"minimum_available_bytes": 8 * GIB, "p95_worker_rss_bytes": GIB, "max_worker_rss_bytes": GIB},
            "swap": {"io_bytes": 0, "maximum_used_bytes": 0},
            "storage": {"minimum_free_bytes": 60 * GIB},
            "trial_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(WorkerTuningError, "trial SHA-256"):
            parse_trial(payload)

    def test_config_is_json_serializable_and_frozen(self) -> None:
        self.assertIn("locked_before_performance_results", json.dumps(self.config, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
