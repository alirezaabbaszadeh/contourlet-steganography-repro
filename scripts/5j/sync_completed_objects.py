#!/usr/bin/env python3
"""Bundle, upload, restore, and verify completed FINAL-5J-v1 objects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping, Sequence

from backup_common import (
    BackupError,
    create_bundle,
    download_remote_bundle,
    load_or_create_ledger,
    object_map,
    partition_entries,
    register_inventory_objects,
    save_ledger,
    upload_filesystem,
    upload_github_release,
    utc_now,
    validate_inventory,
    verify_bundle_archive,
)


DEFAULT_MAX_BUNDLE_BYTES = 512 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument(
        "--backend",
        choices=("filesystem", "github-release"),
        required=True,
    )
    parser.add_argument("--remote-root", type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--release-tag")
    parser.add_argument(
        "--max-bundle-bytes",
        type=int,
        default=DEFAULT_MAX_BUNDLE_BYTES,
    )
    parser.add_argument("--delete-local-bundles-after-verify", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def backend_name(argument: str) -> str:
    return "github_release" if argument == "github-release" else argument


def upload_bundle(
    bundle: Mapping[str, Any],
    *,
    entries: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.backend == "filesystem":
        if args.remote_root is None:
            raise BackupError("--remote-root is required for filesystem backend")
        return upload_filesystem(bundle, args.remote_root.resolve())
    if not args.repository or not args.release_tag:
        raise BackupError(
            "--repository and --release-tag are required for GitHub release backend"
        )
    return upload_github_release(
        bundle,
        repository=args.repository,
        tag=args.release_tag,
        entries=entries,
    )


def verify_ledger_bundle(
    bundle_entry: dict[str, Any],
    *,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> None:
    objects = object_map(ledger)
    expected = []
    for object_id in bundle_entry["object_ids"]:
        try:
            expected.append(objects[str(object_id)])
        except KeyError as exc:
            raise BackupError(
                f"bundle references unknown object: {object_id}"
            ) from exc
    with tempfile.TemporaryDirectory(prefix="ctsteg-5j-verify-") as temporary:
        downloaded = download_remote_bundle(
            bundle_entry,
            destination_dir=Path(temporary),
        )
        verify_bundle_archive(
            downloaded,
            expected_sha256=str(bundle_entry["sha256"]),
            expected_objects=expected,
        )
    timestamp = utc_now()
    bundle_entry["state"] = "committed_complete"
    bundle_entry["verified_at"] = timestamp
    for entry in expected:
        entry["state"] = "committed_complete"
        entry["remote_verified_at"] = timestamp
    save_ledger(ledger_path, ledger)


def resume_uploaded_bundles(
    ledger: dict[str, Any],
    *,
    ledger_path: Path,
) -> int:
    resumed = 0
    for bundle in ledger["bundles"]:
        if bundle.get("state") == "committed_complete":
            continue
        if bundle.get("state") not in {"uploaded", "remote_verified"}:
            raise BackupError(
                f"unsupported incomplete bundle state: {bundle.get('state')!r}"
            )
        verify_ledger_bundle(bundle, ledger=ledger, ledger_path=ledger_path)
        resumed += 1
    return resumed


def main() -> int:
    args = parse_args()
    inventory_path = args.inventory.resolve()
    ledger_path = args.ledger.resolve()
    staging_dir = args.staging_dir.resolve()

    try:
        run_id, inventory_objects = validate_inventory(inventory_path)
        ledger = load_or_create_ledger(ledger_path, run_id)
        resumed = resume_uploaded_bundles(
            ledger,
            ledger_path=ledger_path,
        )
        pending = register_inventory_objects(ledger, inventory_objects)
        save_ledger(ledger_path, ledger)

        unassigned = [
            entry
            for entry in pending
            if entry.get("state") != "committed_complete"
            and entry.get("bundle_id") is None
        ]
        groups = partition_entries(
            unassigned,
            max_bundle_bytes=args.max_bundle_bytes,
        ) if unassigned else []

        created = 0
        uploaded_bytes = 0
        for group in groups:
            sequence = len(ledger["bundles"]) + 1
            bundle = create_bundle(
                run_id=run_id,
                sequence=sequence,
                entries=group,
                output_dir=staging_dir,
            )
            remote = upload_bundle(bundle, entries=group, args=args)
            timestamp = utc_now()
            bundle_entry = {
                "bundle_id": bundle["bundle_id"],
                "asset_name": bundle["asset_name"],
                "sha256": bundle["sha256"],
                "size_bytes": bundle["size_bytes"],
                "object_ids": bundle["object_ids"],
                "classification": bundle["classification"],
                "backend": backend_name(args.backend),
                "remote": remote,
                "state": "uploaded",
                "uploaded_at": timestamp,
                "verified_at": None,
            }
            ledger["bundles"].append(bundle_entry)
            for entry in group:
                entry["state"] = "uploaded"
                entry["bundle_id"] = bundle_entry["bundle_id"]
                entry["uploaded_at"] = timestamp
            save_ledger(ledger_path, ledger)

            verify_ledger_bundle(
                bundle_entry,
                ledger=ledger,
                ledger_path=ledger_path,
            )
            created += 1
            uploaded_bytes += int(bundle["size_bytes"])
            if args.delete_local_bundles_after_verify:
                Path(bundle["path"]).unlink(missing_ok=True)

        committed = sum(
            entry.get("state") == "committed_complete"
            for entry in ledger["objects"]
        )
        incomplete = [
            str(entry["object_id"])
            for entry in ledger["objects"]
            if entry.get("state") != "committed_complete"
        ]
        report = {
            "protocol_id": ledger["protocol_id"],
            "run_id": run_id,
            "registered_objects": len(ledger["objects"]),
            "committed_complete_objects": committed,
            "incomplete_object_ids": incomplete,
            "resumed_bundles": resumed,
            "created_bundles": created,
            "uploaded_bytes": uploaded_bytes,
            "ledger": str(ledger_path),
        }
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else report)
        return 0 if not incomplete else 2
    except BackupError as error:
        print(f"backup sync failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
