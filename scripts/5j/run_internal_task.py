#!/usr/bin/env python3
"""Execute one finalized internal FINAL-5J embedding or evaluation task.

This is the controlled dry-run/pilot entrypoint. It revalidates the finalized
plan, external runtime bindings, source/input fingerprints, and science-ready
gate before touching the content-addressed cache. B1/B2 remain fail-closed.
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
from ctsteg.digital_ad.runtime_tasks_5j import bind_evaluation_task
from ctsteg.digital_ad.runtime_worker_5j import (
    Worker5JError,
    execute_internal_task,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--science-ready-report", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--kind", choices=("embedding", "evaluation"), required=True)
    parser.add_argument("--object-id", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = load_json_object(args.plan)
        index = validate_execution_plan(plan)
        runtime_report = verify_finalized_execution_plan(
            plan,
            runtime_bindings_path=args.runtime_bindings,
            check_files=True,
        )
        verify_created_from(plan, repository_root=args.repository_root)
        validate_science_ready_report(args.science_ready_report)
        pairs = resolve_pair_inputs(plan, repository_root=args.repository_root)

        if args.kind == "embedding":
            try:
                task = index["embedding_by_id"][args.object_id]
            except KeyError as error:
                raise Runner5JError(
                    f"unknown finalized embedding object ID: {args.object_id}"
                ) from error
        else:
            try:
                evaluation = index["evaluation_by_id"][args.object_id]
            except KeyError as error:
                raise Runner5JError(
                    f"unknown finalized evaluation object ID: {args.object_id}"
                ) from error
            try:
                embedding = index["embedding_by_id"][evaluation["embedding_id"]]
            except KeyError as error:
                raise Runner5JError(
                    "evaluation references an unknown finalized embedding"
                ) from error
            task = bind_evaluation_task(evaluation, embedding)

        repository_root = args.repository_root.resolve()
        context = {
            "run_id": index["run_id"],
            "source_fingerprint": plan["created_from"]["source_fingerprint"],
            "config_path": str(
                repository_root / CREATED_FROM_PATHS["config_sha256"]
            ),
            "base_config_sha256": plan["created_from"]["config_sha256"],
            "stability_path": runtime_report["stability_profile"],
            "stability_sha256": runtime_report["stability_profile_sha256"],
            "runtime_binding_report": runtime_report,
            "pair_inputs": pairs,
        }
        result = execute_internal_task(
            task,
            kind=args.kind,
            context=context,
            cache_dir=args.cache_dir,
        )
    except (Runner5JError, Worker5JError, OSError, ValueError) as error:
        print(f"FINAL-5J internal task failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0 if result["status"] in {"completed", "cached"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
