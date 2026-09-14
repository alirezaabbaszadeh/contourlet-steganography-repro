from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/5j/prepare_coco_candidates.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_coco_candidates", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CocoCandidatePreparationTests(unittest.TestCase):
    @staticmethod
    def _write_source(path: Path, index: int) -> None:
        y, x = np.indices((256, 320), dtype=np.uint16)
        values = (x * (index % 7 + 1) + y * (index % 11 + 3) + index * 17) % 256
        image = np.stack(
            [
                values,
                (values + index * 3) % 256,
                (255 - values + index) % 256,
            ],
            axis=-1,
        ).astype(np.uint8)
        Image.fromarray(image, mode="RGB").save(path)

    def _fixture(self, directory: Path) -> tuple[Path, Path]:
        source = directory / "val2017"
        source.mkdir()
        images = []
        for index in range(112):
            image_id = 100000 + index
            file_name = f"{image_id:012d}.jpg"
            self._write_source(source / file_name, index)
            images.append(
                {
                    "id": image_id,
                    "license": 4 if index < 110 else 2,
                    "file_name": file_name,
                    "coco_url": f"https://images.cocodataset.org/val2017/{file_name}",
                    "flickr_url": f"https://example.invalid/flickr/{image_id}",
                    "width": 320,
                    "height": 256,
                    "date_captured": "2013-01-01 00:00:00",
                }
            )
        payload = {
            "licenses": [
                {
                    "id": 4,
                    "name": "Attribution License",
                    "url": "http://creativecommons.org/licenses/by/2.0/",
                },
                {
                    "id": 2,
                    "name": "Noncommercial",
                    "url": "http://creativecommons.org/licenses/by-nc/2.0/",
                },
            ],
            "images": images,
        }
        annotations = directory / "instances_val2017.json"
        annotations.write_text(json.dumps(payload), encoding="utf-8")
        return annotations, source

    def test_preparation_is_deterministic_unique_and_freezer_compatible(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as name:
            temporary = Path(name)
            annotations, source = self._fixture(temporary)
            license_by_id, images = module.load_coco_metadata(annotations)
            eligible = module.eligible_images(license_by_id, images)
            self.assertEqual(len(eligible), 110)
            self.assertTrue(all(item["license_id"] == 4 for item in eligible))

            first_output = temporary / "first"
            second_output = temporary / "second"
            first_rows, first_provenance = module.pair_rows(
                eligible[: module.SOURCE_IMAGE_COUNT],
                source_dir=source,
                output_dir=first_output,
                download=False,
            )
            second_rows, _ = module.pair_rows(
                eligible[: module.SOURCE_IMAGE_COUNT],
                source_dir=source,
                output_dir=second_output,
                download=False,
            )
            self.assertEqual(len(first_rows), 54)
            self.assertEqual(
                [row["pair_id"] for row in first_rows],
                [row["pair_id"] for row in second_rows],
            )
            source_ids = {
                int(entry[role]["id"])
                for entry in first_provenance
                for role in ("cover", "secret")
            }
            self.assertEqual(len(source_ids), 108)
            self.assertTrue(all(row["redistribution_allowed"] == "true" for row in first_rows))
            self.assertTrue(all("CC BY 2.0" in row["cover_license"] for row in first_rows))

            catalog = first_output / "candidate_pairs.csv"
            module.atomic_csv(catalog, first_rows)
            with catalog.open("r", encoding="utf-8", newline="") as stream:
                loaded = list(csv.DictReader(stream))
            self.assertEqual(len(loaded), 54)

            freezer_spec = importlib.util.spec_from_file_location(
                "freeze_data_manifests", ROOT / "scripts/5j/freeze_data_manifests.py"
            )
            assert freezer_spec is not None and freezer_spec.loader is not None
            freezer = importlib.util.module_from_spec(freezer_spec)
            freezer_spec.loader.exec_module(freezer)
            candidates = freezer.load_candidates(
                catalog,
                output_dir=temporary / "manifests",
            )
            self.assertEqual(len(candidates), 54)
            self.assertEqual(len({row["cover_sha256"] for row in candidates}), 54)
            self.assertEqual(len({row["secret_sha256"] for row in candidates}), 54)

            first_cover = Image.open(first_output / first_rows[0]["cover"])
            first_secret = Image.open(first_output / first_rows[0]["secret"])
            self.assertEqual(first_cover.size, (512, 512))
            self.assertEqual(first_secret.size, (128, 128))
            self.assertEqual(first_cover.mode, "L")
            self.assertEqual(first_secret.mode, "L")

    def test_rejects_insufficient_cc_by_pool(self) -> None:
        module = load_module()
        licenses = {
            4: {
                "id": 4,
                "name": "Attribution License",
                "url": "http://creativecommons.org/licenses/by/2.0/",
            }
        }
        images = [
            {
                "id": index,
                "license": 4,
                "file_name": f"{index}.jpg",
                "coco_url": f"https://example.invalid/{index}.jpg",
                "flickr_url": "",
                "width": 640,
                "height": 480,
            }
            for index in range(107)
        ]
        with self.assertRaises(module.CocoPreparationError):
            module.eligible_images(licenses, images)


if __name__ == "__main__":
    unittest.main()
