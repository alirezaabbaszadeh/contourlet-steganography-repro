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
import shutil
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
    load_trials,
    parse_trial,
    recommend,
    unsafe_reasons,
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


def _host_gate(tuning_config: dict[str, object]) -> dict[str, int]:
    cpus = os.cpu_count() or 1
    memory = _host_memory_bytes()
    disk = shutil.disk_usage('/')
    target = tuning_config.get('target_host')
    if not isinstance(target, dict):
        raise WorkerTrialError('worker tuning target_host is invalid')
    required_cpus = int(target['logical_cpus'])
    minimum_memory_gib = float(target.get('minimum_memory_gib', target['memory_gib']))
    minimum_total_storage_gib = float(target.get('minimum_total_storage_gib', 0))
    minimum_free_storage_gib = float(target.get('minimum_free_storage_gib', 0))
    if cpus < required_cpus:
        raise WorkerTrialError(
            f'engineering worker trial requires at least {required_cpus} logical CPUs; found {cpus}'
        )
    if memory is None or memory < minimum_memory_gib * GIB:
        found = 'unknown' if memory is None else f'{memory / GIB:.2f} GiB'
        raise WorkerTrialError(
            f'engineering worker trial requires at least {minimum_memory_gib:.1f} GiB RAM; found {found}'
        )
    if minimum_total_storage_gib and disk.total < minimum_total_storage_gib * GIB:
        raise WorkerTrialError(
            f'engineering worker trial requires about 100 GB storage; found {disk.total / GIB:.2f} GiB'
        )
    if minimum_free_storage_gib and disk.free < minimum_free_storage_gib * GIB:
        raise WorkerTrialError(
            f'engineering worker trial requires at least {minimum_free_storage_gib:.1f} GiB free storage; found {disk.free / GIB:.2f} GiB'
        )
    return {
        'logical_cpus': cpus,
        'memory_bytes': memory,
        'storage_total_bytes': disk.total,
        'storage_free_bytes': disk.free,
    }

def _load_history(run_root: Path) -> tuple[list[Path], dict[str, object]]:
    history_path = run_root / "benchmark_history.json"
    if not history_path.is_file():
        return [], {"schema_version": 1, "trial_paths": []}
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise WorkerTrialError("benchmark history is invalid")
    raw = payload.get("trial_paths")
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise WorkerTrialError("benchmark history trial_paths is invalid")
    paths = [(run_root / item).resolve() for item in raw]
    for path in paths:
        try:
            path.relative_to(run_root.resolve())
        except ValueError as exc:
            raise WorkerTrialError("benchmark history escapes run root") from exc
        if not path.is_file():
            raise WorkerTrialError(f"benchmark history trial is missing: {path}")
    return paths, payload


def _repeat_difference_percent(first: float, second: float) -> float:
    mean = (first + second) / 2.0
    return 0.0 if mean <= 0 else 100.0 * abs(first - second) / mean


def main() -> int:
    args = parse_args()
    try:
        tuning_config = load_config(args.autotune_config)
        host = _host_gate(tuning_config)
        candidates = list(tuning_config["candidate_order"])
        if args.workers not in candidates:
            raise WorkerTrialError("requested workers are outside the frozen candidate set")

        run_root = args.run_dir.resolve()
        cache_root = args.cache_dir.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)
        prior_paths, history = _load_history(run_root)
        prior_trials = load_trials(prior_paths)
        prior_decision = recommend(tuning_config, prior_trials)
        confirmation = False
        if prior_decision["action"] == "test":
            if args.workers != prior_decision["workers"]:
                raise WorkerTrialError(
                    f"profile requires {prior_decision['workers']} workers next; requested {args.workers}"
                )
        elif prior_decision["action"] == "accept":
            selected = prior_decision.get("selected_workers")
            already = sum(trial.workers == selected for trial in prior_trials)
            if args.workers != selected or already != 1:
                raise WorkerTrialError("benchmark is awaiting exactly one fresh-cache confirmation of the selected worker count")
            confirmation = True
        else:
            raise WorkerTrialError("worker profile stopped without an acceptable next trial")

        ordinal = 1 + sum(trial.workers == args.workers for trial in prior_trials)
        if ordinal > 2:
            raise WorkerTrialError("a worker candidate may be measured at most twice")
        trial_name = f"workers-{args.workers:02d}-trial-{ordinal:02d}"
        current_run_dir = run_root / trial_name
        current_cache_dir = cache_root / trial_name
        if current_run_dir.exists() or current_cache_dir.exists():
            raise WorkerTrialError(f"fresh trial namespace already exists: {trial_name}")
        current_run_dir.mkdir(parents=True)
        current_cache_dir.mkdir(parents=True)

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
        atomic_write_json(current_run_dir / "engineering_worker_plan.json", plan)
        atomic_write_json(current_run_dir / "engineering_worker_selection.json", selection)

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
            cache_dir=current_cache_dir,
            run_dir=current_run_dir,
            workers=args.workers,
            sampling_interval_seconds=args.sampling_interval_seconds,
        )
        trial = parse_trial(trial_payload)
        trial_path = current_run_dir / "worker_trial.json"
        all_paths = [*prior_paths, trial_path]
        all_trials = load_trials(all_paths)
        if confirmation:
            selected = int(prior_decision["selected_workers"])
            selected_trials = [item for item in all_trials if item.workers == selected]
            if len(selected_trials) != 2:
                raise WorkerTrialError("selected worker confirmation requires exactly two trials")
            unsafe = [reason for item in selected_trials for reason in unsafe_reasons(item, tuning_config)]
            difference = _repeat_difference_percent(
                selected_trials[0].combined_tasks_per_hour,
                selected_trials[1].combined_tasks_per_hour,
            )
            maximum_difference = float(
                tuning_config["stop_thresholds"]["maximum_repeat_throughput_difference_percent"]
            )
            if unsafe or difference > maximum_difference:
                decision = {
                    "action": "stop",
                    "workers": None,
                    "reason": "selected_worker_confirmation_failed",
                    "selected_workers": None,
                    "unsafe_reasons": sorted(set(unsafe)),
                    "repeat_difference_percent": difference,
                }
            else:
                decision = {
                    "action": "accept",
                    "workers": None,
                    "reason": "selected_worker_confirmation_passed",
                    "selected_workers": selected,
                    "repeat_difference_percent": difference,
                }
        else:
            decision = recommend(tuning_config, all_trials)
        relative_trial_path = trial_path.relative_to(run_root).as_posix()
        history["trial_paths"].append(relative_trial_path)
        history["latest_decision"] = decision
        atomic_write_json(run_root / "benchmark_history.json", history)
        decision_payload = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "purpose": "worker_autotune_engineering_v1",
            "scientific_evidence": False,
            "profile_id": tuning_config.get("profile_id"),
            "trial_sha256": trial.trial_sha256,
            "trial_count": len(all_trials),
            "trial_hashes": [item.trial_sha256 for item in all_trials],
            "host_gate": host,
            "decision": decision,
        }
        atomic_write_json(
            current_run_dir / "engineering_worker_trial_decision.json",
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
        print(f"run_dir={current_run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
