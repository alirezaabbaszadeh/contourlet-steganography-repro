from __future__ import annotations

import io
from pathlib import Path
import subprocess
import unittest
from unittest import mock

from control.operations import collect_health_snapshot, execute_argv, main


class ServerControlOperationsCliTests(unittest.TestCase):
    def test_health_snapshot_contains_bounded_host_fields(self) -> None:
        snapshot = collect_health_snapshot()
        self.assertIsInstance(snapshot["hostname"], str)
        self.assertGreater(int(snapshot["logical_cpus"]), 0)
        self.assertGreater(int(snapshot["memory_total_bytes"]), 0)
        self.assertGreaterEqual(int(snapshot["memory_available_bytes"]), 0)
        self.assertGreater(int(snapshot["disk_total_bytes"]), 0)
        self.assertGreaterEqual(int(snapshot["disk_free_bytes"]), 0)
        self.assertGreaterEqual(int(snapshot["swap_total_bytes"]), 0)

    def test_execute_argv_never_uses_shell(self) -> None:
        completed = subprocess.CompletedProcess(["python3", "-V"], 0)
        with mock.patch("control.operations.subprocess.run", return_value=completed) as run:
            code = execute_argv(["python3", "-V"], timeout_seconds=30)
        self.assertEqual(code, 0)
        run.assert_called_once_with(
            ["python3", "-V"],
            check=False,
            shell=False,
            timeout=30,
        )

    def test_health_check_does_not_require_control_config(self) -> None:
        stdout = io.StringIO()
        with mock.patch("sys.stdout", stdout):
            code = main(
                [
                    "health_check",
                    "--checkout",
                    "/nonexistent/scientific-checkout",
                    "--config",
                    "/nonexistent/control.json",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn('"logical_cpus"', stdout.getvalue())

    def test_non_health_operation_requires_config_file(self) -> None:
        with self.assertRaisesRegex(ValueError, "control config is not readable"):
            main(
                [
                    "runtime_check",
                    "--checkout",
                    str(Path("/tmp/scientific-checkout")),
                    "--config",
                    "/nonexistent/control.json",
                ]
            )


if __name__ == "__main__":
    unittest.main()
