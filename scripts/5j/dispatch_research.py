#!/usr/bin/env python3
"""Run all seven FINAL-5J methods using the local resumable cache.

The plan must be finalized and science-ready. The command starts with the
requested worker count (4 by default), executes all embeddings, verifies
clean acceptance, then executes all evaluations. No remote upload or backup
verification occurs during numerical execution.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import (
    CREATED_FROM_PATHS,
    Runner5JError,
    load_json_object,
    resolve_pair_inputs,
    validate_execution_plan,
    validate_science_ready_report,
    verify_created_from,
)
from ctsteg.digital_ad.runtime_bindings_5j import (
    verify_finalized_execution_plan,
)
from ctsteg.digital_ad.runtime_dispatch_5j import (
    Dispatch5JError,
    build_worker_context,
    run_local_study,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--science-ready-report", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--reserve-cpus", type=int, default=1)
    parser.add_argument("--reserve-memory-gib", type=float, default=3.5)
    parser.add_argument("--worker-memory-gib", type=float, default=1.5)
    parser.add_argument("--hard-cap", type=int, default=7)
    parser.add_argument(
        "--stop-after",
        choices=("embeddings",),
        help="Optional engineering checkpoint after local embedding completion.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repository_root = args.repository_root.resolve()
        plan = load_json_object(args.plan)
        validate_execution_plan(plan)
        runtime_report = verify_finalized_execution_plan(
            plan,
            runtime_bindings_path=args.runtime_bindings,
            check_files=True,
        )
        verify_created_from(plan, repository_root=repository_root)
        validate_science_ready_report(args.science_ready_report)
        pairs = resolve_pair_inputs(
            plan,
            repository_root=repository_root,
        )
        context = build_worker_context(
            plan,
            runtime_report=runtime_report,
            pair_inputs=pairs,
            config_path=(
                repository_root / CREATED_FROM_PATHS["config_sha256"]
            ),
        )
        summary = run_local_study(
            plan,
            context=context,
            cache_dir=args.cache_dir,
            run_dir=args.run_dir,
            workers=args.workers,
            reserve_cpus=args.reserve_cpus,
            reserve_memory_gib=args.reserve_memory_gib,
            worker_memory_gib=args.worker_memory_gib,
            hard_cap=args.hard_cap,
            stop_after=args.stop_after,
        )
    except (
        Runner5JError,
        Dispatch5JError,
        OSError,
        ValueError,
        RuntimeError,
    ) as error:
        print(f"FINAL-5J dispatch failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"status={summary['status']}")
        print(f"run_id={summary['run_id']}")
        print(f"workers={summary['workers']}")
        embedding = summary["embedding_stage"]
        print(
            "embeddings="
            f"{embedding['task_count']} "
            f"cached={embedding['cached']} "
            f"completed={embedding['completed']} "
            f"failed={embedding['failed']}"
        )
        evaluation = summary.get("evaluation_stage")
        if isinstance(evaluation, dict):
            print(
                "evaluations="
                f"{evaluation['task_count']} "
                f"cached={evaluation['cached']} "
                f"completed={evaluation['completed']} "
                f"failed={evaluation['failed']}"
            )
        print(f"run_dir={args.run_dir.resolve()}")
        print("backup_policy=final_only_after_run_completion")
    return 0 if summary["status"] in {
        "embeddings_complete_local",
        "run_complete_local",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
