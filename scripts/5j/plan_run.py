#!/usr/bin/env python3
"""Render a deterministic, non-executing summary of the FINAL-5J-v1 run plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_protocol import ValidationError, load_plan, validate_plan


def expand_channel_instances(plan: dict[str, Any]) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for channel in plan["main"]["channel_instances"]:
        for realization in range(1, int(channel["realizations"]) + 1):
            instances.append(
                {
                    "channel_id": channel["id"],
                    "family": channel["family"],
                    "severity": channel["severity"],
                    "realization": realization,
                }
            )
    return instances


def build_summary(plan_path: Path, repo_root: Path) -> dict[str, Any]:
    raw = plan_path.read_bytes()
    plan = load_plan(plan_path)
    counts = validate_plan(plan, repo_root)
    channel_instances = expand_channel_instances(plan)

    return {
        "protocol_id": plan["protocol_id"],
        "status": plan["status"],
        "payload_format": plan["payload_format"],
        "plan_sha256": hashlib.sha256(raw).hexdigest(),
        "main": {
            "pair_count": plan["main"]["pair_count"],
            "methods": plan["main"]["methods"],
            "channel_instance_count": len(channel_instances),
            "channel_instances": channel_instances,
        },
        "payload_sweep": plan["payload_sweep"],
        "psnr_sweep": plan["psnr_sweep"],
        "counts": counts,
        "gates": {
            "protocol_valid": True,
            "data_manifest_frozen": False,
            "attack_seeds_frozen": False,
            "format_v2_implemented": False,
            "c3_np_implemented": False,
            "baseline_b1_approved": False,
            "baseline_b2_approved": False,
            "remote_backup_gate_implemented": False,
            "main_run_authorized": False
        }
    }


def render_text(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    gates = summary["gates"]
    lines = [
        f"Protocol: {summary['protocol_id']}",
        f"Plan SHA-256: {summary['plan_sha256']}",
        f"Main methods: {', '.join(summary['main']['methods'])}",
        f"Main channel instances per embedding: {summary['main']['channel_instance_count']}",
        "",
        "Planned counts:",
    ]
    lines.extend(f"  {key}: {value}" for key, value in counts.items())
    lines.extend(["", "Implementation gates:"])
    lines.extend(f"  {key}: {'PASS' if value else 'BLOCKED'}" for key, value in gates.items())
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("configs/5j/study_plan_v1.json"),
        help="path to the 5J plan",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--output", type=Path, help="optional output file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    plan_path = args.plan if args.plan.is_absolute() else repo_root / args.plan

    try:
        summary = build_summary(plan_path, repo_root)
    except (OSError, ValidationError, KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"could not build FINAL-5J plan: {exc}") from exc

    rendered = json.dumps(summary, indent=2, sort_keys=True) if args.json else render_text(summary)
    if args.output:
        output_path = args.output if args.output.is_absolute() else repo_root / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
