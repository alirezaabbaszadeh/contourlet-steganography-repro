"""Command-line interface for runs, batch benchmarks, and paired comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

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
    transform_audit = subparsers.add_parser(
        "audit-transform",
        help="write a machine-readable DIGITAL_A_D transform audit",
    )
    transform_audit.add_argument("--config", required=True, type=Path)
    transform_audit.add_argument("--output", required=True, type=Path)

    digital_demo = subparsers.add_parser(
        "digital-demo",
        help="run one deterministic DIGITAL_A_D synthetic experiment",
    )
    digital_demo.add_argument("--config", required=True, type=Path)
    digital_demo.add_argument("--output-dir", required=True, type=Path)
    digital_demo.add_argument("--method", default="C3_A_D")
    digital_demo.add_argument(
        "--attack-profile",
        choices=("none", "pilot", "final"),
        default="pilot",
    )

    digital_run = subparsers.add_parser(
        "digital-run",
        help="run one DIGITAL_A_D method on a cover/secret pair",
    )
    digital_run.add_argument("--cover", required=True, type=Path)
    digital_run.add_argument("--secret", required=True, type=Path)
    digital_run.add_argument("--config", required=True, type=Path)
    digital_run.add_argument("--output-dir", required=True, type=Path)
    digital_run.add_argument("--pair-id", required=True)
    digital_run.add_argument("--method", required=True)
    digital_run.add_argument("--stability-profile", type=Path)
    digital_run.add_argument(
        "--attack-profile",
        choices=("none", "pilot", "final"),
        default="pilot",
    )

    digital_calibrate = subparsers.add_parser(
        "digital-calibrate",
        help="derive a calibration-only subband stability profile",
    )
    digital_calibrate.add_argument("--manifest", required=True, type=Path)
    digital_calibrate.add_argument("--config", required=True, type=Path)
    digital_calibrate.add_argument("--output", required=True, type=Path)

    digital_benchmark = subparsers.add_parser(
        "digital-benchmark",
        help="run controlled C0--C3 experiments from a CSV manifest",
    )
    digital_benchmark.add_argument("--manifest", required=True, type=Path)
    digital_benchmark.add_argument("--config", required=True, type=Path)
    digital_benchmark.add_argument("--output-dir", required=True, type=Path)
    digital_benchmark.add_argument(
        "--methods",
        nargs="+",
        default=["C0_FIXED", "C1_A", "C2_D", "C3_A_D"],
    )
    digital_benchmark.add_argument("--stability-profile", type=Path)
    digital_benchmark.add_argument(
        "--attack-profile",
        choices=("none", "pilot", "final"),
        default="final",
    )
    digital_benchmark.add_argument("--continue-on-error", action="store_true")

    factorial = subparsers.add_parser(
        "digital-factorial",
        help="analyze C0--C3 main effects and A-by-D interaction",
    )
    factorial.add_argument("--results", required=True, type=Path)
    factorial.add_argument("--output-dir", required=True, type=Path)
    factorial.add_argument("--bootstrap-resamples", type=int, default=10_000)
    factorial.add_argument("--permutation-resamples", type=int, default=10_000)
    factorial.add_argument("--seed", type=int, default=2026)

    subparsers.add_parser("methods", help="list registered method identifiers")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command.startswith("digital") or args.command == "audit-transform":
        from .digital_ad.benchmark import run_digital_benchmark
        from .digital_ad.calibration import (
            calibrate_stability,
            load_stability_profile,
            write_stability_profile,
        )
        from .digital_ad.config import DigitalADConfig
        from .digital_ad.experiment import run_digital_experiment
        from .digital_ad.preprocessing import load_uint8_grayscale
        from .digital_ad.statistics import analyze_factorial
        from .digital_ad.transform_audit import write_transform_audit
        from .manifest import read_manifest

        if args.command == "audit-transform":
            config = DigitalADConfig.from_toml(args.config)
            report = write_transform_audit(args.output, config)
            print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
            return 0
        if args.command == "digital-demo":
            config = DigitalADConfig.from_toml(args.config)
            rng = np.random.default_rng(config.master_seed)
            cover = rng.integers(
                0,
                256,
                (config.cover_size, config.cover_size),
                dtype=np.uint8,
            )
            secret = rng.integers(
                0,
                256,
                (config.secret_size, config.secret_size),
                dtype=np.uint8,
            )
            result = run_digital_experiment(
                cover,
                secret,
                pair_id="synthetic",
                method=args.method,
                config=config,
                output_dir=args.output_dir,
                attack_profile=args.attack_profile,
            )
            print(
                json.dumps(
                    {
                        key: result[key]
                        for key in (
                            "method",
                            "pair_id",
                            "success",
                            "failure_reason",
                            "output_dir",
                        )
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if result["success"] or not config.clean_decode_required else 2
        if args.command == "digital-run":
            config = DigitalADConfig.from_toml(args.config)
            cover = load_uint8_grayscale(
                args.cover,
                size=config.cover_size,
            )
            secret = load_uint8_grayscale(
                args.secret,
                size=config.secret_size,
            )
            stability = (
                None
                if args.stability_profile is None
                else load_stability_profile(
                    args.stability_profile,
                    config=config,
                )
            )
            result = run_digital_experiment(
                cover,
                secret,
                pair_id=args.pair_id,
                method=args.method,
                config=config,
                output_dir=args.output_dir,
                stability_profile=stability,
                attack_profile=args.attack_profile,
            )
            print(
                json.dumps(
                    {
                        key: result[key]
                        for key in (
                            "method",
                            "pair_id",
                            "success",
                            "failure_reason",
                            "output_dir",
                        )
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if result["success"] or not config.clean_decode_required else 2
        if args.command == "digital-calibrate":
            config = DigitalADConfig.from_toml(args.config)
            pairs = read_manifest(args.manifest)
            invalid = [
                pair.pair_id
                for pair in pairs
                if not pair.split.lower().startswith("calibration")
            ]
            if invalid:
                raise ValueError(
                    "digital calibration manifest contains non-calibration "
                    f"splits: {invalid}"
                )
            covers = [
                load_uint8_grayscale(pair.cover, size=config.cover_size)
                for pair in pairs
            ]
            profile = calibrate_stability(covers, config=config)
            write_stability_profile(args.output, profile)
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "image_count": profile.artifact["image_count"],
                        "stability": profile.artifact["stability"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "digital-benchmark":
            config = DigitalADConfig.from_toml(args.config)
            result = run_digital_benchmark(
                args.manifest,
                config,
                args.output_dir,
                methods=args.methods,
                stability_path=args.stability_profile,
                attack_profile=args.attack_profile,
                continue_on_error=args.continue_on_error,
            )
            print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
            return 0 if result["failed_units"] == 0 else 2
        if args.command == "digital-factorial":
            result = analyze_factorial(
                args.results,
                args.output_dir,
                bootstrap_resamples=args.bootstrap_resamples,
                permutation_resamples=args.permutation_resamples,
                seed=args.seed,
            )
            print(
                json.dumps(
                    {
                        "comparison_count": len(result["comparisons"]),
                        "output_dir": str(args.output_dir),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
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
