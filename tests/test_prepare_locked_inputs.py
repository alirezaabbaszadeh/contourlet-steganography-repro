from __future__ import annotations

import csv
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_locked_inputs",
    ROOT / "scripts" / "prepare_locked_inputs.py",
)
assert SPEC is not None and SPEC.loader is not None
locked_inputs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = locked_inputs
SPEC.loader.exec_module(locked_inputs)


def image_payload(value: int, *, image_format: str = "PNG") -> bytes:
    stream = BytesIO()
    Image.new("L", (32, 24), color=value).save(stream, format=image_format)
    return stream.getvalue()


class PrepareLockedInputsTests(unittest.TestCase):
    def test_posix_cksum_matches_standard_vectors(self) -> None:
        self.assertEqual(locked_inputs.posix_cksum(b""), (4294967295, 0))
        self.assertEqual(
            locked_inputs.posix_cksum(b"123456789"),
            (930766865, 9),
        )

    def test_rejects_nonfree_commons_license(self) -> None:
        asset = locked_inputs.CommonsAsset(
            "secret-test",
            "File:Test.jpg",
            "test.jpg",
            "traceability_core",
        )
        response = {
            "query": {
                "pages": [
                    {
                        "pageid": 1,
                        "title": asset.title,
                        "imageinfo": [
                            {
                                "url": "https://fixtures.invalid/original.jpg",
                                "thumburl": "https://fixtures.invalid/thumb.jpg",
                                "sha1": "a" * 40,
                                "timestamp": "2026-01-01T00:00:00Z",
                                "mime": "image/jpeg",
                                "extmetadata": {
                                    "LicenseShortName": {
                                        "value": "All Rights Reserved"
                                    },
                                    "UsageTerms": {
                                        "value": "All Rights Reserved"
                                    },
                                },
                            }
                        ],
                    }
                ]
            }
        }
        with self.assertRaisesRegex(ValueError, "free-license allowlist"):
            locked_inputs._validate_commons_page(asset, response)

    def _fixture_constants(self):
        cover_payloads = {
            f"cover-{index}": image_payload(20 + index, image_format="TIFF")
            for index in range(6)
        }
        secret_payloads = {
            f"secret-{index}": image_payload(100 + index)
            for index in range(6)
        }
        usc_assets = tuple(
            locked_inputs.UscAsset(
                asset_id=f"cover-{index}",
                identifier=f"fixture-{index}",
                filename=f"cover-{index}.tiff",
                official_posix_cksum=locked_inputs.posix_cksum(
                    cover_payloads[f"cover-{index}"]
                )[0],
                stratum=(
                    "traceability_core" if index < 4 else "calibration"
                ),
                rights="fixture research rights",
            )
            for index in range(6)
        )
        commons_assets = tuple(
            locked_inputs.CommonsAsset(
                asset_id=f"secret-{index}",
                title=f"File:Secret {index}.png",
                filename=f"secret-{index}.png",
                stratum=(
                    "traceability_core" if index < 4 else "calibration"
                ),
            )
            for index in range(6)
        )
        pairs = tuple(
            locked_inputs.PairSpec(
                pair_id=f"pair-{index}",
                cover_asset_id=f"cover-{index}",
                secret_asset_id=f"secret-{index}",
                split=(
                    "traceability_core" if index < 4 else "calibration"
                ),
            )
            for index in range(6)
        )
        return usc_assets, commons_assets, pairs, cover_payloads, secret_payloads

    def test_full_lock_manifests_hashes_and_resume_protection(self) -> None:
        (
            usc_assets,
            commons_assets,
            pairs,
            cover_payloads,
            secret_payloads,
        ) = self._fixture_constants()
        checksums_html = "\n".join(
            (
                f"<tr><td>{asset.source_path}<td>"
                f"{asset.official_posix_cksum}"
            )
            for asset in usc_assets
        ).encode()

        def fake_fetch(url: str, timeout_seconds: float) -> bytes:
            del timeout_seconds
            if url == locked_inputs.USC_CHECKSUM_URL:
                return checksums_html
            if "sipi.usc.edu/database/download.php" in url:
                identifier = parse_qs(urlparse(url).query)["img"][0]
                asset = next(
                    item for item in usc_assets
                    if item.identifier == identifier
                )
                return cover_payloads[asset.asset_id]
            if url.startswith(locked_inputs.COMMONS_API + "?"):
                title = parse_qs(urlparse(url).query)["titles"][0]
                asset = next(
                    item for item in commons_assets if item.title == title
                )
                index = int(asset.asset_id.rsplit("-", 1)[1])
                return json.dumps(
                    {
                        "query": {
                            "pages": [
                                {
                                    "pageid": 1000 + index,
                                    "title": title,
                                    "canonicalurl": (
                                        "https://commons.wikimedia.org/wiki/"
                                        f"File:Secret_{index}.png"
                                    ),
                                    "imageinfo": [
                                        {
                                            "url": (
                                                "https://fixtures.invalid/"
                                                f"original-{index}.png"
                                            ),
                                            "thumburl": (
                                                "https://fixtures.invalid/"
                                                f"thumb-{index}.png"
                                            ),
                                            "thumbwidth": 1600,
                                            "thumbheight": 1200,
                                            "sha1": f"{index + 1:040x}",
                                            "timestamp": (
                                                "2026-01-01T00:00:00Z"
                                            ),
                                            "size": 999,
                                            "mime": "image/png",
                                            "extmetadata": {
                                                "LicenseShortName": {
                                                    "value": "Public domain"
                                                },
                                                "UsageTerms": {
                                                    "value": "Public domain"
                                                },
                                                "LicenseUrl": {"value": ""},
                                            },
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ).encode()
            if url.startswith("https://fixtures.invalid/thumb-"):
                index = int(url.rsplit("-", 1)[1].split(".", 1)[0])
                return secret_payloads[f"secret-{index}"]
            raise AssertionError(f"unexpected fixture URL: {url}")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "inputs"
            manifests = root / "manifests"
            patches = (
                patch.object(locked_inputs, "USC_ASSETS", usc_assets),
                patch.object(locked_inputs, "COMMONS_ASSETS", commons_assets),
                patch.object(locked_inputs, "PAIR_SPECS", pairs),
                patch.object(locked_inputs, "_fetch_url", fake_fetch),
            )
            with patches[0], patches[1], patches[2], patches[3]:
                report = locked_inputs.prepare_locked_inputs(
                    output,
                    manifests,
                    access_date="2026-07-30",
                    attempts=1,
                )
                self.assertEqual(report["core_pair_count"], 4)
                with (manifests / "traceability-core-v2.csv").open(
                    newline="",
                    encoding="utf-8",
                ) as stream:
                    core = list(csv.DictReader(stream))
                self.assertEqual(len(core), 4)
                self.assertTrue(
                    all(row["split"] == "traceability_core" for row in core)
                )
                for row in core:
                    self.assertEqual(len(row["cover_sha256"]), 64)
                    self.assertEqual(len(row["secret_sha256"]), 64)
                    self.assertEqual(len(row["cover_array_sha256"]), 64)
                    self.assertEqual(len(row["secret_array_sha256"]), 64)
                with (manifests / "calibration-v2.csv").open(
                    newline="",
                    encoding="utf-8",
                ) as stream:
                    calibration = list(csv.DictReader(stream))
                self.assertEqual(len(calibration), 2)
                with (manifests / "source-inventory-v2.csv").open(
                    newline="",
                    encoding="utf-8",
                ) as stream:
                    inventory = list(csv.DictReader(stream))
                self.assertEqual(len(inventory), 12)
                self.assertTrue(
                    all(row["file_sha256"] for row in inventory)
                )
                self.assertTrue(
                    all(row["decoded_array_sha256"] for row in inventory)
                )
                with self.assertRaises(FileExistsError):
                    locked_inputs.prepare_locked_inputs(
                        output,
                        manifests,
                        access_date="2026-07-30",
                        attempts=1,
                    )
                resumed = locked_inputs.prepare_locked_inputs(
                    output,
                    manifests,
                    mode="resume",
                    access_date="2026-07-30",
                    attempts=1,
                )
                self.assertEqual(
                    resumed["core_manifest_sha256"],
                    report["core_manifest_sha256"],
                )
                corrupt = output / "covers" / "cover-0.tiff"
                corrupt.write_bytes(b"corrupt")
                with self.assertRaises(locked_inputs.LockConflict):
                    locked_inputs.prepare_locked_inputs(
                        output,
                        manifests,
                        mode="resume",
                        access_date="2026-07-30",
                        attempts=1,
                    )


if __name__ == "__main__":
    unittest.main()
