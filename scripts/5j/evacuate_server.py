#!/usr/bin/env python3
"""Prove that no unique FINAL-5J-v1 information remains only on the server."""

from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re
from typing import Any, Iterable

from backup_common import BackupError, atomic_write_json, load_json, sha256_file


SECRET_NAME_PATTERNS = (
    "*.pem",
    "*.key",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*token*",
    "*password*",
    "*credential*",
    "*.lic",
    "*license-key*",
)
SECRET_CONTENT_PATTERNS = (
    re.compile(rb"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(rb"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
)
DEFAULT_IGNORE = (
    "*.tmp",
    "*.swp",
    "*.pid",
    "*.lock",
    ".nfs*",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--ignore-glob", action="append", default=[])
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def matches_any(value: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def appears_secret(path: Path) -> list[str]:
    findings: list[str] = []
    lower_name = path.name.lower()
    for pattern in SECRET_NAME_PATTERNS:
        if fnmatch.fnmatch(lower_name, pattern.lower()):
            findings.append(f"filename:{pattern}")
    if path.suffix.lower() in {".age", ".gpg", ".pgp", ".enc"}:
        return findings
    try:
        with path.open("rb") as stream:
            sample = stream.read(64 * 1024)
    except OSError as exc:
        findings.append(f"unreadable:{exc}")
        return findings
    for pattern in SECRET_CONTENT_PATTERNS:
        if pattern.search(sample):
            findings.append(f"content:{pattern.pattern.decode('ascii')}")
    return findings


def relative_display(path: Path, roots: list[Path]) -> str:
    for root in roots:
        try:
            return f"{root}:{path.relative_to(root)}"
        except ValueError:
            continue
    return str(path)


def main() -> int:
    args = parse_args()
    ledger_path = args.ledger.resolve()
    roots = [root.resolve() for root in args.root]
    report_path = args.report.resolve()
    ignore_patterns = (*DEFAULT_IGNORE, *args.ignore_glob)

    try:
        ledger = load_json(ledger_path)
        if not isinstance(ledger, dict) or ledger.get("protocol_id") != "FINAL-5J-v1":
            raise BackupError("invalid or mismatched backup ledger")
        if not roots or any(not root.is_dir() for root in roots):
            raise BackupError("every evacuation root must be an existing directory")

        ledger_by_path: dict[Path, dict[str, Any]] = {}
        duplicate_ledger_paths: list[str] = []
        for entry in ledger.get("objects", []):
            path = Path(str(entry.get("local_path", ""))).resolve()
            if path in ledger_by_path:
                duplicate_ledger_paths.append(str(path))
            ledger_by_path[path] = entry

        scanned: set[Path] = set()
        server_only: list[str] = []
        special_files: list[str] = []
        remote_hash_mismatches: list[str] = []
        unresolved_secret_files: list[dict[str, Any]] = []
        unuploaded_logs: list[str] = []
        unuploaded_manifests: list[str] = []

        for root in roots:
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root).as_posix()
                if matches_any(relative, ignore_patterns) or matches_any(
                    path.name, ignore_patterns
                ):
                    continue
                if path.is_symlink():
                    special_files.append(relative_display(path, roots))
                    continue
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved == ledger_path or resolved == report_path:
                    continue
                if resolved in scanned:
                    continue
                scanned.add(resolved)

                findings = appears_secret(resolved)
                if findings:
                    unresolved_secret_files.append(
                        {
                            "path": relative_display(resolved, roots),
                            "findings": findings,
                        }
                    )

                entry = ledger_by_path.get(resolved)
                committed = entry is not None and entry.get("state") == "committed_complete"
                if not committed:
                    display = relative_display(resolved, roots)
                    server_only.append(display)
                    lower = resolved.name.lower()
                    if lower.endswith(".log") or "log" in resolved.parts:
                        unuploaded_logs.append(display)
                    if (
                        "manifest" in lower
                        or lower.endswith(".csv")
                        or lower.endswith(".jsonl")
                        or "inputs" in resolved.parts
                    ):
                        unuploaded_manifests.append(display)
                    continue

                actual_hash = sha256_file(resolved)
                if actual_hash != entry.get("sha256"):
                    remote_hash_mismatches.append(relative_display(resolved, roots))

        complete_unbacked = [
            str(entry.get("object_id"))
            for entry in ledger.get("objects", [])
            if entry.get("state") != "committed_complete"
        ]
        missing_local_committed = [
            str(entry.get("object_id"))
            for entry in ledger.get("objects", [])
            if entry.get("state") == "committed_complete"
            and any(
                Path(str(entry.get("local_path", ""))).resolve().is_relative_to(root)
                for root in roots
            )
            and not Path(str(entry.get("local_path", ""))).is_file()
        ]
        incomplete_bundles = [
            str(bundle.get("bundle_id"))
            for bundle in ledger.get("bundles", [])
            if bundle.get("state") != "committed_complete"
        ]

        counts = {
            "complete_unbacked": len(complete_unbacked),
            "unique_server_only_files": len(server_only),
            "unuploaded_logs": len(unuploaded_logs),
            "unuploaded_manifests": len(unuploaded_manifests),
            "remote_hash_mismatches": len(remote_hash_mismatches),
            "unresolved_secret_files": len(unresolved_secret_files),
            "special_files": len(special_files),
            "duplicate_ledger_paths": len(duplicate_ledger_paths),
            "missing_local_committed": len(missing_local_committed),
            "incomplete_bundles": len(incomplete_bundles),
        }
        evacuation_ready = all(value == 0 for value in counts.values())
        report = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "run_id": ledger.get("run_id"),
            "ledger": str(ledger_path),
            "roots": [str(root) for root in roots],
            "evacuation_ready": evacuation_ready,
            "counts": counts,
            "details": {
                "complete_unbacked_object_ids": complete_unbacked,
                "unique_server_only_files": server_only,
                "unuploaded_logs": unuploaded_logs,
                "unuploaded_manifests": unuploaded_manifests,
                "remote_hash_mismatches": remote_hash_mismatches,
                "unresolved_secret_files": unresolved_secret_files,
                "special_files": special_files,
                "duplicate_ledger_paths": duplicate_ledger_paths,
                "missing_local_committed_object_ids": missing_local_committed,
                "incomplete_bundle_ids": incomplete_bundles,
            },
            "next_action": (
                "Back up and remotely verify this evacuation report before "
                "destroying or reprovisioning the server."
            ),
        }
        atomic_write_json(report_path, report)
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else counts)
        return 0 if evacuation_ready else 2
    except BackupError as error:
        print(f"server evacuation failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
