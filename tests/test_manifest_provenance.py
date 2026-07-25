from pathlib import Path
import tempfile
import unittest

import numpy as np

from ctsteg.image_io import save_grayscale
from ctsteg.manifest import read_manifest
from ctsteg.methods import available_methods, build_method
from ctsteg.provenance import sha256_array, sha256_file, sha256_json


class ManifestAndProvenanceTests(unittest.TestCase):
    def test_manifest_resolves_paths_and_preserves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = np.arange(64, dtype=np.float64).reshape(8, 8)
            save_grayscale(root / "cover.png", image)
            save_grayscale(root / "secret.png", image[::-1])
            manifest = root / "pairs.csv"
            manifest.write_text(
                "pair_id,cover,secret,split,seed,source\n"
                "pair-1,cover.png,secret.png,locked_test,17,synthetic\n",
                encoding="utf-8",
            )

            pairs = read_manifest(manifest)

            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0].cover, (root / "cover.png").resolve())
            self.assertEqual(pairs[0].seed, 17)
            self.assertEqual(pairs[0].metadata["source"], "synthetic")

    def test_duplicate_experimental_unit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = np.zeros((8, 8), dtype=np.float64)
            save_grayscale(root / "image.png", image)
            manifest = root / "pairs.csv"
            manifest.write_text(
                "pair_id,cover,secret,seed\n"
                "same,image.png,image.png,1\n"
                "same,image.png,image.png,1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read_manifest(manifest)

    def test_hashes_are_deterministic_and_shape_sensitive(self) -> None:
        first = np.arange(16, dtype=np.float64).reshape(4, 4)
        second = first.reshape(2, 8)
        self.assertEqual(sha256_array(first), sha256_array(first.copy()))
        self.assertNotEqual(sha256_array(first), sha256_array(second))
        self.assertEqual(
            sha256_json({"b": 2, "a": 1}),
            sha256_json({"a": 1, "b": 2}),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "payload.bin"
            path.write_bytes(b"reproducible")
            self.assertEqual(sha256_file(path), sha256_file(path))

    def test_baseline_method_is_registered(self) -> None:
        self.assertIn("paper_baseline", available_methods())
        self.assertEqual(build_method("paper_baseline").name, "paper_baseline")
        with self.assertRaisesRegex(ValueError, "unknown method"):
            build_method("not_registered")


if __name__ == "__main__":
    unittest.main()
