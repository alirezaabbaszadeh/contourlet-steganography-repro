from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from PIL import Image

from scripts import download_usc_sipi, server_preflight


class _Response:
    def __init__(self, payload: bytes = b"x") -> None:
        self.payload = payload
        self.status = 206

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return self.payload

    def geturl(self) -> str:
        return "https://fixture.invalid/final"


def _tiff_payload() -> bytes:
    output = BytesIO()
    Image.new("L", (8, 8), color=127).save(output, format="TIFF")
    return output.getvalue()


class ServerResilienceTests(unittest.TestCase):
    @property
    def repository_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _run_retry_script(self, body: str) -> subprocess.CompletedProcess[str]:
        library = shlex.quote(
            str(self.repository_root / "scripts" / "bootstrap_retry.sh")
        )
        script = (
            f"source {library}\n"
            "CTSTEG_RETRY_INITIAL_SECONDS=0\n"
            "CTSTEG_RETRY_MAX_SECONDS=0\n"
            f"{body}\n"
        )
        return subprocess.run(
            ["bash", "-c", script],
            cwd=self.repository_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_shell_retry_recovers_after_two_transient_failures(self) -> None:
        completed = self._run_retry_script(
            """
count=0
flaky() {
  count=$((count + 1))
  if ((count < 3)); then
    return 75
  fi
}
ctsteg_retry_command_n 5 fixture flaky
printf 'count=%d\\n' "${count}"
"""
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("count=3", completed.stdout)
        self.assertIn("recovered on attempt 3/5", completed.stdout)
        self.assertEqual(completed.stdout.count("fixture: attempt"), 3)

    def test_shell_retry_exhausts_and_preserves_last_exit_code(self) -> None:
        completed = self._run_retry_script(
            """
always_fails() {
  return 7
}
ctsteg_retry_command_n 3 fixture always_fails
"""
        )
        self.assertEqual(completed.returncode, 7)
        combined = completed.stdout + completed.stderr
        self.assertEqual(combined.count("fixture: attempt"), 3)
        self.assertIn("exhausted after 3 attempts (exit 7)", combined)

    def test_shell_retry_rejects_an_unbounded_attempt_count(self) -> None:
        completed = self._run_retry_script(
            "ctsteg_retry_command_n 21 fixture true"
        )
        self.assertEqual(completed.returncode, 64)
        self.assertIn("must be an integer from 1 through 20", completed.stderr)

    def test_installed_bootstrap_layout_resolves_libexec_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sbin = root / "sbin"
            libexec = root / "libexec"
            sbin.mkdir()
            libexec.mkdir()
            source_scripts = self.repository_root / "scripts"
            bootstrap = sbin / "ctsteg-bootstrap"
            shutil.copy2(
                source_scripts / "bootstrap_ubuntu_server.sh",
                bootstrap,
            )
            shutil.copy2(source_scripts / "bootstrap_retry.sh", libexec)
            shutil.copy2(source_scripts / "server_preflight.py", libexec)
            config = root / "server.env"
            config.write_text(
                "\n".join(
                    (
                        "CTSTEG_ALLOW_FLOATING_GIT_REF=1",
                        "CTSTEG_RUN_RUNTIME_GATE=0",
                        "CTSTEG_INSTALL_MATLAB=0",
                        "CTSTEG_INSTALL_CONTOURLET=0",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(bootstrap), "--verify", "--config", str(config)],
                cwd=root,
                env={
                    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
                    "CTSTEG_BOOTSTRAP_LIBEXEC_DIR": str(libexec),
                },
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertNotIn("server_preflight.py is missing", completed.stderr)
        self.assertNotIn("bootstrap retry library is missing", completed.stderr)

    def test_preflight_network_probe_recovers_and_records_attempts(self) -> None:
        delays: list[float] = []
        with patch(
            "scripts.server_preflight.urlopen",
            side_effect=[URLError("temporary DNS failure"), _Response()],
        ):
            name, result = server_preflight._network_target_facts(
                "fixture",
                "https://fixture.invalid",
                timeout=1.0,
                attempts=4,
                initial_backoff_seconds=0.25,
                sleep=delays.append,
            )
        self.assertEqual(name, "fixture")
        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(len(result["prior_errors"]), 1)
        self.assertEqual(delays, [0.25])

    def test_preflight_network_probe_records_bounded_exhaustion(self) -> None:
        with patch(
            "scripts.server_preflight.urlopen",
            side_effect=URLError("offline"),
        ):
            _name, result = server_preflight._network_target_facts(
                "fixture",
                "https://fixture.invalid",
                timeout=1.0,
                attempts=3,
                initial_backoff_seconds=0.0,
                sleep=lambda _delay: None,
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(len(result["errors"]), 3)

    def test_preflight_exit_class_separates_transient_and_hard_failures(
        self,
    ) -> None:
        network = ["github", "mathworks"]
        network_blocker = "outbound HTTPS failed for: github, mathworks"
        self.assertEqual(
            server_preflight.classify_failure([], []),
            "ready",
        )
        self.assertEqual(
            server_preflight.classify_failure([network_blocker], network),
            "transient_network",
        )
        self.assertEqual(
            server_preflight.classify_failure(
                ["CPU does not expose AVX2", network_blocker],
                network,
            ),
            "hard_blocked",
        )

    def test_image_download_recovers_from_network_and_payload_failures(
        self,
    ) -> None:
        delays: list[float] = []
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.download_usc_sipi._download_payload",
            side_effect=[
                URLError("temporary connection failure"),
                b"not an image",
                _tiff_payload(),
            ],
        ) as fetch:
            destination = Path(temporary)
            download_usc_sipi.download(
                "fixture",
                "fixture-id",
                destination,
                attempts=4,
                initial_backoff_seconds=0.0,
                maximum_backoff_seconds=0.0,
                timeout_seconds=1.0,
                sleep=delays.append,
            )
            output = destination / "fixture.tiff"
            self.assertTrue(output.is_file())
            self.assertTrue(download_usc_sipi._valid_image(output))
            self.assertEqual(fetch.call_count, 3)
            self.assertEqual(delays, [0.0, 0.0])

    def test_permanent_http_error_is_not_retried(self) -> None:
        error = HTTPError(
            "https://fixture.invalid",
            404,
            "not found",
            hdrs=None,
            fp=None,
        )
        with tempfile.TemporaryDirectory() as temporary, patch(
            "scripts.download_usc_sipi._download_payload",
            side_effect=error,
        ) as fetch:
            with self.assertRaises(HTTPError):
                download_usc_sipi.download(
                    "fixture",
                    "fixture-id",
                    Path(temporary),
                    attempts=6,
                    initial_backoff_seconds=0.0,
                    maximum_backoff_seconds=0.0,
                    timeout_seconds=1.0,
                    sleep=lambda _delay: self.fail(
                        "permanent HTTP errors must not sleep or retry"
                    ),
                )
        self.assertEqual(fetch.call_count, 1)

    def test_systemd_retries_only_retryable_service_failures(self) -> None:
        bootstrap = (
            self.repository_root
            / "deploy"
            / "systemd"
            / "ctsteg-bootstrap.service"
        ).read_text(encoding="utf-8")
        research = (
            self.repository_root
            / "deploy"
            / "systemd"
            / "ctsteg-research@.service"
        ).read_text(encoding="utf-8")
        self.assertIn("Restart=on-failure", bootstrap)
        self.assertIn("RestartPreventExitStatus=2 64", bootstrap)
        self.assertIn("StartLimitBurst=12", bootstrap)
        self.assertIn("Restart=on-failure", research)
        self.assertIn("RestartPreventExitStatus=2 64", research)
        self.assertIn("StartLimitBurst=12", research)


if __name__ == "__main__":
    unittest.main()
