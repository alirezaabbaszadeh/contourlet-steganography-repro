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
    load_one: float = 16.0,
    available_gib: float = 50.0,
    p95_rss_gib: float = 0.75,
    free_storage_gib: float = 60.0,
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
                "maximum_load_one": load_one,
            },
            "memory": {
                "minimum_available_bytes": int(available_gib * GIB),
                "p95_worker_rss_bytes": int(p95_rss_gib * GIB),
                "max_worker_rss_bytes": int((p95_rss_gib + 0.1) * GIB),
            },
            "swap": {"io_bytes": swap_io_bytes, "maximum_used_bytes": 0},
            "storage": {"minimum_free_bytes": int(free_storage_gib * GIB)},
        }
    )


class WorkerTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG)

    def test_profile_is_32core_64g_100gb(self) -> None:
        target = self.config["target_host"]
        self.assertEqual(self.config["profile_id"], "ferdowsi-32c64g-100gb-v1")
        self.assertEqual(target["logical_cpus"], 32)
        self.assertEqual(target["memory_gib"], 64)
        self.assertEqual(target["storage_gb_decimal"], 100)
        self.assertEqual(target["reserved_cpus"], 3)
        self.assertEqual(self.config["maximum_workers"], 29)
        self.assertEqual(32 - self.config["maximum_workers"], 3)

    def test_fixed_cpu_busy_gate_is_forbidden(self) -> None:
        self.assertNotIn(
            "minimum_mean_cpu_busy_percent",
            self.config["scale_up_thresholds"],
        )

    def test_first_trial_is_sixteen_workers(self) -> None:
        decision = recommend(self.config, [])
        self.assertEqual((decision["action"], decision["workers"]), ("test", 16))

    def test_unsafe_sixteen_falls_back_to_twelve(self) -> None:
        decision = recommend(
            self.config,
            [trial(16, throughput=160.0, swap_io_bytes=4096)],
        )
        self.assertEqual(decision["workers"], 12)
        self.assertIn("swap_io", decision["unsafe_reasons"])

    def test_unsafe_twelve_falls_back_to_eight(self) -> None:
        decision = recommend(
            self.config,
            [
                trial(16, throughput=160.0, oom_events=1),
                trial(12, throughput=140.0, swap_io_bytes=4096),
            ],
        )
        self.assertEqual(decision["workers"], 8)

    def test_stable_sixteen_with_headroom_tests_twenty(self) -> None:
        decision = recommend(self.config, [trial(16, throughput=160.0)])
        self.assertEqual((decision["action"], decision["workers"]), ("test", 20))
        self.assertGreaterEqual(decision["projected_headroom_gib"], 10.0)

    def test_low_memory_keeps_sixteen(self) -> None:
        decision = recommend(
            self.config,
            [trial(16, throughput=160.0, available_gib=12.0, p95_rss_gib=0.75)],
        )
        self.assertEqual(decision["selected_workers"], 16)
        self.assertEqual(decision["reason"], "projected_memory_headroom_too_low")

    def test_marginal_throughput_not_cpu_percent_controls_scale_up(self) -> None:
        low_gain = recommend(
            self.config,
            [
                trial(16, throughput=160.0, cpu=99.0),
                trial(20, throughput=170.0, cpu=99.0),
            ],
        )
        self.assertEqual(low_gain["selected_workers"], 16)
        self.assertEqual(low_gain["reason"], "marginal_throughput_gain_is_insufficient")

        enough_gain = recommend(
            self.config,
            [
                trial(16, throughput=160.0, cpu=15.0),
                trial(20, throughput=176.0, cpu=15.0),
            ],
        )
        self.assertEqual((enough_gain["action"], enough_gain["workers"]), ("test", 24))

    def test_stable_ladder_can_reach_twenty_nine(self) -> None:
        decision = recommend(
            self.config,
            [
                trial(16, throughput=160.0),
                trial(20, throughput=180.0),
                trial(24, throughput=200.0),
                trial(27, throughput=215.0),
                trial(29, throughput=226.0),
            ],
        )
        self.assertEqual(decision["action"], "accept")
        self.assertEqual(decision["selected_workers"], 29)
        self.assertEqual(decision["reason"], "maximum_worker_candidate_is_stable")

    def test_unsafe_scale_up_reverts_to_best_stable_candidate(self) -> None:
        decision = recommend(
            self.config,
            [
                trial(16, throughput=160.0),
                trial(20, throughput=180.0),
                trial(24, throughput=200.0, swap_io_bytes=4096),
            ],
        )
        self.assertEqual(decision["action"], "accept")
        self.assertEqual(decision["selected_workers"], 20)

    def test_stable_fallback_is_accepted(self) -> None:
        decision = recommend(
            self.config,
            [trial(16, throughput=160.0, oom_events=1), trial(12, throughput=130.0)],
        )
        self.assertEqual(decision["selected_workers"], 12)

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
            "timing": {"wall_seconds": 600.0, "combined_tasks_per_hour": 160.0},
            "cpu": {
                "mean_busy_percent": 50.0,
                "p95_iowait_percent": 2.0,
                "maximum_load_one": 16.0,
            },
            "memory": {
                "minimum_available_bytes": 48 * GIB,
                "p95_worker_rss_bytes": GIB,
                "max_worker_rss_bytes": GIB,
            },
            "swap": {"io_bytes": 0, "maximum_used_bytes": 0},
            "storage": {"minimum_free_bytes": 60 * GIB},
            "trial_sha256": "0" * 64,
        }
        with self.assertRaisesRegex(WorkerTuningError, "trial SHA-256"):
            parse_trial(payload)

    def test_config_is_json_serializable_and_frozen(self) -> None:
        serialized = json.dumps(self.config, sort_keys=True)
        self.assertIn("locked_before_performance_results", serialized)
        self.assertIn("minimum_marginal_throughput_efficiency_ratio", serialized)


if __name__ == "__main__":
    unittest.main()
