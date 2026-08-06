from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

from ctsteg.digital_ad.calibration import load_stability_profile
from ctsteg.digital_ad.config import DigitalADConfig


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/5j/build_stability_profile.py"


class Final5JStabilityBuilderTests(unittest.TestCase):
    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_builder_uses_only_calibration_covers_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "calibration.csv"
            covers: list[Path] = []
            for index in range(2):
                y, x = np.indices((512, 512))
                pixels = (
                    (x * (index + 3) + y * (index + 7) + index * 29) % 256
                ).astype(np.uint8)
                path = root / f"cover-{index}.png"
                Image.fromarray(pixels, mode="L").save(path)
                covers.append(path)
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["pair_id", "split", "cover", "cover_sha256"],
                )
                writer.writeheader()
                for index, cover in enumerate(covers):
                    writer.writerow(
                        {
                            "pair_id": f"cal-{index}",
                            "split": "calibration",
                            "cover": cover.name,
                            "cover_sha256": self._sha256(cover),
                        }
                    )
            config = root / "control.toml"
            config.write_text(
                "[digital_ad]\n"
                "format_version = 2\n"
                "transform_profile = \"haar_orthogonal_control_v1\"\n"
                "levels = 1\n"
                "directions = 4\n",
                encoding="utf-8",
            )
            output = root / "stability.json"
            command = [
                sys.executable,
                str(SCRIPT),
                "--manifest",
                str(manifest),
                "--config",
                str(config),
                "--output",
                str(output),
            ]
            first = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["calibration_only"])
            self.assertEqual(payload["protocol_id"], "FINAL-5J-v1")
            self.assertEqual(payload["image_count"], 2)
            self.assertEqual(len(payload["inputs"]), 2)
            self.assertTrue(payload["profile_identity"])
            config_object = DigitalADConfig.from_toml(config)
            loaded = load_stability_profile(output, config=config_object)
            self.assertTrue(loaded.values)

            second = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("refusing to replace", second.stdout)


if __name__ == "__main__":
    unittest.main()
