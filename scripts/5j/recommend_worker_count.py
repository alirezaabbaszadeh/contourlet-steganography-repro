#!/usr/bin/env python3
"""Recommend the next FINAL-5J worker trial from frozen measurements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.worker_tuning_5j import (
    WorkerTuningError,
    load_config,
    load_trials,
    recommend,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/5j/worker_autotune_v1.json",
    )
    parser.add_argument(
        "--trial",
        type=Path,
        action="append",
        default=[],
        help="Trial JSON in chronological order; repeat this option.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        trials = load_trials(args.trial)
        decision = recommend(config, trials)
    except (OSError, json.JSONDecodeError, WorkerTuningError) as error:
        print(f"worker tuning decision failed: {error}", file=sys.stderr)
        return 1

    payload = {
        "schema_version": 1,
        "protocol_id": "FINAL-5J-v1",
        "config": str(args.config.resolve()),
        "trial_count": len(trials),
        "trial_hashes": [trial.trial_sha256 for trial in trials],
        "decision": decision,
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
