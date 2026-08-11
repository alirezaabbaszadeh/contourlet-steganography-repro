"""Internal-only engineering plan for tuning workers before B1/B2 are ready."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from ctsteg.provenance import sha256_file, sha256_json

from .runtime_5j import Runner5JError
from .worker_tuning_5j import canonical_sha256


PROTOCOL_ID = "FINAL-5J-v1"
PURPOSE = "worker_autotune_engineering_v1"
METHODS = ("C0", "C1", "C2", "C3_NP", "C3")
PAYLOAD_FRACTIONS = (0.25, 0.50, 0.75, 1.00)
CHANNELS = (
    {"id": "clean", "family": "clean", "severity": None, "realization": 1},
    {"id": "jpeg-q70", "family": "jpeg", "severity": 70, "realization": 1},
    {"id": "gaussian-v10-r1", "family": "gaussian", "severity": 10, "realization": 1},
    {
        "id": "salt-pepper-d003-r1",
        "family": "salt_pepper",
        "severity": 0.03,
        "realization": 1,
    },
)


def _resolve_input(
    manifest: Path,
    repository_root: Path,
    value: str,
    role: str,
) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = manifest.parent / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError as exc:
        raise Runner5JError(
            f"engineering {role} escapes repository root: {resolved}"
        ) from exc
    if not resolved.is_file() or resolved.is_symlink():
        raise Runner5JError(f"engineering {role} is not a regular file: {resolved}")
    return resolved


def load_engineering_pairs(
    manifest_path: str | Path,
    *,
    repository_root: str | Path,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    manifest = Path(manifest_path).resolve()
    root = Path(repository_root).resolve()
    try:
        with manifest.open("r", newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
    except OSError as error:
        raise Runner5JError(f"cannot read engineering manifest: {manifest}") from error
    if len(rows) != 2:
        raise Runner5JError(
            f"worker engineering manifest must contain exactly two pairs; found {len(rows)}"
        )
    pairs: list[dict[str, str]] = []
    inputs: dict[str, dict[str, str]] = {}
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: str(item.get("pair_id", ""))):
        pair_id = str(row.get("pair_id", "")).strip()
        if not pair_id or pair_id in seen:
            raise Runner5JError("engineering pair IDs are missing or duplicated")
        if str(row.get("split", "")).strip() != "dry_run":
            raise Runner5JError(f"engineering pair {pair_id} is not split=dry_run")
        cover = _resolve_input(manifest, root, str(row.get("cover", "")), "cover")
        secret = _resolve_input(manifest, root, str(row.get("secret", "")), "secret")
        cover_hash = sha256_file(cover)
        secret_hash = sha256_file(secret)
        if cover_hash != str(row.get("cover_sha256", "")):
            raise Runner5JError(f"engineering cover hash mismatch for {pair_id}")
        if secret_hash != str(row.get("secret_sha256", "")):
            raise Runner5JError(f"engineering secret hash mismatch for {pair_id}")
        pairs.append(
            {
                "pair_id": pair_id,
                "cover_sha256": cover_hash,
                "secret_sha256": secret_hash,
            }
        )
        inputs[pair_id] = {"cover": str(cover), "secret": str(secret)}
        seen.add(pair_id)
    return pairs, inputs


def source_tree_fingerprint(root: str | Path) -> str:
    directory = Path(root).resolve()
    files = sorted(path for path in directory.rglob("*.py") if path.is_file())
    if not files:
        raise Runner5JError(f"source tree contains no Python files: {directory}")
    return sha256_json(
        {
            "schema": 1,
            "files": [
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in files
            ],
        }
    )


def _method_fingerprint(method: str, source_fingerprint: str) -> str:
    return sha256_json(
        {
            "protocol_id": PROTOCOL_ID,
            "payload_format_version": 2,
            "method": method,
            "source_fingerprint": source_fingerprint,
        }
    )


def _pair_seed(pair_id: str, channel_id: str) -> int | None:
    if channel_id in {"clean", "jpeg-q70"}:
        return None
    digest = hashlib.sha256(
        f"{PROTOCOL_ID}:{PURPOSE}:{pair_id}:{channel_id}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big")


def build_engineering_plan(
    pairs: Sequence[Mapping[str, str]],
    *,
    source_fingerprint: str,
    config_sha256: str,
    runtime_bindings_sha256: str,
    target_psnr_db: float = 45.0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if len(pairs) != 2:
        raise Runner5JError("engineering worker plan requires exactly two pairs")
    common = {
        "purpose": PURPOSE,
        "source_fingerprint": source_fingerprint,
        "config_sha256": config_sha256,
        "runtime_bindings_sha256": runtime_bindings_sha256,
    }
    embeddings: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    for pair in pairs:
        for method in METHODS:
            fingerprint = _method_fingerprint(method, source_fingerprint)
            for fraction in PAYLOAD_FRACTIONS:
                material = {
                    "schema_version": 1,
                    "protocol_id": PROTOCOL_ID,
                    **common,
                    "pair_id": pair["pair_id"],
                    "cover_sha256": pair["cover_sha256"],
                    "secret_sha256": pair["secret_sha256"],
                    "method": method,
                    "method_fingerprint": fingerprint,
                    "payload_fraction": fraction,
                    "target_psnr_db": target_psnr_db,
                    "payload_format_version": 2,
                }
                embedding_id = sha256_json(material)
                embedding = {
                    "embedding_id": embedding_id,
                    "component": "payload_sweep",
                    "pair_id": pair["pair_id"],
                    "cover_sha256": pair["cover_sha256"],
                    "secret_sha256": pair["secret_sha256"],
                    "method": method,
                    "method_fingerprint": fingerprint,
                    "payload_fraction": fraction,
                    "target_psnr_db": target_psnr_db,
                    "payload_format_version": 2,
                }
                embeddings.append(embedding)
                for channel in CHANNELS:
                    seed = _pair_seed(str(pair["pair_id"]), str(channel["id"]))
                    evaluation_material = {
                        "schema_version": 1,
                        "protocol_id": PROTOCOL_ID,
                        **common,
                        "embedding_id": embedding_id,
                        "channel_instance_id": channel["id"],
                        "family": channel["family"],
                        "severity": channel["severity"],
                        "realization": channel["realization"],
                        "pair_seed": seed,
                    }
                    evaluations.append(
                        {
                            "evaluation_id": sha256_json(evaluation_material),
                            "embedding_id": embedding_id,
                            "component": "payload_sweep",
                            "pair_id": pair["pair_id"],
                            "method": method,
                            "channel_instance_id": channel["id"],
                            "family": channel["family"],
                            "severity": channel["severity"],
                            "realization": channel["realization"],
                            "pair_seed": seed,
                        }
                    )
    if len(embeddings) != 40 or len(evaluations) != 160:
        raise AssertionError("engineering worker plan count mismatch")
    if len({item["embedding_id"] for item in embeddings}) != 40:
        raise AssertionError("engineering embedding IDs are not unique")
    if len({item["evaluation_id"] for item in evaluations}) != 160:
        raise AssertionError("engineering evaluation IDs are not unique")

    plan_material = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "plan_kind": PURPOSE,
        "created_from": common,
        "counts": {"embeddings": 40, "evaluations": 160, "total": 200},
        "embeddings": embeddings,
        "evaluations": evaluations,
    }
    plan_id = sha256_json(plan_material)
    plan = {
        **plan_material,
        "plan_id": plan_id,
        "run_id": f"5j-perf-{plan_id[:20]}",
    }
    index = {
        "plan_id": plan_id,
        "run_id": plan["run_id"],
        "embedding_by_id": {item["embedding_id"]: item for item in embeddings},
        "evaluation_by_id": {item["evaluation_id"]: item for item in evaluations},
    }
    selection_material = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "status": "frozen_before_trial",
        "plan_id": plan_id,
        "run_id": plan["run_id"],
        "selection_policy": PURPOSE,
        "embedding_ids": [item["embedding_id"] for item in embeddings],
        "evaluation_ids": [item["evaluation_id"] for item in evaluations],
    }
    selection = {
        **selection_material,
        "selection_sha256": canonical_sha256(selection_material),
    }
    return plan, index, selection
