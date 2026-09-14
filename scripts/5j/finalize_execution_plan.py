#!/usr/bin/env python3
"""Bind a logical FINAL-5J-v1 plan to frozen external runtime evidence.

The input plan is produced by ``build_execution_plan.py``. This command verifies
Octave, the Contourlet toolbox tree, Stage-0 evidence, and the calibration-only
stability profile, then recomputes every embedding/evaluation identity and the
run ID. Only this finalized plan is admissible to the research runner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import Runner5JError, load_json_object
from ctsteg.digital_ad.runtime_bindings_5j import finalize_execution_plan
from ctsteg.runtime import atomic_write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--runtime-bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        unbound = load_json_object(args.plan)
        finalized, verification = finalize_execution_plan(
            unbound,
            runtime_bindings_path=args.runtime_bindings,
            check_files=True,
        )
        output = args.output.resolve()
        if output.exists() and output.stat().st_size:
            existing = load_json_object(output)
            if existing != finalized:
                raise Runner5JError(
                    f"refusing to replace a different finalized plan: {output}"
                )
        else:
            atomic_write_json(output, finalized)
        if args.verification_output is not None:
            destination = args.verification_output.resolve()
            if destination.exists() and destination.stat().st_size:
                existing = load_json_object(destination)
                if existing != verification:
                    raise Runner5JError(
                        "refusing to replace different runtime verification"
                    )
            else:
                atomic_write_json(destination, verification)
    except (Runner5JError, OSError, ValueError) as error:
        print(f"FINAL-5J plan finalization failed: {error}", file=sys.stderr)
        return 1

    report = {
        "protocol_id": finalized["protocol_id"],
        "base_plan_id": finalized["base_plan_id"],
        "plan_id": finalized["plan_id"],
        "run_id": finalized["run_id"],
        "runtime_bindings_sha256": finalized["created_from"][
            "runtime_bindings_sha256"
        ],
        "counts": finalized["counts"],
        "output": str(output),
    }
    if args.verification_output is not None:
        report["verification_output"] = str(args.verification_output.resolve())
    print(
        json.dumps(report, indent=2, sort_keys=True)
        if args.json
        else "\n".join(f"{key}={value}" for key, value in report.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
