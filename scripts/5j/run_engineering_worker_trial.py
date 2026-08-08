#!/usr/bin/env python3
"""Run the internal-only 5J worker trial on two frozen dry-run pairs.

This performance namespace is not scientific evidence and must never be merged
into the final 530/8,420 result archive. It exists only to choose a safe and
fast process count before B1/B2 and the main 50-pair plan are ready.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from ctsteg.provenance import sha256_file
from ctsteg.runtime import atomic_write_json
from ctsteg.digital_ad.config import DigitalADConfig, OCTAVE_PDFB_PROFILE
from ctsteg.digital_ad.engineering_worker_plan_5j import (
    build_engineering_plan,
    load_engineering_pairs,
    source_tree_fingerprint,
)
from ctsteg.digital_ad.runtime_5j import Runner5JError
from ctsteg.digital_ad.runtime_bindings_5j import validate_runtime_bindings
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
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/5j/format_v2_layer_integrity.toml",
    )
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
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


def _host_gate() -> dict[str, int]:
    cpus = os.cpu_count() or 1
    memory = _host_memory_bytes()
    if cpus < 32:
        raise WorkerTrialError(
            f"engineering worker trial requires at least 32 logical CPUs; found {cpus}"
        )
    if memory is None or memory < 60 * GIB:
        found = "unknown" if memory is None else f"{memory / GIB:.2f} GiB"
        raise WorkerTrialError(
            f"engineering worker trial requires approximately 64 GiB RAM; found {found}"
        )
    return {"logical_cpus": cpus, "memory_bytes": memory}


def main() -> int:
    args = parse_args()
    try:
        host = _host_gate()
        tuning_config = load_config(args.autotune_config)
        if args.workers > int(tuning_config["maximum_workers"]):
            raise WorkerTrialError("requested workers exceed the frozen 28-worker cap")
        if not args.run_dir.exists():
            args.run_dir.mkdir(parents=True)
        elif any(args.run_dir.iterdir()):
            raise WorkerTrialError("run directory must be empty for a new trial")

        repository_root = args.repository_root.resolve()
        config_path = args.config.resolve()
        config = DigitalADConfig.from_toml(config_path)
        if config.format_version != 2:
            raise WorkerTrialError("engineering trial requires payload format version 2")
        if config.transform_profile != OCTAVE_PDFB_PROFILE:
            raise WorkerTrialError("engineering trial requires the approved Octave PDFB profile")

        runtime_report = validate_runtime_bindings(
            args.runtime_bindings,
            check_files=True,
        )
        pairs, pair_inputs = load_engineering_pairs(
            args.manifest,
            repository_root=repository_root,
        )
        source_fingerprint = source_tree_fingerprint(
            repository_root / "src/ctsteg"
        )
        config_sha256 = sha256_file(config_path)
        plan, index, selection = build_engineering_plan(
            pairs,
            source_fingerprint=source_fingerprint,
            config_sha256=config_sha256,
            runtime_bindings_sha256=runtime_report["binding_sha256"],
            target_psnr_db=config.psnr_target_db,
        )
        atomic_write_json(args.run_dir / "engineering_worker_plan.json", plan)
        atomic_write_json(args.run_dir / "engineering_worker_selection.json", selection)

        context = {
            "run_id": index["run_id"],
            "source_fingerprint": source_fingerprint,
            "config_path": str(config_path),
            "base_config_sha256": config_sha256,
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
        decision = recommend(tuning_config, [trial])
        decision_payload = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "purpose": "worker_autotune_engineering_v1",
            "scientific_evidence": False,
            "trial_sha256": trial.trial_sha256,
            "host_gate": host,
            "decision": decision,
        }
        atomic_write_json(
            args.run_dir / "engineering_worker_trial_decision.json",
            decision_payload,
        )
    except (
        OSError,
        json.JSONDecodeError,
        Runner5JError,
        WorkerTrialError,
        WorkerTuningError,
        ValueError,
    ) as error:
        print(f"engineering worker trial failed: {error}", file=sys.stderr)
        return 1

    output = {"trial": trial_payload, **decision_payload}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print("scientific_evidence=false")
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
