#!/usr/bin/env python3
"""Verify the FINAL-5J B1/B2 code-freeze manifest against local bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


class FreezeValidationError(ValueError):
    """Raised when a frozen baseline file or identity has changed."""


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--freeze",
        type=Path,
        default=root / "docs/5j/baselines/BASELINE_CODE_FREEZE.json",
    )
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
        if freeze.get("protocol_id") != "FINAL-5J-v1":
            raise FreezeValidationError("baseline freeze protocol mismatch")
        if freeze.get("freeze_id") != "FINAL-5J-BASELINES-v1":
            raise FreezeValidationError("unexpected baseline freeze ID")
        methods = freeze.get("methods")
        if not isinstance(methods, dict) or set(methods) != {"B1", "B2"}:
            raise FreezeValidationError("freeze must define B1 and B2")
        files = freeze.get("files")
        if not isinstance(files, list) or not files:
            raise FreezeValidationError("freeze contains no file records")
        root = args.repository_root.resolve()
        records: list[dict[str, Any]] = []
        paths: set[str] = set()
        for item in files:
            if not isinstance(item, dict):
                raise FreezeValidationError("invalid freeze file record")
            relative = str(item.get("path", ""))
            expected = str(item.get("git_blob_sha", ""))
            if not relative or relative in paths:
                raise FreezeValidationError(
                    f"missing or duplicate freeze path: {relative!r}"
                )
            paths.add(relative)
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
            except ValueError as error:
                raise FreezeValidationError(
                    f"freeze path escapes repository: {relative}"
                ) from error
            if not path.is_file() or path.is_symlink():
                raise FreezeValidationError(
                    f"frozen file is missing or invalid: {relative}"
                )
            actual = git_blob_sha(path)
            if actual != expected:
                raise FreezeValidationError(
                    f"frozen file changed: {relative}: {actual} != {expected}"
                )
            records.append(
                {
                    "path": relative,
                    "git_blob_sha": actual,
                    "role": item.get("role"),
                }
            )
        report = {
            "protocol_id": "FINAL-5J-v1",
            "freeze_id": freeze["freeze_id"],
            "repository_commit": freeze["repository_commit"],
            "valid": True,
            "file_count": len(records),
            "files": records,
        }
    except (
        FreezeValidationError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"FINAL-5J baseline freeze validation failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"freeze_id={report['freeze_id']}")
        print(f"valid={str(report['valid']).lower()}")
        print(f"file_count={report['file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
