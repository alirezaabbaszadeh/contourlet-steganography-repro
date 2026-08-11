from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from control.head_request import HeadRequestError, changed_request_paths


class ServerControlHeadRequestTests(unittest.TestCase):
    def test_accepts_exactly_one_request_json(self) -> None:
        completed = subprocess.CompletedProcess(
            ["git"],
            0,
            stdout=b"requests/2026-08-10-health.json\0",
        )
        with mock.patch("control.head_request.subprocess.run", return_value=completed) as run:
            paths = changed_request_paths(Path("/repo"), "a" * 40)
        self.assertEqual(paths, ["requests/2026-08-10-health.json"])
        call = run.call_args
        self.assertEqual(call.kwargs["shell"], False)
        self.assertEqual(call.kwargs["capture_output"], True)
        self.assertIn("-z", call.args[0])

    def test_rejects_multiple_request_files(self) -> None:
        completed = subprocess.CompletedProcess(
            ["git"],
            0,
            stdout=b"requests/a.json\0requests/b.json\0",
        )
        with mock.patch("control.head_request.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(HeadRequestError, "exactly one"):
                changed_request_paths(Path("/repo"), "b" * 40)

    def test_rejects_non_request_file_even_if_git_reports_it(self) -> None:
        completed = subprocess.CompletedProcess(
            ["git"],
            0,
            stdout=b"control/request.py\0",
        )
        with mock.patch("control.head_request.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(HeadRequestError, "exactly one"):
                changed_request_paths(Path("/repo"), "c" * 40)

    def test_rejects_non_json_under_requests(self) -> None:
        completed = subprocess.CompletedProcess(
            ["git"],
            0,
            stdout=b"requests/command.sh\0",
        )
        with mock.patch("control.head_request.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(HeadRequestError, "exactly one"):
                changed_request_paths(Path("/repo"), "d" * 40)

    def test_git_failure_is_fail_closed(self) -> None:
        completed = subprocess.CompletedProcess(["git"], 128, stdout=b"", stderr=b"bad")
        with mock.patch("control.head_request.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(HeadRequestError, "git diff-tree failed"):
                changed_request_paths(Path("/repo"), "e" * 40)


if __name__ == "__main__":
    unittest.main()
