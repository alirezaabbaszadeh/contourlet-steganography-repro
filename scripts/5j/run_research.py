#!/usr/bin/env python3
"""Run the fail-closed FINAL-5J-v1 local-execution preflight.

The supplied plan must already be finalized against a frozen runtime-binding
file. This command verifies runtime, source, input, and science-readiness gates.
Remote backup is not an execution gate; it is performed once after the complete
run, analysis, and manuscript package are finished.
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
    parser.add_argument(
        "--ledger",
        type=Path,
        help="Optional final-archive ledger; it does not gate execution.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _local_progress(run_dir: Path) -> tuple[int, int]:
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    counts = status.get("state_counts", {})
    locally_complete = int(counts.get("backup_pending", 0)) + int(
        counts.get("committed_complete", 0)
    )
    return locally_complete, int(status["total_tasks"])


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
        run_dir = Path(summary["run_dir"])
        verification_path = record_runtime_binding_verification(
            run_dir,
            binding_report,
        )
        locally_complete, total_tasks = _local_progress(run_dir)
        summary.pop("committed_complete", None)
        summary["locally_complete"] = locally_complete
        summary["total_tasks"] = total_tasks
        summary["backup_policy"] = "final_only_after_run_completion"
        summary["runtime_binding_verification"] = str(verification_path)
        atomic_write_json(run_dir / "run_summary.json", summary)
    except (Runner5JError, OSError, ValueError, json.JSONDecodeError) as error:
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
            f"locally_complete={summary['locally_complete']}"
        )
        print("backup_policy=final_only_after_run_completion")
        print(
            "runtime_binding_verification="
            f"{summary['runtime_binding_verification']}"
        )
        print(f"run_dir={summary['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
