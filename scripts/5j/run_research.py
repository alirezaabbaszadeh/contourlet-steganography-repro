#!/usr/bin/env python3
"""Run the fail-closed FINAL-5J-v1 preflight contract.

The supplied plan must already be finalized against a frozen runtime-binding
file. This command re-verifies those bytes, all source/input fingerprints,
science readiness, immutable cache state, and the optional backup ledger. It
publishes a resumable run directory but does not yet dispatch numerical tasks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import Runner5JError, load_json_object, prepare_run
from ctsteg.digital_ad.runtime_bindings_5j import (
    record_runtime_binding_verification,
    verify_finalized_execution_plan,
)
from ctsteg.runtime import atomic_write_json


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
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
        plan = load_json_object(args.plan)
        binding_report = verify_finalized_execution_plan(
            plan,
            runtime_bindings_path=args.runtime_bindings,
            check_files=True,
        )
        summary = prepare_run(
            args.plan,
            repository_root=args.repository_root,
            science_ready_report=args.science_ready_report,
            output_root=args.output_root,
            cache_dir=args.cache_dir,
            ledger_path=args.ledger,
        )
        verification_path = record_runtime_binding_verification(
            summary["run_dir"],
            binding_report,
        )
        summary["runtime_binding_verification"] = str(verification_path)
        atomic_write_json(Path(summary["run_dir"]) / "run_summary.json", summary)
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
        print(
            "runtime_binding_verification="
            f"{summary['runtime_binding_verification']}"
        )
        print(f"run_dir={summary['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
