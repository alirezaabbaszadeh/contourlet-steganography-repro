#!/usr/bin/env python3
"""Run the fail-closed FINAL-5J-v1 preflight contract.

This command validates the frozen expanded plan, all source/input fingerprints,
science readiness, immutable cache state, and the optional backup ledger.  It
publishes a resumable run directory but does not yet dispatch numerical tasks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import Runner5JError, prepare_run


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--science-ready-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = prepare_run(
            args.plan,
            repository_root=args.repository_root,
            science_ready_report=args.science_ready_report,
            output_root=args.output_root,
            cache_dir=args.cache_dir,
            ledger_path=args.ledger,
        )
    except (Runner5JError, OSError, ValueError) as error:
        print(f"FINAL-5J preflight failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"status={summary['status']}")
        print(f"run_id={summary['run_id']}")
        print(f"plan_id={summary['plan_id']}")
        print(
            "tasks="
            f"{summary['total_tasks']} "
            f"committed_complete={summary['committed_complete']}"
        )
        print(f"run_dir={summary['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
