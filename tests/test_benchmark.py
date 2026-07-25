import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ctsteg.benchmark import run_benchmark
from ctsteg.config import ExperimentConfig
from ctsteg.experiment import synthetic_pair
from ctsteg.image_io import save_grayscale
from ctsteg.methods import (
    MethodEmbedding,
    MethodExtraction,
    register_method,
)


class _ReferenceReplacingMethod:
    name = "reference_replacing_test_method"
    version = "1"

    def embed(self, cover, secret, config):
        del config
        cover_array = np.asarray(cover, dtype=np.float64)
        secret_array = np.asarray(secret, dtype=np.float64)
        return MethodEmbedding(
            cover=cover_array + 1.0,
            secret=secret_array,
            stego=cover_array,
            extraction_context=secret_array,
        )

    def extract(self, stego, original_cover, config, *, context=None):
        del stego, original_cover, config
        return MethodExtraction(
            recovered_secret=np.asarray(context, dtype=np.float64)
        )


class BenchmarkTests(unittest.TestCase):
    def test_batch_run_writes_provenance_and_long_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "pairs.csv"
            manifest_rows = ["pair_id,cover,secret,split,seed"]
            for index in range(2):
                cover, secret = synthetic_pair(size=32, seed=index + 1)
                cover_name = f"cover-{index}.png"
                secret_name = f"secret-{index}.png"
                save_grayscale(root / cover_name, cover)
                save_grayscale(root / secret_name, secret)
                manifest_rows.append(
                    f"pair-{index},{cover_name},{secret_name},test,{100 + index}"
                )
            manifest.write_text("\n".join(manifest_rows) + "\n", encoding="utf-8")
            config = replace(
                ExperimentConfig(),
                image_size=32,
                levels=2,
                band_policy="all_details",
                embed_lowpass=True,
                quantize_stego=True,
            )
            output = root / "benchmark"

            result = run_benchmark(
                manifest,
                config,
                output,
                include_attacks=False,
                save_artifacts=True,
            )

            self.assertEqual(result["successful_units"], 2)
            self.assertEqual(result["failed_units"], 0)
            self.assertEqual(result["result_row_count"], 34)
            for filename in (
                "benchmark.json",
                "provenance.json",
                "results_long.csv",
                "summary.csv",
            ):
                self.assertTrue((output / filename).is_file())
            with (output / "results_long.csv").open(
                newline="", encoding="utf-8"
            ) as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 34)
            self.assertEqual({row["method"] for row in rows}, {"paper_baseline"})
            self.assertEqual(
                {row["scope"] for row in rows},
                {"imperceptibility", "recovery", "efficiency"},
            )
            with (output / "provenance.json").open(encoding="utf-8") as stream:
                provenance = json.load(stream)
            self.assertEqual(provenance["manifest"]["unit_count"], 2)
            self.assertEqual(
                len(provenance["manifest"]["input_files_sha256"]),
                64,
            )
            self.assertEqual(provenance["config"]["image_size"], 32)
            self.assertEqual(
                len(provenance["method"]["implementation_sha256"]),
                64,
            )
            self.assertEqual(
                set(provenance["evaluation_code"]),
                {
                    "attacks_sha256",
                    "attack_suite_sha256",
                    "benchmark_sha256",
                    "image_io_sha256",
                    "manifest_sha256",
                    "metrics_sha256",
                },
            )
            self.assertEqual(len(provenance["run_id"]), 16)
            self.assertTrue(
                (
                    output
                    / "artifacts"
                    / "pair-0"
                    / "seed-100"
                    / "stego.png"
                ).is_file()
            )

    def test_nonempty_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cover, secret = synthetic_pair(size=16, seed=1)
            save_grayscale(root / "cover.png", cover)
            save_grayscale(root / "secret.png", secret)
            manifest = root / "pairs.csv"
            manifest.write_text(
                "pair_id,cover,secret\none,cover.png,secret.png\n",
                encoding="utf-8",
            )
            output = root / "existing"
            output.mkdir()
            (output / "stale.txt").write_text("stale", encoding="utf-8")
            config = replace(
                ExperimentConfig(),
                image_size=16,
                levels=2,
            )
            with self.assertRaisesRegex(FileExistsError, "not empty"):
                run_benchmark(
                    manifest,
                    config,
                    output,
                    include_attacks=False,
                )

    def test_method_cannot_replace_metric_reference_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cover, secret = synthetic_pair(size=16, seed=1)
            save_grayscale(root / "cover.png", cover)
            save_grayscale(root / "secret.png", secret)
            manifest = root / "pairs.csv"
            manifest.write_text(
                "pair_id,cover,secret\none,cover.png,secret.png\n",
                encoding="utf-8",
            )
            register_method(
                _ReferenceReplacingMethod.name,
                _ReferenceReplacingMethod,
                replace=True,
            )
            config = replace(
                ExperimentConfig(),
                image_size=16,
                levels=2,
            )
            with self.assertRaisesRegex(RuntimeError, "must not alter"):
                run_benchmark(
                    manifest,
                    config,
                    root / "benchmark",
                    method_name=_ReferenceReplacingMethod.name,
                    include_attacks=False,
                )


if __name__ == "__main__":
    unittest.main()
