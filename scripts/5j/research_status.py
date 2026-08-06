#!/usr/bin/env python3
"""Reconstruct FINAL-5J-v1 progress from cache objects and backup ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import (
    Runner5JError,
    load_json_object,
    reconstruct_status,
)
from ctsteg.runtime import atomic_write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-records", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = load_json_object(args.plan)
        status = reconstruct_status(
            plan,
            cache_dir=args.cache_dir,
            ledger_path=args.ledger,
        )
        if args.output is not None:
            atomic_write_json(args.output.resolve(), status)
    except (Runner5JError, OSError, ValueError) as error:
        print(f"FINAL-5J status failed: {error}", file=sys.stderr)
        return 1

    display = dict(status)
    if not args.include_records:
        display.pop("records", None)
    if args.json:
        print(json.dumps(display, indent=2, sort_keys=True))
    else:
        print(f"run_id={status['run_id']}")
        print(f"plan_id={status['plan_id']}")
        print(
            f"committed_complete={status['committed_complete']}/"
            f"{status['total_tasks']}"
        )
        print(f"progress_fraction={status['progress_fraction']:.8f}")
        for state, count in status["state_counts"].items():
            print(f"{state}={count}")
        if args.output is not None:
            print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
