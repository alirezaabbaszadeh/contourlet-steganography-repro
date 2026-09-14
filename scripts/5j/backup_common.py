#!/usr/bin/env python3
"""Shared deterministic backup primitives for FINAL-5J-v1."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
from typing import Any, Iterable, Mapping, Sequence


PROTOCOL_ID = "FINAL-5J-v1"
LEDGER_SCHEMA_VERSION = 1
OBJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
CLASSIFICATION_ORDER = {"public": 0, "restricted": 1, "secret": 2}
ENCRYPTION_VALUES = {"none", "client_side_encrypted", "external_secret_custody"}
OBJECT_STATES = {
    "locally_validated",
    "hashed",
    "uploaded",
    "remote_verified",
    "committed_complete",
}
MAX_GITHUB_ASSET_BYTES = 2 * 1024 * 1024 * 1024 - 1


class BackupError(RuntimeError):
    """Fail-closed backup error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_json_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BackupError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BackupError(f"invalid JSON in {path}: {exc}") from exc


def new_ledger(run_id: str) -> dict[str, Any]:
    if len(run_id.strip()) < 8:
        raise BackupError("run_id must contain at least eight characters")
    created = utc_now()
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "run_id": run_id,
        "created_at": created,
        "updated_at": created,
        "objects": [],
        "bundles": [],
    }


def load_or_create_ledger(path: Path, run_id: str) -> dict[str, Any]:
    if not path.exists():
        return new_ledger(run_id)
    ledger = load_json(path)
    if not isinstance(ledger, dict):
        raise BackupError("backup ledger root must be an object")
    if ledger.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise BackupError("unsupported backup ledger schema version")
    if ledger.get("protocol_id") != PROTOCOL_ID:
        raise BackupError("backup ledger protocol mismatch")
    if ledger.get("run_id") != run_id:
        raise BackupError("backup ledger run_id mismatch")
    if not isinstance(ledger.get("objects"), list) or not isinstance(
        ledger.get("bundles"), list
    ):
        raise BackupError("backup ledger arrays are invalid")
    return ledger


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = utc_now()
    atomic_write_json(path, ledger)


def resolve_inventory_path(inventory_path: Path, declared: str) -> Path:
    candidate = Path(declared).expanduser()
    if not candidate.is_absolute():
        candidate = inventory_path.parent / candidate
    return candidate.resolve()


