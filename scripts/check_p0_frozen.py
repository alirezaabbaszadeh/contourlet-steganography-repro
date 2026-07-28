#!/usr/bin/env python3
"""Fail CI when a frozen numerical P0 file changes unexpectedly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "p0_freeze_manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    for relative, expected in payload["files"].items():
        path = ROOT / relative
        if not path.is_file():
            mismatches.append(f"{relative}: missing")
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(
                f"{relative}: expected {expected}, observed {actual}"
            )
    if mismatches:
        raise SystemExit("P0 freeze violation:\n" + "\n".join(mismatches))
    print(f"P0 freeze verified for {len(payload['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
