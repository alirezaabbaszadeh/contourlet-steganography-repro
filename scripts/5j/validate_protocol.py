#!/usr/bin/env python3
"""Fail-closed validator for the FINAL-5J-v1 machine-readable plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

EXPECTED_METHODS = ["C0", "C1", "C2", "C3_NP", "C3", "B1", "B2"]
EXPECTED_COUNTS = {
    "main_embeddings": 350,
    "main_evaluations": 7700,
    "payload_sweep_embeddings": 90,
    "payload_sweep_evaluations": 360,
    "psnr_sweep_embeddings": 90,
    "psnr_sweep_evaluations": 360,
    "total_embeddings": 530,
    "total_evaluations": 8420,
}
REQUIRED_DOCS = [
    "docs/FINAL_5J_IMPLEMENTATION_PLAN.md",
    "docs/5j/SECURITY_BACKUP_POLICY.md",
    "docs/5j/PROTOCOL.md",
    "docs/5j/STATISTICAL_ANALYSIS_PLAN.md",
    "docs/5j/FAILURE_SEVERITY_SPEC.md",
]


class ValidationError(ValueError):
    """Raised when the locked plan is internally inconsistent."""


def load_plan(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"plan file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError("plan root must be a JSON object")
    return value


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def compute_counts(plan: dict[str, Any]) -> dict[str, int]:
    main = plan["main"]
    main_pair_count = int(main["pair_count"])
    main_methods = list(main["methods"])
    channel_count = sum(int(item["realizations"]) for item in main["channel_instances"])

    main_embeddings = main_pair_count * len(main_methods)
    main_evaluations = main_embeddings * channel_count

    payload = plan["payload_sweep"]
    payload_embeddings = (
        int(payload["pair_count"])
        * len(payload["methods"])
        * len(payload["incremental_payload_fractions"])
    )
    payload_evaluations = payload_embeddings * len(payload["channels"])

    psnr = plan["psnr_sweep"]
    psnr_embeddings = (
        int(psnr["pair_count"])
        * len(psnr["methods"])
        * len(psnr["incremental_target_db"])
    )
    psnr_evaluations = psnr_embeddings * len(psnr["channels"])

    return {
        "main_embeddings": main_embeddings,
        "main_evaluations": main_evaluations,
        "payload_sweep_embeddings": payload_embeddings,
        "payload_sweep_evaluations": payload_evaluations,
        "psnr_sweep_embeddings": psnr_embeddings,
        "psnr_sweep_evaluations": psnr_evaluations,
        "total_embeddings": main_embeddings + payload_embeddings + psnr_embeddings,
        "total_evaluations": main_evaluations + payload_evaluations + psnr_evaluations,
    }


def validate_plan(plan: dict[str, Any], repo_root: Path) -> dict[str, int]:
    errors: list[str] = []

    _require(plan.get("protocol_id") == "FINAL-5J-v1", "protocol_id must be FINAL-5J-v1", errors)
    _require(
        plan.get("payload_format") == "v2_layer_integrity",
        "payload_format must be v2_layer_integrity",
        errors,
    )

    try:
        main = plan["main"]
        _require(main["pair_count"] == 50, "main pair_count must be 50", errors)
        _require(main["methods"] == EXPECTED_METHODS, f"main methods must equal {EXPECTED_METHODS}", errors)
        _require(len(set(main["methods"])) == 7, "main methods must be unique", errors)

        channels = main["channel_instances"]
        ids = [item["id"] for item in channels]
        _require(len(channels) == 10, "main must define 10 channel-level records", errors)
        _require(len(set(ids)) == len(ids), "channel IDs must be unique", errors)
        _require(
            sum(int(item["realizations"]) for item in channels) == 22,
            "main channel records must expand to exactly 22 instances",
            errors,
        )

        family_instances: dict[str, int] = {}
        for item in channels:
            realizations = int(item["realizations"])
            _require(realizations > 0, f"channel {item['id']} has non-positive realizations", errors)
            family = str(item["family"])
            family_instances[family] = family_instances.get(family, 0) + realizations
        _require(
            family_instances == {"clean": 1, "jpeg": 3, "gaussian": 9, "salt_pepper": 9},
            f"unexpected channel-family expansion: {family_instances}",
            errors,
        )

        payload = plan["payload_sweep"]
        _require(payload["pair_count"] == 10, "payload sweep pair_count must be 10", errors)
        _require(payload["methods"] == ["C0", "C3_NP", "C3"], "payload sweep methods changed", errors)
        _require(
            payload["incremental_payload_fractions"] == [0.25, 0.5, 0.75],
            "payload sweep incremental levels changed",
            errors,
        )
        _require(payload["reference_payload_fraction"] == 1.0, "payload reference must be 1.0", errors)
        _require(len(payload["channels"]) == 4, "payload sweep must have four channels", errors)

        psnr = plan["psnr_sweep"]
        _require(psnr["pair_count"] == 10, "PSNR sweep pair_count must be 10", errors)
        _require(psnr["methods"] == ["C0", "C3_NP", "C3"], "PSNR sweep methods changed", errors)
        _require(
            psnr["incremental_target_db"] == [40.0, 42.5, 47.5],
            "PSNR sweep incremental targets changed",
            errors,
        )
        _require(psnr["reference_target_db"] == 45.0, "PSNR reference must be 45.0 dB", errors)
        _require(len(psnr["channels"]) == 4, "PSNR sweep must have four channels", errors)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"malformed plan structure: {exc}")

    try:
        counts = compute_counts(plan)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"could not compute counts: {exc}")
        counts = {}

    for key, expected in EXPECTED_COUNTS.items():
        _require(counts.get(key) == expected, f"computed {key}={counts.get(key)!r}, expected {expected}", errors)
        declared = plan.get("expected_counts", {}).get(key)
        _require(declared == expected, f"declared {key}={declared!r}, expected {expected}", errors)

    freeze_rules = plan.get("freeze_rules", {})
    required_rules = [
        "outcome_driven_expansion_prohibited",
        "previous_88_evaluations_immutable",
        "seeds_must_be_locked_before_results",
        "main_run_requires_baseline_contracts",
        "main_run_requires_remote_backup_gate",
    ]
    for rule in required_rules:
        _require(freeze_rules.get(rule) is True, f"freeze rule must be true: {rule}", errors)

    for relative_path in REQUIRED_DOCS:
        _require((repo_root / relative_path).is_file(), f"required document missing: {relative_path}", errors)

    if errors:
        raise ValidationError("\n".join(f"- {message}" for message in errors))
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("configs/5j/study_plan_v1.json"),
        help="path to the machine-readable 5J plan",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON validation report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = args.plan if args.plan.is_absolute() else repo_root / args.plan

    try:
        plan = load_plan(plan_path)
        counts = validate_plan(plan, repo_root)
    except ValidationError as exc:
        if args.json:
            print(json.dumps({"valid": False, "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"FINAL-5J protocol validation failed:\n{exc}", file=sys.stderr)
        return 1

    report = {
        "valid": True,
        "protocol_id": plan["protocol_id"],
        "status": plan["status"],
        "counts": counts,
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("FINAL-5J protocol validation passed")
        for key, value in counts.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