def validate_inventory(inventory_path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = load_json(inventory_path)
    if not isinstance(payload, dict):
        raise BackupError("inventory root must be an object")
    if payload.get("protocol_id") != PROTOCOL_ID:
        raise BackupError("inventory protocol mismatch")
    run_id = str(payload.get("run_id", "")).strip()
    if len(run_id) < 8:
        raise BackupError("inventory run_id is missing or too short")
    objects = payload.get("objects")
    if not isinstance(objects, list) or not objects:
        raise BackupError("inventory must contain at least one object")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            raise BackupError(f"inventory object {index} must be an object")
        object_id = str(item.get("object_id", "")).strip()
        if not OBJECT_ID_RE.fullmatch(object_id):
            raise BackupError(f"invalid object_id: {object_id!r}")
        if object_id in seen_ids:
            raise BackupError(f"duplicate object_id: {object_id}")
        seen_ids.add(object_id)
        kind = str(item.get("kind", "")).strip()
        if not kind:
            raise BackupError(f"object {object_id} has no kind")
        classification = str(item.get("classification", "")).strip()
        if classification not in CLASSIFICATION_ORDER:
            raise BackupError(
                f"object {object_id} has invalid classification {classification!r}"
            )
        encryption = str(item.get("encryption", "")).strip()
        if encryption not in ENCRYPTION_VALUES:
            raise BackupError(
                f"object {object_id} has invalid encryption {encryption!r}"
            )
        path = resolve_inventory_path(inventory_path, str(item.get("path", "")))
        if not path.is_file() or path.is_symlink():
            raise BackupError(f"object {object_id} is not a regular file: {path}")
        if path in seen_paths:
            raise BackupError(f"duplicate inventory path: {path}")
        seen_paths.add(path)
        if classification == "public" and encryption == "external_secret_custody":
            raise BackupError(
                f"public object {object_id} cannot use external_secret_custody"
            )
        normalized.append(
            {
                "object_id": object_id,
                "kind": kind,
                "path": path,
                "classification": classification,
                "encryption": encryption,
            }
        )
    return run_id, normalized


def register_inventory_objects(
    ledger: dict[str, Any],
    objects: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(item["object_id"]): item for item in ledger["objects"]}
    pending: list[dict[str, Any]] = []
    timestamp = utc_now()
    for item in objects:
        object_id = str(item["object_id"])
        path = Path(item["path"])
        digest = sha256_file(path)
        size = path.stat().st_size
        existing = by_id.get(object_id)
        if existing is not None:
            expected = (
                existing.get("sha256"),
                existing.get("size_bytes"),
                Path(str(existing.get("local_path", ""))).resolve(),
                existing.get("classification"),
                existing.get("encryption"),
            )
            actual = (
                digest,
                size,
                path.resolve(),
                item["classification"],
                item["encryption"],
            )
            if expected != actual:
                raise BackupError(
                    f"object_id {object_id} was reused for different material"
                )
            if existing.get("state") != "committed_complete":
                pending.append(existing)
            continue
        entry = {
            "object_id": object_id,
            "kind": str(item["kind"]),
            "local_path": str(path.resolve()),
            "sha256": digest,
            "size_bytes": size,
            "classification": str(item["classification"]),
            "encryption": str(item["encryption"]),
            "state": "hashed",
            "bundle_id": None,
            "local_validated_at": timestamp,
            "uploaded_at": None,
            "remote_verified_at": None,
        }
        ledger["objects"].append(entry)
        by_id[object_id] = entry
        pending.append(entry)
    return pending


def highest_classification(entries: Iterable[Mapping[str, Any]]) -> str:
    values = list(entries)
    if not values:
        raise BackupError("cannot classify an empty bundle")
    return max(
        (str(item["classification"]) for item in values),
        key=CLASSIFICATION_ORDER.__getitem__,
    )


def partition_entries(
    entries: Sequence[dict[str, Any]],
    *,
    max_bundle_bytes: int,
) -> list[list[dict[str, Any]]]:
    if max_bundle_bytes <= 0 or max_bundle_bytes >= MAX_GITHUB_ASSET_BYTES:
        raise BackupError(
            f"max_bundle_bytes must be within 1..{MAX_GITHUB_ASSET_BYTES - 1}"
        )
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_size = 0
    overhead_per_object = 4096
    for entry in sorted(entries, key=lambda item: str(item["object_id"])):
        estimated = int(entry["size_bytes"]) + overhead_per_object
        if estimated > max_bundle_bytes:
            raise BackupError(
                f"object {entry['object_id']} exceeds the bundle-size policy"
            )
        if current and current_size + estimated > max_bundle_bytes:
            groups.append(current)
            current = []
            current_size = 0
        current.append(entry)
        current_size += estimated
    if current:
        groups.append(current)
    return groups


def _tar_info(name: str, size: int, *, mode: int = 0o600) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mtime = 0
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def create_bundle(
    *,
    run_id: str,
    sequence: int,
    entries: Sequence[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    if not entries:
        raise BackupError("bundle entries must not be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / f".bundle-{sequence:06d}.{os.getpid()}.tmp"
    manifest = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": run_id,
        "sequence": sequence,
        "objects": [
            {
                "object_id": entry["object_id"],
                "kind": entry["kind"],
                "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"],
                "classification": entry["classification"],
                "encryption": entry["encryption"],
                "member": f"objects/{entry['object_id']}/payload.bin",
            }
            for entry in entries
        ],
    }
    manifest_bytes = canonical_json_bytes(manifest)
    with tarfile.open(temporary, mode="w", format=tarfile.PAX_FORMAT) as archive:
        archive.addfile(
            _tar_info("MANIFEST.json", len(manifest_bytes), mode=0o644),
            io.BytesIO(manifest_bytes),
        )
        for entry in entries:
            path = Path(str(entry["local_path"]))
            if sha256_file(path) != entry["sha256"]:
                raise BackupError(
                    f"local object changed before bundling: {entry['object_id']}"
                )
            member = f"objects/{entry['object_id']}/payload.bin"
            with path.open("rb") as stream:
                archive.addfile(_tar_info(member, int(entry["size_bytes"])), stream)
    digest = sha256_file(temporary)
    asset_name = f"ctsteg-5j-{run_id}-bundle-{sequence:06d}-{digest[:12]}.tar"
    final_path = output_dir / asset_name
    os.replace(temporary, final_path)
    if final_path.stat().st_size >= MAX_GITHUB_ASSET_BYTES:
        raise BackupError("bundle exceeds GitHub's per-asset size limit")
    return {
        "bundle_id": f"bundle-{sequence:06d}-{digest[:12]}",
        "asset_name": asset_name,
        "sha256": digest,
        "size_bytes": final_path.stat().st_size,
        "object_ids": [str(entry["object_id"]) for entry in entries],
        "classification": highest_classification(entries),
        "path": final_path,
    }


def run_command(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(arguments),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise BackupError(f"required command not found: {arguments[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "command failed").strip()
        raise BackupError(f"command failed ({arguments[0]}): {detail}") from exc


def github_repository_visibility(repository: str) -> str:
    result = run_command(
        ["gh", "repo", "view", repository, "--json", "visibility"]
    )
    try:
        visibility = json.loads(result.stdout)["visibility"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise BackupError("could not parse GitHub repository visibility") from exc
    return str(visibility).upper()


def github_release_assets(repository: str, tag: str) -> set[str]:
    result = run_command(
        ["gh", "release", "view", tag, "--repo", repository, "--json", "assets"]
    )
    try:
        assets = json.loads(result.stdout)["assets"]
        return {str(item["name"]) for item in assets}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise BackupError("could not parse GitHub release assets") from exc


def upload_filesystem(bundle: Mapping[str, Any], remote_root: Path) -> dict[str, Any]:
    remote_root.mkdir(parents=True, exist_ok=True)
    source = Path(bundle["path"])
    destination = remote_root / str(bundle["asset_name"])
    if destination.exists():
        if sha256_file(destination) != bundle["sha256"]:
            raise BackupError(f"remote asset name collision: {destination}")
    else:
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    return {
        "locator": str(destination.resolve()),
        "repository": None,
        "release_tag": None,
        "asset_name": destination.name,
    }


def upload_github_release(
    bundle: Mapping[str, Any],
    *,
    repository: str,
    tag: str,
    entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    visibility = github_repository_visibility(repository)
    if visibility == "PUBLIC":
        for entry in entries:
            if (
                entry["classification"] != "public"
                and entry["encryption"] != "client_side_encrypted"
            ):
                raise BackupError(
                    "non-public material may enter a public GitHub release only "
                    "as client-side encrypted ciphertext"
                )
    assets = github_release_assets(repository, tag)
    asset_name = str(bundle["asset_name"])
    if asset_name not in assets:
        run_command(
            [
                "gh",
                "release",
                "upload",
                tag,
                str(bundle["path"]),
                "--repo",
                repository,
            ]
        )
    return {
        "locator": f"github-release:{repository}:{tag}:{asset_name}",
        "repository": repository,
        "release_tag": tag,
        "asset_name": asset_name,
    }


def download_remote_bundle(
    bundle_entry: Mapping[str, Any],
    *,
    destination_dir: Path,
) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    backend = str(bundle_entry["backend"])
    remote = bundle_entry["remote"]
    asset_name = str(bundle_entry["asset_name"])
    destination = destination_dir / asset_name
    if backend == "filesystem":
        source = Path(str(remote["locator"]))
        if not source.is_file():
            raise BackupError(f"remote filesystem asset missing: {source}")
        shutil.copyfile(source, destination)
    elif backend == "github_release":
        repository = str(remote.get("repository") or "")
        tag = str(remote.get("release_tag") or "")
        if not repository or not tag:
            raise BackupError("GitHub remote metadata is incomplete")
        run_command(
            [
                "gh",
                "release",
                "download",
                tag,
                "--repo",
                repository,
                "--pattern",
                asset_name,
                "--dir",
                str(destination_dir),
            ]
        )
    else:
        raise BackupError(f"backend {backend!r} cannot be downloaded automatically")
    if not destination.is_file():
        raise BackupError(f"download did not create expected asset: {destination}")
    return destination


def verify_bundle_archive(
    path: Path,
    *,
    expected_sha256: str,
    expected_objects: Sequence[Mapping[str, Any]],
) -> None:
    if sha256_file(path) != expected_sha256:
        raise BackupError(f"remote bundle SHA-256 mismatch: {path}")
    by_id = {str(item["object_id"]): item for item in expected_objects}
    with tarfile.open(path, mode="r:") as archive:
        try:
            manifest_stream = archive.extractfile("MANIFEST.json")
        except KeyError as exc:
            raise BackupError("bundle manifest is missing") from exc
        if manifest_stream is None:
            raise BackupError("bundle manifest is unreadable")
        try:
            manifest = json.loads(manifest_stream.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError("bundle manifest is invalid") from exc
        manifest_objects = manifest.get("objects")
        if not isinstance(manifest_objects, list):
            raise BackupError("bundle manifest objects are invalid")
        if {str(item.get("object_id")) for item in manifest_objects} != set(by_id):
            raise BackupError("bundle object set differs from ledger")
        for item in manifest_objects:
            object_id = str(item["object_id"])
            expected = by_id[object_id]
            member_name = str(item["member"])
            stream = archive.extractfile(member_name)
            if stream is None:
                raise BackupError(f"bundle member is missing: {member_name}")
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
            if digest.hexdigest() != expected["sha256"]:
                raise BackupError(f"object hash mismatch in bundle: {object_id}")
            if size != expected["size_bytes"]:
                raise BackupError(f"object size mismatch in bundle: {object_id}")


def object_map(ledger: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["object_id"]): item for item in ledger["objects"]}
