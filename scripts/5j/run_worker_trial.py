#!/usr/bin/env python3
"""Run one monitored FINAL-5J internal-worker performance trial."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
import sys
from typing import Any

from ctsteg.runtime import atomic_write_json
from ctsteg.digital_ad.runtime_5j import (
    CREATED_FROM_PATHS,
    Runner5JError,
    load_json_object,
    resolve_pair_inputs,
    validate_execution_plan,
    validate_science_ready_report,
    verify_created_from,
)
from ctsteg.digital_ad.runtime_bindings_5j import verify_finalized_execution_plan
from ctsteg.digital_ad.worker_trial_5j import WorkerTrialError, run_worker_trial
from ctsteg.digital_ad.worker_tuning_5j import (
    GIB,
    WorkerTuningError,
    load_config,
    parse_trial,
    recommend,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--science-ready-report", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--sampling-interval-seconds", type=float, default=2.0)
    parser.add_argument(
        "--autotune-config",
        type=Path,
        default=root / "configs/5j/worker_autotune_v1.json",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _host_memory_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _require_target_host(config: dict[str, Any]) -> dict[str, Any]:
    cpus = os.cpu_count() or 1
    memory = _host_memory_bytes()
    disk = shutil.disk_usage("/")
    target = config["target_host"]
    required_cpus = int(target["logical_cpus"])
    minimum_memory_gib = float(target["minimum_memory_gib"])
    minimum_total_storage_gib = float(target["minimum_total_storage_gib"])
    minimum_free_storage_gib = float(target["minimum_free_storage_gib"])
    if cpus < required_cpus:
        raise WorkerTrialError(
            f"worker tuning target requires at least {required_cpus} logical CPUs; found {cpus}"
        )
    if memory is None or memory < minimum_memory_gib * GIB:
        found = "unknown" if memory is None else f"{memory / GIB:.2f} GiB"
        raise WorkerTrialError(
            f"worker tuning target requires at least {minimum_memory_gib:.1f} GiB RAM; found {found}"
        )
    if disk.total < minimum_total_storage_gib * GIB:
        raise WorkerTrialError(
            f"worker tuning target requires about 100 GB storage; found {disk.total / GIB:.2f} GiB"
        )
    if disk.free < minimum_free_storage_gib * GIB:
        raise WorkerTrialError(
            f"worker tuning requires at least {minimum_free_storage_gib:.1f} GiB free storage; found {disk.free / GIB:.2f} GiB"
        )
    return {
        "logical_cpus": cpus,
        "memory_bytes": memory,
        "storage_total_bytes": disk.total,
        "storage_free_bytes": disk.free,
    }


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.autotune_config)
        host = _require_target_host(config)
        if args.workers > int(config["maximum_workers"]):
            raise WorkerTrialError("requested workers exceed the frozen 7-worker cap")
        if not args.run_dir.exists():
            args.run_dir.mkdir(parents=True)
        elif any(args.run_dir.iterdir()):
            raise WorkerTrialError("run directory must be empty for a new worker trial")

        plan = load_json_object(args.plan)
        index = validate_execution_plan(plan)
        runtime_report = verify_finalized_execution_plan(
            plan,
            runtime_bindings_path=args.runtime_bindings,
            check_files=True,
        )
        repository_root = args.repository_root.resolve()
        verify_created_from(plan, repository_root=repository_root)
        validate_science_ready_report(args.science_ready_report)
        pair_inputs = resolve_pair_inputs(plan, repository_root=repository_root)
        selection = load_json_object(args.selection)

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
            "pair_inputs": pair_inputs,
        }
        trial_payload = run_worker_trial(
            index=index,
            selection_payload=selection,
            context=context,
            cache_dir=args.cache_dir,
            run_dir=args.run_dir,
            workers=args.workers,
            sampling_interval_seconds=args.sampling_interval_seconds,
        )
        trial = parse_trial(trial_payload)
        decision = recommend(config, [trial])
        envelope = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "trial_sha256": trial.trial_sha256,
            "host_gate": host,
            "decision": decision,
        }
        atomic_write_json(args.run_dir / "worker_trial_decision.json", envelope)
    except (
        OSError,
        json.JSONDecodeError,
        Runner5JError,
        WorkerTrialError,
        WorkerTuningError,
        ValueError,
    ) as error:
        print(f"FINAL-5J worker trial failed: {error}", file=sys.stderr)
        return 1

    output = {"trial": trial_payload, **envelope}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"workers={trial_payload['workers']}")
        print(f"trial_sha256={trial_payload['trial_sha256']}")
        print(f"completed={trial_payload['tasks']['completed']}")
        print(
            "operational_failures="
            f"{trial_payload['tasks']['operational_failures']}"
        )
        print(
            "combined_tasks_per_hour="
            f"{trial_payload['timing']['combined_tasks_per_hour']:.3f}"
        )
        print(f"next_action={decision['action']}")
        print(f"next_workers={decision['workers']}")
        print(f"run_dir={args.run_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
