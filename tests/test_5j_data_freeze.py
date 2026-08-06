from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/5j/freeze_data_manifests.py"
CATALOG_HEADER = [
    "pair_id",
    "cover",
    "secret",
    "cover_source",
    "secret_source",
    "cover_rights_status",
    "secret_rights_status",
    "cover_license",
    "secret_license",
    "preprocessing_id",
    "redistribution_allowed",
    "private_archive_object_id",
    "notes",
]


class Final5JDataFreezeTests(unittest.TestCase):
    @staticmethod
    def _write_image(path: Path, shape: tuple[int, int], index: int) -> None:
        y, x = np.indices(shape)
        pixels = (
            (x * (index + 3) + y * (index + 5) + index * 17) % 256
        ).astype(np.uint8)
        Image.fromarray(pixels, mode="L").save(path)

    def test_freeze_is_exact_disjoint_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "assets"
            assets.mkdir()
            catalog = root / "candidates.csv"
            with catalog.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=CATALOG_HEADER)
                writer.writeheader()
                for index in range(54):
                    cover = assets / f"cover-{index:03d}.png"
                    secret = assets / f"secret-{index:03d}.png"
                    self._write_image(cover, (512, 512), index)
                    self._write_image(secret, (128, 128), index + 100)
                    writer.writerow(
                        {
                            "pair_id": f"pair-{index:03d}",
                            "cover": cover.relative_to(root).as_posix(),
                            "secret": secret.relative_to(root).as_posix(),
                            "cover_source": f"fixture-cover-{index}",
                            "secret_source": f"fixture-secret-{index}",
                            "cover_rights_status": "public_domain",
                            "secret_rights_status": "public_domain",
                            "cover_license": "fixture-public-domain",
                            "secret_license": "fixture-public-domain",
                            "preprocessing_id": "fixture-l-v1",
                            "redistribution_allowed": "true",
                            "private_archive_object_id": "",
                            "notes": "synthetic test fixture",
                        }
                    )
            output = root / "manifests"
            report = root / "freeze.json"
            command = [
                sys.executable,
                str(SCRIPT),
                "--catalog",
                str(catalog),
                "--output-dir",
                str(output),
                "--report",
                str(report),
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
            first_bytes = {
                path.name: path.read_bytes()
                for path in output.glob("*.csv")
            }
            first_report = json.loads(report.read_text(encoding="utf-8"))
            second = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            self.assertEqual(
                first_bytes,
                {path.name: path.read_bytes() for path in output.glob("*.csv")},
            )
            second_report = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(
                first_report["report_identity"],
                second_report["report_identity"],
            )
            self.assertEqual(
                first_report["selected_counts"],
                {"calibration": 2, "dry_run": 2, "main": 50, "sweep": 10},
            )
            calibration = set(first_report["selected_pair_ids"]["calibration"])
            dry_run = set(first_report["selected_pair_ids"]["dry_run"])
            main = set(first_report["selected_pair_ids"]["main"])
            sweep = set(first_report["selected_pair_ids"]["sweep"])
            self.assertTrue(calibration.isdisjoint(dry_run))
            self.assertTrue(calibration.isdisjoint(main))
            self.assertTrue(dry_run.isdisjoint(main))
            self.assertTrue(sweep.issubset(main))


if __name__ == "__main__":
    unittest.main()
