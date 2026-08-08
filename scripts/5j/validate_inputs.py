#!/usr/bin/env python3
"""Validate FINAL-5J-v1 data manifests, baseline contracts, and attack seeds."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

PROTOCOL_ID = "FINAL-5J-v1"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RIGHTS = {
    "public_domain",
    "redistribution_permitted",
    "research_use_only",
    "private_permission",
    "metadata_only",
}
MODES = {"L", "RGB", "RGBA"}
HEADER = [
    "pair_id",
    "split",
    "cover",
    "secret",
    "cover_sha256",
    "secret_sha256",
    "cover_source",
    "secret_source",
    "cover_rights_status",
    "secret_rights_status",
    "cover_license",
    "secret_license",
    "cover_width",
    "cover_height",
    "secret_width",
    "secret_height",
    "cover_mode",
    "secret_mode",
    "preprocessing_id",
    "redistribution_allowed",
    "private_archive_object_id",
    "notes",
]


class ValidationError(ValueError):
    """Raised when implementation scaffolding is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root must be an object: {path}")
    return value


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def uint32_seed(text: str) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32)


def expected_channel_ids(plan: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for channel in plan["main"]["channel_instances"]:
        channel_id = str(channel["id"])
        realizations = int(channel["realizations"])
        if realizations == 1:
            result.append(channel_id)
        else:
            result.extend(f"{channel_id}_r{index}" for index in range(1, realizations + 1))
    return result


def validate_seed_lock(plan: dict[str, Any], lock: dict[str, Any], errors: list[str]) -> None:
    require(lock.get("protocol_id") == PROTOCOL_ID, "seed lock protocol_id mismatch", errors)
    require(lock.get("status") == "locked_before_results", "seed lock is not frozen", errors)
    entries = lock.get("channel_instances")
    if not isinstance(entries, list):
        errors.append("seed lock channel_instances must be an array")
        return

    ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
    expected_ids = expected_channel_ids(plan)
    require(ids == expected_ids, f"seed channel IDs differ from plan: {ids!r}", errors)
    require(len(ids) == 22 and len(set(ids)) == 22, "seed lock must contain 22 unique instances", errors)

    observed_seeds: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("seed entry must be an object")
            continue
        instance_id = str(entry.get("id", ""))
        stochastic = entry.get("stochastic")
        seed = entry.get("base_seed")
        if stochastic is True:
            expected = uint32_seed(f"{PROTOCOL_ID}:{instance_id}")
            require(seed == expected, f"base seed mismatch for {instance_id}: {seed!r} != {expected}", errors)
            if isinstance(seed, int):
                require(seed not in observed_seeds, f"duplicate stochastic base seed: {seed}", errors)
                observed_seeds.add(seed)
        elif stochastic is False:
            require(seed is None, f"deterministic channel {instance_id} must have null seed", errors)
        else:
            errors.append(f"stochastic must be boolean for {instance_id}")


def validate_template(path: Path, errors: list[str]) -> None:
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            reader = csv.reader(stream)
            header = next(reader)
            extra = next(reader, None)
    except FileNotFoundError:
        errors.append(f"manifest template missing: {path}")
        return
    require(header == HEADER, f"manifest template header mismatch: {path}", errors)
    require(extra is None, f"manifest template must contain no data rows: {path}", errors)


def parse_bool(value: str, *, field: str, line: int) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValidationError(f"line {line}: {field} must be true or false")


def positive_int(value: str, *, field: str, line: int) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ValidationError(f"line {line}: {field} must be an integer") from exc
    if result <= 0:
        raise ValidationError(f"line {line}: {field} must be positive")
    return result


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(
    path: Path,
    *,
    required_split: str,
    check_files: bool,
) -> list[dict[str, Any]]:
    try:
        stream = path.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ValidationError(f"final manifest missing: {path}") from exc

    with stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADER:
            raise ValidationError(f"final manifest header mismatch: {path}")
        rows: list[dict[str, Any]] = []
        pair_ids: set[str] = set()
        for line, row in enumerate(reader, start=2):
            pair_id = (row.get("pair_id") or "").strip()
            if not SAFE_ID.fullmatch(pair_id):
                raise ValidationError(f"line {line}: invalid pair_id {pair_id!r}")
            if pair_id in pair_ids:
                raise ValidationError(f"line {line}: duplicate pair_id {pair_id!r}")
            pair_ids.add(pair_id)

            split = (row.get("split") or "").strip()
            if split != required_split:
                raise ValidationError(
                    f"line {line}: split {split!r} must equal {required_split!r}"
                )

            normalized: dict[str, Any] = dict(row)
            for name in ("cover_sha256", "secret_sha256"):
                value = (row.get(name) or "").strip()
                if not HEX64.fullmatch(value):
                    raise ValidationError(f"line {line}: invalid {name}")
                normalized[name] = value

            for name in ("cover_source", "secret_source", "cover_license", "secret_license"):
                if not (row.get(name) or "").strip():
                    raise ValidationError(f"line {line}: {name} must not be empty")

            for name in ("cover_rights_status", "secret_rights_status"):
                value = (row.get(name) or "").strip()
                if value not in RIGHTS:
                    raise ValidationError(f"line {line}: unsupported {name}={value!r}")

            for name in ("cover_width", "cover_height", "secret_width", "secret_height"):
                normalized[name] = positive_int(row.get(name) or "", field=name, line=line)

            for name in ("cover_mode", "secret_mode"):
                value = (row.get(name) or "").strip()
                if value not in MODES:
                    raise ValidationError(f"line {line}: unsupported {name}={value!r}")

            preprocessing_id = (row.get("preprocessing_id") or "").strip()
            if not SAFE_ID.fullmatch(preprocessing_id):
                raise ValidationError(f"line {line}: invalid preprocessing_id")

            redistribution = parse_bool(
                row.get("redistribution_allowed") or "",
                field="redistribution_allowed",
                line=line,
            )
            normalized["redistribution_allowed"] = redistribution
            archive_id = (row.get("private_archive_object_id") or "").strip()
            if not redistribution and not archive_id:
                raise ValidationError(
                    f"line {line}: non-redistributable inputs require private_archive_object_id"
                )

            for role in ("cover", "secret"):
                declared = (row.get(role) or "").strip()
                if not declared:
                    raise ValidationError(f"line {line}: {role} path must not be empty")
                if check_files:
                    resolved = (path.parent / declared).resolve() if not Path(declared).is_absolute() else Path(declared).resolve()
                    if not resolved.is_file():
                        raise ValidationError(f"line {line}: {role} file missing: {resolved}")
                    actual = hash_file(resolved)
                    expected = normalized[f"{role}_sha256"]
                    if actual != expected:
                        raise ValidationError(
                            f"line {line}: {role} SHA-256 mismatch: {actual} != {expected}"
                        )
            rows.append(normalized)

    if not rows:
        raise ValidationError(f"final manifest contains no rows: {path}")
    return rows


def validate_baselines(
    repo_root: Path,
    registry: dict[str, Any],
    errors: list[str],
    blockers: list[str],
) -> None:
    require(registry.get("protocol_id") == PROTOCOL_ID, "baseline registry protocol mismatch", errors)
    slots = registry.get("slots")
    if not isinstance(slots, list):
        errors.append("baseline registry slots must be an array")
        return
    require([slot.get("slot") for slot in slots] == ["B1", "B2"], "baseline slots must be B1 then B2", errors)

    for slot in slots:
        slot_id = str(slot.get("slot", ""))
        contract_path = repo_root / str(slot.get("contract_path", ""))
        try:
            contract = load_json(contract_path)
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        require(contract.get("protocol_id") == PROTOCOL_ID, f"{slot_id} protocol mismatch", errors)
        require(contract.get("slot") == slot_id, f"{slot_id} contract slot mismatch", errors)
        status = contract.get("status")
        approved = slot.get("approved") is True and status == "approved"
        if not approved:
            blockers.append(f"{slot_id} is not approved")
            continue

        require(contract.get("license_review") == "compatible", f"{slot_id} license not compatible", errors)
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
            require(bool(str(contract.get(field, "")).strip()), f"{slot_id} missing {field}", errors)
        clean = contract.get("clean_round_trip", {})
        require(
            clean.get("status") in {"passed", "scientific_failure"},
            f"{slot_id} clean round-trip has no admissible outcome",
            errors,
        )
        require(bool(str(clean.get("evidence_object_id", "")).strip()), f"{slot_id} clean evidence missing", errors)


def validate_data(
    repo_root: Path,
    registry: dict[str, Any],
    *,
    check_files: bool,
    errors: list[str],
    blockers: list[str],
) -> dict[str, list[dict[str, Any]]]:
    require(registry.get("protocol_id") == PROTOCOL_ID, "data registry protocol mismatch", errors)
    manifests = registry.get("manifests")
    if not isinstance(manifests, dict):
        errors.append("data registry manifests must be an object")
        return {}

    expected_sets = ["calibration", "dry_run", "main", "sweep"]
    require(list(manifests) == expected_sets, f"data sets must be ordered {expected_sets}", errors)

    loaded: dict[str, list[dict[str, Any]]] = {}
    for name in expected_sets:
        spec = manifests.get(name, {})
        template_path = repo_root / str(spec.get("template_path", ""))
        validate_template(template_path, errors)
        final_path = repo_root / str(spec.get("final_path", ""))
        if not final_path.is_file():
            blockers.append(f"final {name} manifest is missing")
            continue
        try:
            rows = read_manifest(
                final_path,
                required_split=str(spec.get("required_split", "")),
                check_files=check_files,
            )
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        target = int(spec.get("target_count", 0))
        rule = spec.get("size_rule")
        if rule == "exact":
            require(len(rows) == target, f"{name} must contain exactly {target} rows", errors)
        elif rule == "minimum":
            require(len(rows) >= target, f"{name} must contain at least {target} rows", errors)
        else:
            errors.append(f"unsupported size rule for {name}: {rule!r}")
        loaded[name] = rows

    if {"main", "sweep"}.issubset(loaded):
        main_by_id = {row["pair_id"]: row for row in loaded["main"]}
        sweep_ids = {row["pair_id"] for row in loaded["sweep"]}
        require(sweep_ids.issubset(main_by_id), "sweep pair IDs must be a subset of main", errors)
        for row in loaded["sweep"]:
            main_row = main_by_id.get(row["pair_id"])
            if main_row:
                require(
                    row["cover_sha256"] == main_row["cover_sha256"]
                    and row["secret_sha256"] == main_row["secret_sha256"],
                    f"sweep pair {row['pair_id']} bytes differ from main",
                    errors,
                )

    for left, right in (("calibration", "dry_run"), ("calibration", "main"), ("dry_run", "main")):
        if left not in loaded or right not in loaded:
            continue
        left_ids = {row["pair_id"] for row in loaded[left]}
        right_ids = {row["pair_id"] for row in loaded[right]}
        require(left_ids.isdisjoint(right_ids), f"{left} and {right} pair IDs overlap", errors)
        left_hashes = {row[key] for row in loaded[left] for key in ("cover_sha256", "secret_sha256")}
        right_hashes = {row[key] for row in loaded[right] for key in ("cover_sha256", "secret_sha256")}
        require(left_hashes.isdisjoint(right_hashes), f"{left} and {right} image bytes overlap", errors)

    if "main" in loaded:
        covers = [row["cover_sha256"] for row in loaded["main"]]
        secrets = [row["secret_sha256"] for row in loaded["main"]]
        require(len(covers) == len(set(covers)), "main covers must be unique", errors)
        require(len(secrets) == len(set(secrets)), "main secrets must be unique", errors)

    return loaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="verify restored image files and their SHA-256 values",
    )
    parser.add_argument(
        "--require-science-ready",
        action="store_true",
        help="fail unless all manifests and B1/B2 approvals are complete",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    errors: list[str] = []
    blockers: list[str] = []

    try:
        plan = load_json(repo_root / "configs/5j/study_plan_v1.json")
        seed_lock = load_json(repo_root / "configs/5j/seeds.lock.json")
        data_registry = load_json(repo_root / "configs/5j/data_registry_v1.json")
        baseline_registry = load_json(repo_root / "configs/5j/baseline_registry_v1.json")
    except ValidationError as exc:
        errors.append(str(exc))
        plan = {}
        seed_lock = {}
        data_registry = {}
        baseline_registry = {}

    if plan:
        validate_seed_lock(plan, seed_lock, errors)
    loaded = validate_data(
        repo_root,
        data_registry,
        check_files=args.check_files,
        errors=errors,
        blockers=blockers,
    )
    validate_baselines(repo_root, baseline_registry, errors, blockers)

    if data_registry.get("main_run_authorized") is not True:
        blockers.append("data registry main_run_authorized is false")
    if baseline_registry.get("main_run_authorized") is not True:
        blockers.append("baseline registry main_run_authorized is false")

    blockers = list(dict.fromkeys(blockers))
    science_ready = not errors and not blockers
    report = {
        "valid_scaffolding": not errors,
        "science_ready": science_ready,
        "protocol_id": PROTOCOL_ID,
        "seed_instance_count": len(seed_lock.get("channel_instances", [])) if isinstance(seed_lock, dict) else 0,
        "loaded_manifest_counts": {key: len(value) for key, value in loaded.items()},
        "blockers": blockers,
        "errors": errors,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        if errors:
            print("FINAL-5J input validation errors:", file=sys.stderr)
            for item in errors:
                print(f"- {item}", file=sys.stderr)
        else:
            print("FINAL-5J input scaffolding validation passed")
        if blockers:
            print("Scientific execution blockers:")
            for item in blockers:
                print(f"- {item}")
        print(f"science_ready={str(science_ready).lower()}")

    if errors:
        return 1
    if args.require_science_ready and not science_ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
