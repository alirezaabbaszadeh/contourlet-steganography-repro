"""Command-line interface for baseline and robustness runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ExperimentConfig
from .encryption import pseudocode_reachability
from .experiment import demo_config, run_experiment, synthetic_pair
from .image_io import load_grayscale


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

    subparsers.add_parser(
        "audit",
        help="print machine-checkable Algorithm 1 reachability facts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "audit":
        print(json.dumps(pseudocode_reachability(), indent=2, sort_keys=True))
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

