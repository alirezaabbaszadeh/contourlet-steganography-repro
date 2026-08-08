#!/usr/bin/env python3
"""Verify one locally downloaded or remotely restored FINAL-5J archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from typing import Any


MANIFEST_NAME = "FINAL_ARCHIVE_MANIFEST.json"


class VerifyArchiveError(ValueError):
    """Raised when the final archive is incomplete or hash-divergent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_stream(stream: Any) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def canonical_json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        archive_path = args.archive.resolve()
        if not archive_path.is_file():
            raise VerifyArchiveError(f"archive is missing: {archive_path}")
        archive_sha256 = sha256_file(archive_path)
        if args.expected_sha256 and archive_sha256 != args.expected_sha256:
            raise VerifyArchiveError(
                f"archive SHA-256 mismatch: {archive_sha256} != "
                f"{args.expected_sha256}"
            )
        with tarfile.open(archive_path, mode="r:gz") as archive:
            names = archive.getnames()
            if not names or names[0] != MANIFEST_NAME:
                raise VerifyArchiveError(
                    "internal manifest must be the first member"
                )
            if len(names) != len(set(names)):
                raise VerifyArchiveError(
                    "archive contains duplicate member names"
                )
            manifest_stream = archive.extractfile(MANIFEST_NAME)
            if manifest_stream is None:
                raise VerifyArchiveError("internal manifest cannot be read")
            manifest = json.load(manifest_stream)
            if manifest.get("protocol_id") != "FINAL-5J-v1":
                raise VerifyArchiveError("archive protocol mismatch")
            recorded_inventory = manifest.get("inventory_sha256")
            inventory_material = {
                key: value
                for key, value in manifest.items()
                if key != "inventory_sha256"
            }
            actual_inventory = hashlib.sha256(
                canonical_json_bytes(inventory_material)
            ).hexdigest()
            if recorded_inventory != actual_inventory:
                raise VerifyArchiveError(
                    "internal inventory SHA-256 mismatch"
                )
            entries = manifest.get("files")
            if not isinstance(entries, list):
                raise VerifyArchiveError("archive inventory is invalid")
            expected_names = {MANIFEST_NAME}
            verified_bytes = 0
            for item in entries:
                if not isinstance(item, dict):
                    raise VerifyArchiveError(
                        "archive inventory entry is invalid"
                    )
                name = str(item.get("path", ""))
                if not name.startswith("inputs/") or ".." in Path(name).parts:
                    raise VerifyArchiveError(
                        f"unsafe archive member path: {name}"
                    )
                expected_names.add(name)
                member = archive.getmember(name)
                if not member.isfile():
                    raise VerifyArchiveError(
                        f"inventory member is not a file: {name}"
                    )
                stream = archive.extractfile(member)
                if stream is None:
                    raise VerifyArchiveError(
                        f"cannot read inventory member: {name}"
                    )
                digest, size = sha256_stream(stream)
                if size != int(item.get("size", -1)):
                    raise VerifyArchiveError(f"size mismatch: {name}")
                if digest != item.get("sha256"):
                    raise VerifyArchiveError(f"SHA-256 mismatch: {name}")
                verified_bytes += size
            if set(names) != expected_names:
                extras = sorted(set(names) - expected_names)
                missing = sorted(expected_names - set(names))
                raise VerifyArchiveError(
                    "archive member set mismatch: "
                    f"extras={extras} missing={missing}"
                )
            if int(manifest.get("file_count", -1)) != len(entries):
                raise VerifyArchiveError("archive file_count mismatch")
            if int(manifest.get("byte_count", -1)) != verified_bytes:
                raise VerifyArchiveError("archive byte_count mismatch")
        report = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "archive": str(archive_path),
            "archive_sha256": archive_sha256,
            "archive_size": archive_path.stat().st_size,
            "run_id": manifest["run_id"],
            "plan_id": manifest["plan_id"],
            "classification": manifest["classification"],
            "inventory_sha256": manifest["inventory_sha256"],
            "file_count": manifest["file_count"],
            "verified_byte_count": verified_bytes,
            "verification_status": "final_backup_verified",
        }
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except (
        VerifyArchiveError,
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"FINAL-5J final archive verification failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
