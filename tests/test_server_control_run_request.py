from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from control.run_request import RequestRunError, resolve_request_path, run_process


class ServerControlRunRequestTests(unittest.TestCase):
    def test_resolve_request_path_accepts_json_under_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            requests.mkdir()
            expected = requests / "health.json"
            expected.write_text("{}", encoding="utf-8")
            self.assertEqual(
                resolve_request_path(root, "requests/health.json"),
                expected.resolve(),
            )

    def test_resolve_request_path_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requests").mkdir()
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RequestRunError, "requests directory"):
                resolve_request_path(root, "requests/../outside.json")

    def test_resolve_request_path_rejects_non_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requests = root / "requests"
            requests.mkdir()
            path = requests / "command.sh"
            path.write_text("echo nope", encoding="utf-8")
            with self.assertRaisesRegex(RequestRunError, "JSON request"):
                resolve_request_path(root, "requests/command.sh")

    def test_run_process_never_uses_shell(self) -> None:
        completed = subprocess.CompletedProcess(["git", "--version"], 0)
        with mock.patch("control.run_request.subprocess.run", return_value=completed) as run:
            result = run_process(["git", "--version"], timeout_seconds=30)
        self.assertIs(result, completed)
        run.assert_called_once_with(
            ["git", "--version"],
            check=False,
            shell=False,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()
