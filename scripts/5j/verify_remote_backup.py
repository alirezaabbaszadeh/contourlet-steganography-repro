#!/usr/bin/env python3
"""Re-download and verify every remotely backed FINAL-5J-v1 bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from backup_common import (
    BackupError,
    download_remote_bundle,
    load_json,
    object_map,
    save_ledger,
    utc_now,
    verify_bundle_archive,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--bundle-id", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ledger_path = args.ledger.resolve()
    try:
        ledger = load_json(ledger_path)
        if not isinstance(ledger, dict) or ledger.get("protocol_id") != "FINAL-5J-v1":
            raise BackupError("invalid or mismatched backup ledger")
        objects = object_map(ledger)
        selected = set(args.bundle_id)
        bundles = [
            bundle
            for bundle in ledger.get("bundles", [])
            if not selected or bundle.get("bundle_id") in selected
        ]
        if selected - {str(item.get("bundle_id")) for item in bundles}:
            missing = sorted(selected - {str(item.get("bundle_id")) for item in bundles})
            raise BackupError(f"unknown bundle IDs: {missing}")
        if not bundles:
            raise BackupError("no bundles selected for verification")

        verified: list[str] = []
        mismatches: list[str] = []
        with tempfile.TemporaryDirectory(prefix="ctsteg-5j-verify-all-") as temporary:
            root = Path(temporary)
            for bundle in bundles:
                bundle_id = str(bundle["bundle_id"])
                expected = []
                for object_id in bundle["object_ids"]:
                    try:
                        expected.append(objects[str(object_id)])
                    except KeyError as exc:
                        raise BackupError(
                            f"bundle {bundle_id} references unknown object {object_id}"
                        ) from exc
                try:
                    downloaded = download_remote_bundle(
                        bundle,
                        destination_dir=root / bundle_id,
                    )
                    verify_bundle_archive(
                        downloaded,
                        expected_sha256=str(bundle["sha256"]),
                        expected_objects=expected,
                    )
                except BackupError:
                    mismatches.append(bundle_id)
                    bundle["state"] = "uploaded"
                    bundle["verified_at"] = None
                    for entry in expected:
                        entry["state"] = "uploaded"
                        entry["remote_verified_at"] = None
                    continue
                timestamp = utc_now()
                bundle["state"] = "committed_complete"
                bundle["verified_at"] = timestamp
                for entry in expected:
                    entry["state"] = "committed_complete"
                    entry["remote_verified_at"] = timestamp
                verified.append(bundle_id)
        save_ledger(ledger_path, ledger)
        report = {
            "protocol_id": ledger["protocol_id"],
            "run_id": ledger["run_id"],
            "selected_bundles": len(bundles),
            "verified_bundle_ids": verified,
            "mismatch_bundle_ids": mismatches,
        }
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else report)
        return 0 if not mismatches else 2
    except BackupError as error:
        print(f"remote backup verification failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
