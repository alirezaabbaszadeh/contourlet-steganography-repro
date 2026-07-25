"""Command-line interface for runs, batch benchmarks, and paired comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark
from .config import ExperimentConfig
from .encryption import pseudocode_reachability
from .experiment import demo_config, run_experiment, synthetic_pair
from .image_io import load_grayscale
from .methods import available_methods
from .statistics import compare_benchmarks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctsteg",
        description="Auditable reconstruction of the 2026 CT steganography paper",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run on two image files")
    run.add_argument("--cover", required=True, type=Path)
    run.add_argument("--secret", required=True, type=Path)
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--skip-attacks", action="store_true")

    demo = subparsers.add_parser("demo", help="run a deterministic synthetic demo")
    demo.add_argument("--output-dir", type=Path, default=Path("results/demo"))
    demo.add_argument("--size", type=int, default=128)
    demo.add_argument("--no-quantize", action="store_true")
    demo.add_argument("--skip-attacks", action="store_true")

    benchmark = subparsers.add_parser(
        "benchmark",
        help="run one registered method over a paired CSV manifest",
    )
    benchmark.add_argument("--manifest", required=True, type=Path)
    benchmark.add_argument("--config", required=True, type=Path)
    benchmark.add_argument("--output-dir", required=True, type=Path)
    benchmark.add_argument("--method", default="paper_baseline")
    benchmark.add_argument("--skip-attacks", action="store_true")
    benchmark.add_argument("--save-artifacts", action="store_true")
    benchmark.add_argument(
        "--continue-on-error",
        action="store_true",
        help="record failed pairs and continue instead of stopping at the first",
    )

    compare = subparsers.add_parser(
        "compare",
        help="perform a paired statistical comparison of two benchmark CSVs",
    )
    compare.add_argument("--baseline", required=True, type=Path)
    compare.add_argument("--proposed", required=True, type=Path)
    compare.add_argument("--output-dir", required=True, type=Path)
    compare.add_argument("--bootstrap-resamples", type=int, default=10_000)
    compare.add_argument("--permutation-resamples", type=int, default=10_000)
    compare.add_argument("--seed", type=int, default=2026)
    compare.add_argument("--allow-incomplete-pairs", action="store_true")
    compare.add_argument(
        "--allow-provenance-mismatch",
        action="store_true",
        help="override manifest/config/input mismatch protection",
    )

    subparsers.add_parser(
        "audit",
        help="print machine-checkable Algorithm 1 reachability facts",
    )
    subparsers.add_parser("methods", help="list registered method identifiers")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "audit":
        print(json.dumps(pseudocode_reachability(), indent=2, sort_keys=True))
        return 0
    if args.command == "methods":
        print(json.dumps({"methods": available_methods()}, indent=2))
        return 0
    if args.command == "benchmark":
        config = ExperimentConfig.from_toml(args.config)
        summary = run_benchmark(
            args.manifest,
            config,
            args.output_dir,
            method_name=args.method,
            include_attacks=not args.skip_attacks,
            save_artifacts=args.save_artifacts,
            continue_on_error=args.continue_on_error,
        )
        print(
            json.dumps(
                {
                    "run_id": summary["run_id"],
                    "method": summary["method"],
                    "successful_units": summary["successful_units"],
                    "failed_units": summary["failed_units"],
                    "result_row_count": summary["result_row_count"],
                    "output_dir": str(args.output_dir),
                    "files": summary["files"],
                },
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return 0
    if args.command == "compare":
        comparison = compare_benchmarks(
            args.baseline,
            args.proposed,
            args.output_dir,
            bootstrap_resamples=args.bootstrap_resamples,
            permutation_resamples=args.permutation_resamples,
            seed=args.seed,
            allow_incomplete_pairs=args.allow_incomplete_pairs,
            allow_provenance_mismatch=args.allow_provenance_mismatch,
        )
        print(
            json.dumps(
                {
                    "analysis_id": comparison["analysis_id"],
                    "comparison_count": len(comparison["comparisons"]),
                    "output_dir": str(args.output_dir),
                    "provenance_checks": comparison["provenance_checks"],
                },
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return 0

    if args.command == "demo":
        config = demo_config(
            size=args.size,
            quantize_stego=not args.no_quantize,
        )
        cover, secret = synthetic_pair(size=args.size, seed=config.random_seed)
        summary = run_experiment(
            cover,
            secret,
            config,
            args.output_dir,
            include_attacks=not args.skip_attacks,
        )
    else:
        config = ExperimentConfig.from_toml(args.config)
        cover = load_grayscale(args.cover, size=config.image_size)
        secret = load_grayscale(args.secret, size=config.image_size)
        summary = run_experiment(
            cover,
            secret,
            config,
            args.output_dir,
            include_attacks=not args.skip_attacks,
        )

    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
