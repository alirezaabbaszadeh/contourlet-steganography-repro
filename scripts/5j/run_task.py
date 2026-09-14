#!/usr/bin/env python3
"""Execute one finalized FINAL-5J embedding or evaluation task.

The command dispatches C0/C1/C2/C3_NP/C3 to the internal worker and B1/B2 to
the frozen baseline worker. Numerical progress is local-cache based; remote
backup is not consulted or required during execution.
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
from ctsteg.digital_ad.runtime_baseline_worker_5j import (
    BaselineWorker5JError,
    execute_baseline_task,
)
from ctsteg.digital_ad.runtime_bindings_5j import (
    verify_finalized_execution_plan,
)
from ctsteg.digital_ad.runtime_tasks_5j import bind_evaluation_task
from ctsteg.digital_ad.runtime_worker_5j import (
    Worker5JError,
    execute_internal_task,
)


INTERNAL_METHODS = {"C0", "C1", "C2", "C3_NP", "C3"}
BASELINE_METHODS = {"B1", "B2"}


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--science-ready-report", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument(
        "--kind",
        choices=("embedding", "evaluation"),
        required=True,
    )
    parser.add_argument("--object-id", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _baseline_fingerprints(plan: dict[str, object]) -> dict[str, str]:
    values: dict[str, set[str]] = {"B1": set(), "B2": set()}
    for raw in plan["embeddings"]:
        if not isinstance(raw, dict):
            continue
        method = str(raw.get("method", ""))
        if method in values:
            values[method].add(str(raw.get("method_fingerprint", "")))
    output: dict[str, str] = {}
    for method, fingerprints in values.items():
        if len(fingerprints) != 1 or "" in fingerprints:
            raise Runner5JError(
                f"execution plan has inconsistent {method} fingerprints"
            )
        output[method] = next(iter(fingerprints))
    return output


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
        pairs = resolve_pair_inputs(
            plan,
            repository_root=args.repository_root,
        )

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
                embedding = index["embedding_by_id"][
                    evaluation["embedding_id"]
                ]
            except KeyError as error:
                raise Runner5JError(
                    "evaluation references an unknown finalized embedding"
                ) from error
            task = bind_evaluation_task(evaluation, embedding)

        repository_root = args.repository_root.resolve()
        context = {
            "run_id": index["run_id"],
            "source_fingerprint": plan["created_from"][
                "source_fingerprint"
            ],
            "config_path": str(
                repository_root / CREATED_FROM_PATHS["config_sha256"]
            ),
            "base_config_sha256": plan["created_from"]["config_sha256"],
            "stability_path": runtime_report["stability_profile"],
            "stability_sha256": runtime_report[
                "stability_profile_sha256"
            ],
            "runtime_binding_report": runtime_report,
            "pair_inputs": pairs,
            "baseline_method_fingerprints": _baseline_fingerprints(plan),
        }
        method = str(task["method"])
        if method in INTERNAL_METHODS:
            result = execute_internal_task(
                task,
                kind=args.kind,
                context=context,
                cache_dir=args.cache_dir,
            )
        elif method in BASELINE_METHODS:
            result = execute_baseline_task(
                task,
                kind=args.kind,
                context=context,
                cache_dir=args.cache_dir,
            )
        else:
            raise Runner5JError(f"unknown task method: {method}")
    except (
        Runner5JError,
        Worker5JError,
        BaselineWorker5JError,
        OSError,
        ValueError,
    ) as error:
        print(f"FINAL-5J task failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}={value}")
    return 0 if result["status"] in {"completed", "cached"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
