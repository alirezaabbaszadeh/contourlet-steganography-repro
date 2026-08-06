from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/5j/build_final_archive.py"
VERIFY = ROOT / "scripts/5j/verify_final_archive.py"


class Final5JArchiveTests(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _build(self, root: Path, output: Path) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["SOURCE_DATE_EPOCH"] = "1786056240"
        return subprocess.run(
            [
                sys.executable,
                str(BUILD),
                "--include",
                f"results={root / 'results'}",
                "--include",
                f"paper={root / 'paper'}",
                "--output",
                str(output),
                "--run-id",
                "5j-fixture-run",
                "--plan-id",
                "f" * 64,
                "--classification",
                "public",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

    def test_archive_is_deterministic_and_independently_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "paper").mkdir()
            (root / "results" / "analysis.json").write_text(
                '{"result": 1}\n',
                encoding="utf-8",
            )
            (root / "paper" / "article.pdf").write_bytes(b"fixture-pdf")
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"
            first_run = self._build(root, first)
            self.assertEqual(first_run.returncode, 0, first_run.stdout)
            second_run = self._build(root, second)
            self.assertEqual(second_run.returncode, 0, second_run.stdout)
            self.assertEqual(self._sha256(first), self._sha256(second))

            expected = self._sha256(first)
            report = root / "verify.json"
            verified = subprocess.run(
                [
                    sys.executable,
                    str(VERIFY),
                    "--archive",
                    str(first),
                    "--expected-sha256",
                    expected,
                    "--output",
                    str(report),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(verified.returncode, 0, verified.stdout)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["verification_status"],
                "final_backup_verified",
            )
            self.assertEqual(payload["file_count"], 2)

    def test_plaintext_private_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results").mkdir()
            (root / "paper").mkdir()
            (root / "results" / "private-key.pem").write_text(
                "-----BEGIN RSA PRIVATE KEY-----\nfixture\n",
                encoding="utf-8",
            )
            (root / "paper" / "article.txt").write_text(
                "fixture",
                encoding="utf-8",
            )
            result = self._build(root, root / "blocked.tar.gz")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("plaintext secret", result.stdout)


if __name__ == "__main__":
    unittest.main()
