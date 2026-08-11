from __future__ import annotations

from pathlib import Path
import unittest

from control.operations import OperationError, build_scientific_argv, validate_config


CHECKOUT = Path("/srv/ctsteg/control/scientific-repo")


def config() -> dict[str, object]:
    return {
        "schema_version": 1,
        "bootstrap_config": "/etc/ctsteg-bootstrap.env",
        "plan": "/srv/ctsteg/final/finalized-plan.json",
        "runtime_bindings": "/srv/ctsteg/final/runtime-bindings.json",
        "science_ready_report": "/srv/ctsteg/final/science-ready.json",
        "output_root": "/srv/ctsteg/results",
        "cache_dir": "/srv/ctsteg/cache",
        "engineering_manifest": "/srv/ctsteg/final/engineering-pairs.json",
        "engineering_cache_dir": "/srv/ctsteg/engineering/cache",
        "engineering_run_dir": "/srv/ctsteg/engineering/run",
        "final_control_helper": "/usr/local/sbin/ctsteg-control-final",
    }


class ServerControlOperationsTests(unittest.TestCase):
    def test_config_paths_must_be_absolute(self) -> None:
        payload = config()
        payload["plan"] = "relative/plan.json"
        with self.assertRaisesRegex(OperationError, "absolute path"):
            validate_config(payload)

    def test_worker_benchmark_uses_fixed_required_paths(self) -> None:
        argv = build_scientific_argv(
            "worker_benchmark",
            config(),
            CHECKOUT,
            workers=7,
        )
        self.assertEqual(argv[0], "python3")
        self.assertEqual(
            argv[1],
            str(CHECKOUT / "scripts/5j/run_engineering_worker_trial.py"),
        )
        self.assertIn("--manifest", argv)
        self.assertIn("/srv/ctsteg/final/engineering-pairs.json", argv)
        self.assertIn("--runtime-bindings", argv)
        self.assertIn("--repository-root", argv)
        self.assertEqual(argv[-2:], ["--workers", "7"])

    def test_runtime_check_uses_fail_closed_preflight(self) -> None:
        argv = build_scientific_argv("runtime_check", config(), CHECKOUT)
        self.assertEqual(argv[1], str(CHECKOUT / "scripts/5j/run_research.py"))
        self.assertIn("--science-ready-report", argv)
        self.assertIn("--runtime-bindings", argv)
        self.assertIn("--json", argv)

    def test_research_status_uses_plan_and_cache(self) -> None:
        argv = build_scientific_argv("research_status", config(), CHECKOUT)
        self.assertEqual(argv[1], str(CHECKOUT / "scripts/5j/research_status.py"))
        self.assertIn("--plan", argv)
        self.assertIn("--cache-dir", argv)
        self.assertIn("--json", argv)

    def test_final_run_uses_only_fixed_privileged_helper(self) -> None:
        argv = build_scientific_argv("run_final_5j", config(), CHECKOUT)
        self.assertEqual(
            argv,
            ["sudo", "-n", "/usr/local/sbin/ctsteg-control-final", "start"],
        )

    def test_health_check_is_native_and_has_no_scientific_argv(self) -> None:
        with self.assertRaisesRegex(OperationError, "native operation"):
            build_scientific_argv("health_check", config(), CHECKOUT)


if __name__ == "__main__":
    unittest.main()
