#!/usr/bin/env python3
"""Reconstruct FINAL-5J-v1 execution progress from the local cache.

Remote backup is a final archival step and is shown separately when a final
ledger is supplied. It never determines numerical progress.
"""

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
    parser.add_argument(
        "--ledger",
        type=Path,
        help="Optional final-archive ledger; never used as an execution gate.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-records", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def normalize_local_progress(status: dict[str, object]) -> dict[str, object]:
    raw_counts = dict(status.get("state_counts", {}))
    locally_complete = int(raw_counts.get("backup_pending", 0)) + int(
        raw_counts.get("committed_complete", 0)
    )
    final_backup_verified = int(raw_counts.get("committed_complete", 0))
    total = int(status["total_tasks"])

    normalized: dict[str, int] = {}
    for state, count in raw_counts.items():
        if state in {"backup_pending", "committed_complete"}:
            continue
        normalized[str(state)] = int(count)
    if locally_complete:
        normalized["locally_complete"] = locally_complete

    records = status.get("records")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            original = record.get("state")
            if original in {"backup_pending", "committed_complete"}:
                record["state"] = "locally_complete"
            record["final_backup_verified"] = original == "committed_complete"

    status["state_counts"] = dict(sorted(normalized.items()))
    status["locally_complete"] = locally_complete
    status["final_backup_verified"] = final_backup_verified
    status["progress_fraction"] = locally_complete / total if total else 0.0
    status["final_backup_fraction"] = (
        final_backup_verified / total if total else 0.0
    )
    status["backup_policy"] = "final_only_after_run_completion"
    status.pop("committed_complete", None)
    return status


def main() -> int:
    args = parse_args()
    try:
        plan = load_json_object(args.plan)
        status = reconstruct_status(
            plan,
            cache_dir=args.cache_dir,
            ledger_path=args.ledger,
        )
        status = normalize_local_progress(status)
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
            f"locally_complete={status['locally_complete']}/"
            f"{status['total_tasks']}"
        )
        print(
            "final_backup_verified="
            f"{status['final_backup_verified']}/{status['total_tasks']}"
        )
        print(f"progress_fraction={status['progress_fraction']:.8f}")
        for state, count in status["state_counts"].items():
            print(f"{state}={count}")
        if args.output is not None:
            print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
