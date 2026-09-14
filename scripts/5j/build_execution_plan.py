#!/usr/bin/env python3
"""Expand frozen FINAL-5J-v1 inputs into 530/8,420 content-addressed tasks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib
from typing import Any, Iterable, Mapping, Sequence

from ctsteg.provenance import sha256_json as provenance_sha256_json


PROTOCOL_ID = "FINAL-5J-v1"
FORMAT_VERSION = 2
HASH_FIELDS = ("cover_sha256", "secret_sha256")
HEX64 = set("0123456789abcdef")


class PlanError(ValueError):
    """Fail-closed execution-plan error."""


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


def sha256_json(payload: object) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlanError(f"JSON root must be an object: {path}")
    return value


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in HEX64 for character in value)


def read_pairs(path: Path, *, expected_count: int) -> list[dict[str, str]]:
    try:
        stream = path.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise PlanError(f"manifest missing: {path}") from exc
    with stream:
        reader = csv.DictReader(stream)
        required = {"pair_id", *HASH_FIELDS}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise PlanError(f"manifest lacks required columns: {path}")
        rows: list[dict[str, str]] = []
        seen: set[str] = set()
        for line, row in enumerate(reader, start=2):
            pair_id = (row.get("pair_id") or "").strip()
            if not pair_id or pair_id in seen:
                raise PlanError(f"line {line}: missing or duplicate pair_id")
            seen.add(pair_id)
            normalized = {"pair_id": pair_id}
            for field in HASH_FIELDS:
                value = (row.get(field) or "").strip().lower()
                if not valid_sha256(value):
                    raise PlanError(f"line {line}: invalid {field}")
                normalized[field] = value
            rows.append(normalized)
    if len(rows) != expected_count:
        raise PlanError(
            f"manifest {path} contains {len(rows)} pairs; expected {expected_count}"
        )
    return rows


def source_tree_fingerprint(source_root: Path) -> str:
    if not source_root.is_dir():
        raise PlanError(f"source root missing: {source_root}")
    records = [
        {
            "path": path.relative_to(source_root).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(source_root.rglob("*.py"))
        if path.is_file()
    ]
    if not records:
        raise PlanError("source tree contains no Python files")
    return sha256_json({"schema": 1, "files": records})


def load_format_version(config_path: Path) -> int:
    try:
        with config_path.open("rb") as stream:
            payload = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise PlanError(f"config missing: {config_path}") from exc
    values = payload.get("digital_ad", payload)
    version = values.get("format_version")
    if version != FORMAT_VERSION:
        raise PlanError(
            f"5J execution requires format_version={FORMAT_VERSION}, got {version!r}"
        )
    return int(version)


def baseline_method_fingerprints(
    registry_path: Path,
    *,
    repository_root: Path,
) -> dict[str, str]:
    registry = load_json(registry_path)
    if registry.get("protocol_id") != PROTOCOL_ID:
        raise PlanError("baseline registry protocol mismatch")
    if registry.get("status") != "frozen" or registry.get("main_run_authorized") is not True:
        raise PlanError("baseline registry is not frozen and authorized")
    slots = registry.get("slots")
    if not isinstance(slots, list):
        raise PlanError("baseline registry slots are invalid")
    fingerprints: dict[str, str] = {}
    for expected_slot in ("B1", "B2"):
        matches = [item for item in slots if item.get("slot") == expected_slot]
        if len(matches) != 1:
            raise PlanError(f"baseline registry must contain one {expected_slot} slot")
        slot = matches[0]
        if slot.get("status") != "approved" or slot.get("approved") is not True:
            raise PlanError(f"baseline {expected_slot} is not approved")
        contract_path = repository_root / str(slot.get("contract_path", ""))
        contract = load_json(contract_path.resolve())
        if (
            contract.get("protocol_id") != PROTOCOL_ID
            or contract.get("slot") != expected_slot
            or contract.get("status") != "approved"
            or contract.get("license_review") != "compatible"
        ):
            raise PlanError(f"baseline {expected_slot} contract is not approved")
        for field in (
            "method_name",
            "paper_citation",
            "source_repository",
            "source_commit",
            "license",
            "adapter_fingerprint",
            "approved_by",
            "approved_at",
        ):
            if not str(contract.get(field, "")).strip():
                raise PlanError(f"baseline {expected_slot} missing {field}")
        clean = contract.get("clean_round_trip")
        if not isinstance(clean, dict) or clean.get("status") not in {
            "passed",
            "scientific_failure",
        }:
            raise PlanError(f"baseline {expected_slot} lacks admissible clean evidence")
        if not str(clean.get("evidence_object_id", "")).strip():
            raise PlanError(f"baseline {expected_slot} clean evidence ID is missing")
        fingerprints[expected_slot] = sha256_json(contract)
    return fingerprints


def channel_entries(seed_lock: Mapping[str, Any]) -> list[dict[str, Any]]:
    if (
        seed_lock.get("protocol_id") != PROTOCOL_ID
        or seed_lock.get("status") != "locked_before_results"
    ):
        raise PlanError("attack seed lock is not valid and frozen")
    entries = seed_lock.get("channel_instances")
    if not isinstance(entries, list) or len(entries) != 22:
        raise PlanError("attack seed lock must contain exactly 22 instances")
    identifiers = [str(item.get("id", "")) for item in entries]
    if len(set(identifiers)) != 22 or any(not value for value in identifiers):
        raise PlanError("attack seed instance IDs are missing or duplicated")
    return [dict(item) for item in entries]


def pair_seed(pair_id: str, channel: Mapping[str, Any]) -> int | None:
    if channel.get("stochastic") is False:
        if channel.get("base_seed") is not None:
            raise PlanError(f"deterministic channel {channel.get('id')} has a seed")
        return None
    if channel.get("stochastic") is not True:
        raise PlanError(f"channel {channel.get('id')} has invalid stochastic flag")
    base_seed = channel.get("base_seed")
    if not isinstance(base_seed, int) or not 0 <= base_seed < 2**32:
        raise PlanError(f"channel {channel.get('id')} has invalid base seed")
    material = (
        f"{PROTOCOL_ID}:{pair_id}:{channel['id']}:{base_seed}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % (2**32)


def internal_method_fingerprint(
    method: str,
    *,
    source_fingerprint: str,
) -> str:
    return provenance_sha256_json(
        {
            "protocol_id": PROTOCOL_ID,
            "payload_format_version": FORMAT_VERSION,
            "method": method,
            "source_fingerprint": source_fingerprint,
        }
    )


def embedding_task(
    *,
    component: str,
    pair: Mapping[str, str],
    method: str,
    method_fingerprint: str,
    payload_fraction: float,
    target_psnr_db: float,
    common_identity: Mapping[str, str],
) -> dict[str, Any]:
    material = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "component": component,
        "pair_id": pair["pair_id"],
        "cover_sha256": pair["cover_sha256"],
        "secret_sha256": pair["secret_sha256"],
        "method": method,
        "method_fingerprint": method_fingerprint,
        "payload_fraction": payload_fraction,
        "target_psnr_db": target_psnr_db,
        "payload_format_version": FORMAT_VERSION,
        **common_identity,
    }
    return {
        "embedding_id": sha256_json(material),
        "component": component,
        "pair_id": pair["pair_id"],
        "cover_sha256": pair["cover_sha256"],
        "secret_sha256": pair["secret_sha256"],
        "method": method,
        "method_fingerprint": method_fingerprint,
        "payload_fraction": payload_fraction,
        "target_psnr_db": target_psnr_db,
        "payload_format_version": FORMAT_VERSION,
    }


def evaluation_task(
    embedding: Mapping[str, Any],
    channel: Mapping[str, Any],
    *,
    common_identity: Mapping[str, str],
) -> dict[str, Any]:
    seed = pair_seed(str(embedding["pair_id"]), channel)
    material = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "embedding_id": embedding["embedding_id"],
        "channel_instance_id": channel["id"],
        "family": channel["family"],
        "severity": channel["severity"],
        "realization": channel["realization"],
        "pair_seed": seed,
        **common_identity,
    }
    return {
        "evaluation_id": sha256_json(material),
        "embedding_id": embedding["embedding_id"],
        "component": embedding["component"],
        "pair_id": embedding["pair_id"],
        "method": embedding["method"],
        "channel_instance_id": channel["id"],
        "family": channel["family"],
        "severity": channel["severity"],
        "realization": channel["realization"],
        "pair_seed": seed,
    }


def expand_component(
    *,
    component: str,
    pairs: Sequence[Mapping[str, str]],
    methods: Sequence[str],
    method_fingerprints: Mapping[str, str],
    payload_fractions: Sequence[float],
    target_psnr_values: Sequence[float],
    channels: Sequence[Mapping[str, Any]],
    common_identity: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    embeddings: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    for pair in pairs:
        for method in methods:
            try:
                fingerprint = method_fingerprints[method]
            except KeyError as exc:
                raise PlanError(f"missing method fingerprint: {method}") from exc
            for payload_fraction in payload_fractions:
                for target_psnr in target_psnr_values:
                    embedding = embedding_task(
                        component=component,
                        pair=pair,
                        method=method,
                        method_fingerprint=fingerprint,
                        payload_fraction=float(payload_fraction),
                        target_psnr_db=float(target_psnr),
                        common_identity=common_identity,
                    )
                    embeddings.append(embedding)
                    evaluations.extend(
                        evaluation_task(
                            embedding,
                            channel,
                            common_identity=common_identity,
                        )
                        for channel in channels
                    )
    return embeddings, evaluations


def verify_counts_and_identity(
    plan: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    counts = plan["counts"]
    for key, expected_value in expected.items():
        if counts.get(key) != expected_value:
            raise PlanError(
                f"expanded count {key}={counts.get(key)}; expected {expected_value}"
            )
    embeddings = plan["embeddings"]
    evaluations = plan["evaluations"]
    embedding_ids = [item["embedding_id"] for item in embeddings]
    evaluation_ids = [item["evaluation_id"] for item in evaluations]
    if len(embedding_ids) != len(set(embedding_ids)):
        raise PlanError("duplicate embedding identities detected")
    if len(evaluation_ids) != len(set(evaluation_ids)):
        raise PlanError("duplicate evaluation identities detected")
    known_embeddings = set(embedding_ids)
    if any(item["embedding_id"] not in known_embeddings for item in evaluations):
        raise PlanError("evaluation references an unknown embedding")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument(
        "--study-plan",
        type=Path,
        default=root / "configs/5j/study_plan_v1.json",
    )
    parser.add_argument(
        "--seed-lock",
        type=Path,
        default=root / "configs/5j/seeds.lock.json",
    )
    parser.add_argument(
        "--baseline-registry",
        type=Path,
        default=root / "configs/5j/baseline_registry_v1.json",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/5j/format_v2_layer_integrity.toml",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=root / "src/ctsteg",
    )
    parser.add_argument(
        "--main-manifest",
        type=Path,
        default=root / "data-manifests/5j/main_50_pairs.csv",
    )
    parser.add_argument(
        "--sweep-manifest",
        type=Path,
        default=root / "data-manifests/5j/sweep_10_pairs.csv",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repository_root = args.repository_root.resolve()
        study_path = args.study_plan.resolve()
        seed_path = args.seed_lock.resolve()
        baseline_path = args.baseline_registry.resolve()
        config_path = args.config.resolve()
        main_path = args.main_manifest.resolve()
        sweep_path = args.sweep_manifest.resolve()
        source_root = args.source_root.resolve()

        study = load_json(study_path)
        if study.get("protocol_id") != PROTOCOL_ID:
            raise PlanError("study plan protocol mismatch")
        expected_counts = study.get("expected_counts")
        if not isinstance(expected_counts, dict):
            raise PlanError("study plan expected_counts are invalid")
        if study.get("freeze_rules", {}).get("outcome_driven_expansion_prohibited") is not True:
            raise PlanError("outcome-driven expansion prohibition is missing")
        seed_lock = load_json(seed_path)
        channels = channel_entries(seed_lock)
        channel_by_id = {str(item["id"]): item for item in channels}

        load_format_version(config_path)
        main_pairs = read_pairs(
            main_path,
            expected_count=int(study["main"]["pair_count"]),
        )
        sweep_pairs = read_pairs(
            sweep_path,
            expected_count=int(study["payload_sweep"]["pair_count"]),
        )
        main_by_id = {item["pair_id"]: item for item in main_pairs}
        if not all(
            pair["pair_id"] in main_by_id
            and pair["cover_sha256"] == main_by_id[pair["pair_id"]]["cover_sha256"]
            and pair["secret_sha256"] == main_by_id[pair["pair_id"]]["secret_sha256"]
            for pair in sweep_pairs
        ):
            raise PlanError("sweep manifest is not an exact-byte subset of main")

        source_fingerprint = source_tree_fingerprint(source_root)
        baseline_fingerprints = baseline_method_fingerprints(
            baseline_path,
            repository_root=repository_root,
        )
        methods = list(study["main"]["methods"])
        method_fingerprints = {
            method: (
                baseline_fingerprints[method]
                if method in baseline_fingerprints
                else internal_method_fingerprint(
                    method,
                    source_fingerprint=source_fingerprint,
                )
            )
            for method in methods
        }

        created_from = {
            "study_plan_sha256": sha256_file(study_path),
            "seed_lock_sha256": sha256_file(seed_path),
            "main_manifest_sha256": sha256_file(main_path),
            "sweep_manifest_sha256": sha256_file(sweep_path),
            "baseline_registry_sha256": sha256_file(baseline_path),
            "config_sha256": sha256_file(config_path),
            "source_fingerprint": source_fingerprint,
        }
        common_identity = dict(created_from)

        main_embeddings, main_evaluations = expand_component(
            component="main",
            pairs=main_pairs,
            methods=methods,
            method_fingerprints=method_fingerprints,
            payload_fractions=(1.0,),
            target_psnr_values=(45.0,),
            channels=channels,
            common_identity=common_identity,
        )
        payload_channels = [
            channel_by_id[channel_id]
            for channel_id in study["payload_sweep"]["channels"]
        ]
        payload_embeddings, payload_evaluations = expand_component(
            component="payload_sweep",
            pairs=sweep_pairs,
            methods=study["payload_sweep"]["methods"],
            method_fingerprints=method_fingerprints,
            payload_fractions=study["payload_sweep"]["incremental_payload_fractions"],
            target_psnr_values=(45.0,),
            channels=payload_channels,
            common_identity=common_identity,
        )
        psnr_channels = [
            channel_by_id[channel_id]
            for channel_id in study["psnr_sweep"]["channels"]
        ]
        psnr_embeddings, psnr_evaluations = expand_component(
            component="psnr_sweep",
            pairs=sweep_pairs,
            methods=study["psnr_sweep"]["methods"],
            method_fingerprints=method_fingerprints,
            payload_fractions=(1.0,),
            target_psnr_values=study["psnr_sweep"]["incremental_target_db"],
            channels=psnr_channels,
            common_identity=common_identity,
        )

        embeddings = [
            *main_embeddings,
            *payload_embeddings,
            *psnr_embeddings,
        ]
        evaluations = [
            *main_evaluations,
            *payload_evaluations,
            *psnr_evaluations,
        ]
        counts = {
            "main_embeddings": len(main_embeddings),
            "main_evaluations": len(main_evaluations),
            "payload_sweep_embeddings": len(payload_embeddings),
            "payload_sweep_evaluations": len(payload_evaluations),
            "psnr_sweep_embeddings": len(psnr_embeddings),
            "psnr_sweep_evaluations": len(psnr_evaluations),
            "total_embeddings": len(embeddings),
            "total_evaluations": len(evaluations),
        }
        material = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "created_from": created_from,
            "counts": counts,
            "embeddings": embeddings,
            "evaluations": evaluations,
        }
        plan_id = sha256_json(material)
        plan = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "plan_id": plan_id,
            "run_id": f"5j-{plan_id[:20]}",
            "created_from": created_from,
            "counts": counts,
            "embeddings": embeddings,
            "evaluations": evaluations,
        }
        verify_counts_and_identity(plan, expected_counts)
        output = (
            {
                "protocol_id": PROTOCOL_ID,
                "plan_id": plan_id,
                "run_id": plan["run_id"],
                "created_from": created_from,
                "counts": counts,
            }
            if args.summary_only
            else plan
        )
        atomic_write_json(args.output.resolve(), output)
        print(
            json.dumps(
                {
                    "plan_id": plan_id,
                    "run_id": plan["run_id"],
                    "counts": counts,
                    "output": str(args.output.resolve()),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (PlanError, KeyError, TypeError, ValueError) as error:
        print(f"execution plan build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
