#!/usr/bin/env python3
"""Create the server-final FINAL-5J execution package from a real stability profile.

This command is intentionally the last planning step on the target numerical
server. It validates frozen Git inputs, builds the logical 530/8,420 plan,
freezes actual Octave/toolbox/Stage-0/stability hashes without manual JSON
editing, and writes the runtime-bound final plan plus verification reports.

The stability profile itself must already have been produced from the two frozen
calibration covers with ``build_stability_profile.py`` on this same runtime.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


PROTOCOL_ID = "FINAL-5J-v1"


class FinalPlanPreparationError(RuntimeError):
    """Raised when a FINAL-5J server-finalization stage fails."""


def run_checked(command: list[str], *, cwd: Path) -> str:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if process.returncode != 0:
        raise FinalPlanPreparationError(
            f"command failed ({process.returncode}): {' '.join(command)}\n"
            f"{process.stdout}"
        )
    return process.stdout


def parse_json_output(text: str, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise FinalPlanPreparationError(
            f"{label} did not emit valid JSON: {error}\n{text}"
        ) from error
    if not isinstance(payload, dict):
        raise FinalPlanPreparationError(f"{label} JSON root is not an object")
    return payload


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--runtime-executable", type=Path, required=True)
    parser.add_argument("--toolbox", type=Path, required=True)
    parser.add_argument("--stage0-evidence", type=Path, required=True)
    parser.add_argument("--stability-profile", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        root = args.repository_root.expanduser().resolve()
        if not root.is_dir():
            raise FinalPlanPreparationError(f"repository root missing: {root}")
        output = args.output_dir.expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)

        readiness_path = output / "input-readiness.json"
        unbound_path = output / "final-5j-unbound.json"
        binding_path = output / "final-5j-runtime-bindings.json"
        binding_verification = output / "runtime-binding-verification.json"
        bound_path = output / "final-5j-bound.json"
        final_verification = output / "final-plan-verification.json"
        for path in (
            readiness_path,
            unbound_path,
            binding_path,
            binding_verification,
            bound_path,
            final_verification,
        ):
            if path.exists() and path.stat().st_size:
                raise FinalPlanPreparationError(
                    f"refusing to overwrite existing finalization artifact: {path}"
                )

        readiness_stdout = run_checked(
            [
                sys.executable,
                str(root / "scripts/5j/validate_inputs.py"),
                "--check-files",
                "--require-science-ready",
                "--json",
            ],
            cwd=root,
        )
        readiness = parse_json_output(readiness_stdout, label="input readiness")
        if readiness.get("science_ready") is not True:
            raise FinalPlanPreparationError("frozen inputs are not science-ready")
        readiness_path.write_text(
            json.dumps(readiness, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        logical_stdout = run_checked(
            [
                sys.executable,
                str(root / "scripts/5j/build_execution_plan.py"),
                "--repository-root",
                str(root),
                "--output",
                str(unbound_path),
            ],
            cwd=root,
        )
        logical = parse_json_output(logical_stdout, label="logical plan builder")

        freeze_command = [
            sys.executable,
            str(root / "scripts/5j/freeze_runtime_bindings.py"),
            "--runtime-executable",
            str(args.runtime_executable.expanduser().resolve()),
            "--toolbox",
            str(args.toolbox.expanduser().resolve()),
            "--stage0-evidence",
            str(args.stage0_evidence.expanduser().resolve()),
            "--stability-profile",
            str(args.stability_profile.expanduser().resolve()),
            "--approved-by",
            args.approved_by,
            "--output",
            str(binding_path),
            "--verification-output",
            str(binding_verification),
            "--json",
        ]
        if args.approved_at:
            freeze_command.extend(["--approved-at", args.approved_at])
        binding_stdout = run_checked(freeze_command, cwd=root)
        binding = parse_json_output(binding_stdout, label="runtime binding freeze")

        final_stdout = run_checked(
            [
                sys.executable,
                str(root / "scripts/5j/finalize_execution_plan.py"),
                "--plan",
                str(unbound_path),
                "--runtime-bindings",
                str(binding_path),
                "--output",
                str(bound_path),
                "--verification-output",
                str(final_verification),
                "--json",
            ],
            cwd=root,
        )
        finalized = parse_json_output(final_stdout, label="final plan builder")

        bound = json.loads(bound_path.read_text(encoding="utf-8"))
        counts = bound.get("counts", {})
        if counts.get("total_embeddings") != 530 or counts.get("total_evaluations") != 8420:
            raise FinalPlanPreparationError(
                f"finalized plan count mismatch: {counts!r}"
            )
        if "runtime_bindings_sha256" not in bound.get("created_from", {}):
            raise FinalPlanPreparationError("finalized plan is not runtime-bound")

        report = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "status": "final_execution_plan_ready",
            "repository_root": str(root),
            "input_readiness": str(readiness_path),
            "unbound_plan": str(unbound_path),
            "base_plan_id": bound.get("base_plan_id"),
            "runtime_bindings": str(binding_path),
            "runtime_bindings_sha256": binding.get("binding_sha256"),
            "runtime_binding_verification": str(binding_verification),
            "final_plan": str(bound_path),
            "plan_id": bound.get("plan_id"),
            "run_id": bound.get("run_id"),
            "final_plan_verification": str(final_verification),
            "counts": counts,
            "logical_builder": logical,
            "finalizer": finalized,
        }
        (output / "FINAL_PLAN_READY.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (
        FinalPlanPreparationError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(f"FINAL-5J final plan preparation failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("status=final_execution_plan_ready")
        print(f"base_plan_id={report['base_plan_id']}")
        print(f"plan_id={report['plan_id']}")
        print(f"run_id={report['run_id']}")
        print("counts=530 embeddings / 8420 evaluations")
        print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
