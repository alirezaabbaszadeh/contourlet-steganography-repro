from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ctsteg.digital_ad.runtime_bindings_5j import (
    STAGE0_PROFILE,
    STAGE0_SCHEME,
    TRANSFORM_PROFILE,
    validate_runtime_bindings,
)


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "scripts/5j/freeze_runtime_bindings.py"


class Final5JRuntimeFreezeTests(unittest.TestCase):
    @staticmethod
    def _digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    def test_freezer_computes_and_verifies_all_runtime_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "octave-cli-fixture"
            runtime.write_bytes(b"fixture-octave-runtime\n")
            runtime.chmod(0o755)

            toolbox = root / "toolbox"
            toolbox.mkdir()
            for name in (
                "pdfbdec.m",
                "pdfbrec.m",
                "pfilters.m",
                "wfb2dec.m",
                "wfb2rec.m",
                "dfbdec_l.m",
                "dfbrec_l.m",
                "resampc.m",
            ):
                (toolbox / name).write_text(
                    f"% fixture {name}\n",
                    encoding="utf-8",
                )

            stage0 = root / "stage0.json"
            stage0.write_text(
                json.dumps(
                    {
                        "schema": 2,
                        "runtime_verified": True,
                        "passed": True,
                        "profile": STAGE0_PROFILE,
                        "scheme": STAGE0_SCHEME,
                        "exploratory": False,
                        "author_equivalence_claimed": False,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            stability = root / "stability.json"
            stability.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "protocol_id": "FINAL-5J-v1",
                        "calibration_only": True,
                        "transform_profile": TRANSFORM_PROFILE,
                        "transform_fingerprint": self._digest("transform"),
                        "stability": {"V:P4:LH": 1.0},
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            output = root / "runtime-bindings.json"
            verification = root / "verification.json"
            process = subprocess.run(
                [
                    sys.executable,
                    str(FREEZE),
                    "--runtime-executable",
                    str(runtime),
                    "--toolbox",
                    str(toolbox),
                    "--stage0-evidence",
                    str(stage0),
                    "--stability-profile",
                    str(stability),
                    "--approved-by",
                    "fixture-test",
                    "--approved-at",
                    "2026-08-08T00:00:00Z",
                    "--output",
                    str(output),
                    "--verification-output",
                    str(verification),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            report = json.loads(process.stdout)
            self.assertEqual(report["status"], "frozen")
            self.assertTrue(report["science_ready"])
            self.assertEqual(report["toolbox_file_count"], 8)
            self.assertTrue(verification.is_file())
            validated = validate_runtime_bindings(output, check_files=True)
            self.assertEqual(
                validated["binding_sha256"],
                report["binding_sha256"],
            )

            repeated = subprocess.run(
                [
                    sys.executable,
                    str(FREEZE),
                    "--runtime-executable",
                    str(runtime),
                    "--toolbox",
                    str(toolbox),
                    "--stage0-evidence",
                    str(stage0),
                    "--stability-profile",
                    str(stability),
                    "--approved-by",
                    "fixture-test",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("refusing to replace", repeated.stdout)


if __name__ == "__main__":
    unittest.main()
