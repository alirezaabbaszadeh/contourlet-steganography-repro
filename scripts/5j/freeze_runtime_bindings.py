#!/usr/bin/env python3
"""Freeze and verify the real FINAL-5J PDFB runtime bindings.

The command computes all hashes from actual files/directories, writes a
science-ready runtime-binding object, and immediately verifies every bound byte
plus the locked Stage-0 and stability contracts. No hash is entered manually.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from ctsteg.digital_ad.runtime_5j import Runner5JError
from ctsteg.digital_ad.runtime_bindings_5j import (
    PROTOCOL_ID,
    RUNTIME_BINDING_SCHEMA_VERSION,
    TRANSFORM_PROFILE,
    toolbox_inventory,
    toolbox_tree_sha256,
    validate_runtime_bindings,
)
from ctsteg.provenance import sha256_file
from ctsteg.runtime import atomic_write_json


class RuntimeFreezeError(RuntimeError):
    """Raised when runtime bindings cannot be frozen safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def regular_file(path: Path, *, executable: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise RuntimeFreezeError(f"not a regular file: {resolved}")
    if executable and not os.access(resolved, os.X_OK):
        raise RuntimeFreezeError(f"runtime is not executable: {resolved}")
    return resolved


def regular_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir() or resolved.is_symlink():
        raise RuntimeFreezeError(f"not a regular directory: {resolved}")
    return resolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", type=Path, required=True)
    parser.add_argument("--toolbox", type=Path, required=True)
    parser.add_argument("--stage0-evidence", type=Path, required=True)
    parser.add_argument("--stability-profile", type=Path, required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--approved-at", help="ISO timestamp; defaults to current UTC")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate: Path | None = None
    try:
        output = args.output.expanduser().resolve()
        if output.exists() and output.stat().st_size:
            raise RuntimeFreezeError(
                f"refusing to replace non-empty runtime binding: {output}"
            )
        runtime = regular_file(args.runtime_executable, executable=True)
        toolbox = regular_directory(args.toolbox)
        stage0 = regular_file(args.stage0_evidence)
        stability = regular_file(args.stability_profile)
        approved_by = args.approved_by.strip()
        if not approved_by:
            raise RuntimeFreezeError("--approved-by must be non-empty")

        inventory = toolbox_inventory(toolbox)
        payload = {
            "schema_version": RUNTIME_BINDING_SCHEMA_VERSION,
            "protocol_id": PROTOCOL_ID,
            "status": "frozen",
            "transform_profile": TRANSFORM_PROFILE,
            "runtime_executable": {
                "path": str(runtime),
                "sha256": sha256_file(runtime),
            },
            "toolbox": {
                "path": str(toolbox),
                "tree_sha256": toolbox_tree_sha256(inventory),
            },
            "stage0_evidence": {
                "path": str(stage0),
                "sha256": sha256_file(stage0),
            },
            "stability_profile": {
                "path": str(stability),
                "sha256": sha256_file(stability),
            },
            "science_ready": True,
            "approved_by": approved_by,
            "approved_at": args.approved_at or utc_now(),
            "blockers": [],
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        candidate = output.with_name(f".{output.name}.{os.getpid()}.candidate")
        if candidate.exists():
            candidate.unlink()
        atomic_write_json(candidate, payload)
        validate_runtime_bindings(candidate, check_files=True)
        os.replace(candidate, output)
        report = validate_runtime_bindings(output, check_files=True)
        report.update(
            {
                "status": "frozen",
                "science_ready": True,
                "approved_by": approved_by,
                "approved_at": payload["approved_at"],
                "output": str(output),
            }
        )
        if args.verification_output is not None:
            atomic_write_json(args.verification_output.expanduser().resolve(), report)
    except (RuntimeFreezeError, Runner5JError, OSError, ValueError) as error:
        if candidate is not None and candidate.exists():
            candidate.unlink()
        print(f"FINAL-5J runtime freeze failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"runtime_bindings={report['output']}")
        print(f"binding_sha256={report['binding_sha256']}")
        print(f"runtime_sha256={report['runtime_executable_sha256']}")
        print(f"toolbox_tree_sha256={report['toolbox_tree_sha256']}")
        print(f"stability_sha256={report['stability_profile_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
