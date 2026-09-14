#!/usr/bin/env python3
"""Deterministically freeze FINAL-5J calibration, dry-run, main, and sweep pairs.

The input catalog contains already-preprocessed candidate cover/secret pairs and
explicit rights metadata. Selection never inspects algorithmic outcomes:

- candidates are hash-validated and deduplicated;
- a protocol-domain SHA-256 score defines a stable order;
- first 2 pairs -> calibration;
- next 2 pairs -> engineering dry run;
- next 50 pairs -> main study;
- 10 main pairs with the lowest independent sweep score -> sweep subset.

At least 54 valid disjoint candidate pairs are required. The script writes all
four final manifests atomically plus a freeze report. It does not download,
invent, or infer image rights.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

from PIL import Image


PROTOCOL_ID = "FINAL-5J-v1"
SELECTION_VERSION = 1
MANIFEST_HEADER = [
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
CATALOG_REQUIRED = {
    "pair_id",
    "cover",
    "secret",
    "cover_source",
    "secret_source",
    "cover_rights_status",
    "secret_rights_status",
    "cover_license",
    "secret_license",
    "preprocessing_id",
    "redistribution_allowed",
    "private_archive_object_id",
    "notes",
}
RIGHTS = {
    "public_domain",
    "redistribution_permitted",
    "research_use_only",
    "private_permission",
    "metadata_only",
}


class FreezeDataError(ValueError):
    """Raised when candidate data cannot be frozen safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: object) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        json.dump(
            payload,
            stream,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_write_csv(
    path: Path,
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in MANIFEST_HEADER})
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def parse_bool(value: str, *, field: str, pair_id: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise FreezeDataError(
        f"{pair_id}: {field} must be the literal true or false"
    )


def resolve_asset(catalog: Path, declared: str, *, role: str, pair_id: str) -> Path:
    value = Path(declared).expanduser()
    if not value.is_absolute():
        value = catalog.parent / value
    resolved = value.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise FreezeDataError(
            f"{pair_id}: {role} is not a regular file: {resolved}"
        )
    return resolved


def image_metadata(path: Path, *, role: str, pair_id: str) -> dict[str, Any]:
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            mode = image.mode
    except (OSError, ValueError) as error:
        raise FreezeDataError(
            f"{pair_id}: unreadable {role} image: {path}: {error}"
        ) from error
    if role == "cover" and (width, height) != (512, 512):
        raise FreezeDataError(
            f"{pair_id}: cover must already be 512x512, got {width}x{height}"
        )
    if role == "secret" and (width, height) != (128, 128):
        raise FreezeDataError(
            f"{pair_id}: secret must already be 128x128, got {width}x{height}"
        )
    if mode != "L":
        raise FreezeDataError(
            f"{pair_id}: {role} must already be grayscale mode L, got {mode}"
        )
    return {"width": width, "height": height, "mode": mode}


def manifest_relative(path: Path, *, output_dir: Path) -> str:
    try:
        return os.path.relpath(path, output_dir)
    except ValueError:
        return str(path)


def selection_score(row: dict[str, Any], *, domain: str) -> str:
    material = (
        f"{PROTOCOL_ID}:{SELECTION_VERSION}:{domain}:"
        f"{row['pair_id']}:{row['cover_sha256']}:{row['secret_sha256']}"
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def load_candidates(catalog: Path, *, output_dir: Path) -> list[dict[str, Any]]:
    try:
        stream = catalog.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise FreezeDataError(f"candidate catalog is missing: {catalog}") from error
    with stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = sorted(CATALOG_REQUIRED - fields)
        if missing:
            raise FreezeDataError(
                f"candidate catalog is missing columns: {missing}"
            )
        rows: list[dict[str, Any]] = []
        pair_ids: set[str] = set()
        cover_hashes: set[str] = set()
        secret_hashes: set[str] = set()
        all_hashes: set[str] = set()
        for line, raw in enumerate(reader, start=2):
            pair_id = (raw.get("pair_id") or "").strip()
            if not pair_id:
                raise FreezeDataError(f"line {line}: pair_id is empty")
            if pair_id in pair_ids:
                raise FreezeDataError(f"line {line}: duplicate pair_id {pair_id}")
            pair_ids.add(pair_id)
            for field in (
                "cover_source",
                "secret_source",
                "cover_license",
                "secret_license",
                "preprocessing_id",
            ):
                if not (raw.get(field) or "").strip():
                    raise FreezeDataError(
                        f"{pair_id}: required metadata {field} is empty"
                    )
            for field in ("cover_rights_status", "secret_rights_status"):
                value = (raw.get(field) or "").strip()
                if value not in RIGHTS:
                    raise FreezeDataError(
                        f"{pair_id}: unsupported {field}={value!r}"
                    )
            redistribution = parse_bool(
                raw.get("redistribution_allowed") or "",
                field="redistribution_allowed",
                pair_id=pair_id,
            )
            archive_id = (raw.get("private_archive_object_id") or "").strip()
            if not redistribution and not archive_id:
                raise FreezeDataError(
                    f"{pair_id}: restricted data requires private_archive_object_id"
                )

            cover = resolve_asset(
                catalog,
                raw.get("cover") or "",
                role="cover",
                pair_id=pair_id,
            )
            secret = resolve_asset(
                catalog,
                raw.get("secret") or "",
                role="secret",
                pair_id=pair_id,
            )
            cover_meta = image_metadata(cover, role="cover", pair_id=pair_id)
            secret_meta = image_metadata(secret, role="secret", pair_id=pair_id)
            cover_hash = sha256_file(cover)
            secret_hash = sha256_file(secret)
            if cover_hash in cover_hashes:
                raise FreezeDataError(f"{pair_id}: duplicate cover bytes")
            if secret_hash in secret_hashes:
                raise FreezeDataError(f"{pair_id}: duplicate secret bytes")
            if cover_hash in all_hashes or secret_hash in all_hashes:
                raise FreezeDataError(
                    f"{pair_id}: an image byte-identically repeats another role"
                )
            cover_hashes.add(cover_hash)
            secret_hashes.add(secret_hash)
            all_hashes.update((cover_hash, secret_hash))
            row = {
                "pair_id": pair_id,
                "split": "candidate",
                "cover": manifest_relative(cover, output_dir=output_dir),
                "secret": manifest_relative(secret, output_dir=output_dir),
                "cover_sha256": cover_hash,
                "secret_sha256": secret_hash,
                "cover_source": (raw.get("cover_source") or "").strip(),
                "secret_source": (raw.get("secret_source") or "").strip(),
                "cover_rights_status": (
                    raw.get("cover_rights_status") or ""
                ).strip(),
                "secret_rights_status": (
                    raw.get("secret_rights_status") or ""
                ).strip(),
                "cover_license": (raw.get("cover_license") or "").strip(),
                "secret_license": (raw.get("secret_license") or "").strip(),
                "cover_width": cover_meta["width"],
                "cover_height": cover_meta["height"],
                "secret_width": secret_meta["width"],
                "secret_height": secret_meta["height"],
                "cover_mode": cover_meta["mode"],
                "secret_mode": secret_meta["mode"],
                "preprocessing_id": (
                    raw.get("preprocessing_id") or ""
                ).strip(),
                "redistribution_allowed": str(redistribution).lower(),
                "private_archive_object_id": archive_id,
                "notes": (raw.get("notes") or "").strip(),
            }
            row["selection_score"] = selection_score(row, domain="primary")
            row["sweep_score"] = selection_score(row, domain="sweep")
            rows.append(row)
    if len(rows) < 54:
        raise FreezeDataError(
            f"at least 54 valid candidates are required, found {len(rows)}"
        )
    return rows


def with_split(row: dict[str, Any], split: str) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key in MANIFEST_HEADER}
    result["split"] = split
    return result


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data-manifests/5j",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=root / "data-manifests/5j/data_freeze_report.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        catalog = args.catalog.resolve()
        output_dir = args.output_dir.resolve()
        candidates = load_candidates(catalog, output_dir=output_dir)
        ordered = sorted(
            candidates,
            key=lambda row: (row["selection_score"], row["pair_id"]),
        )
        calibration_source = ordered[:2]
        dry_run_source = ordered[2:4]
        main_source = ordered[4:54]
        sweep_source = sorted(
            main_source,
            key=lambda row: (row["sweep_score"], row["pair_id"]),
        )[:10]
        calibration = [with_split(row, "calibration") for row in calibration_source]
        dry_run = [with_split(row, "dry_run") for row in dry_run_source]
        main = [with_split(row, "main") for row in main_source]
        sweep = [with_split(row, "sweep") for row in sweep_source]
        outputs = {
            "calibration": output_dir / "calibration.csv",
            "dry_run": output_dir / "dry_run.csv",
            "main": output_dir / "main_50_pairs.csv",
            "sweep": output_dir / "sweep_10_pairs.csv",
        }
        for name, rows in (
            ("calibration", calibration),
            ("dry_run", dry_run),
            ("main", main),
            ("sweep", sweep),
        ):
            atomic_write_csv(outputs[name], rows)

        excluded = ordered[54:]
        report = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "selection_version": SELECTION_VERSION,
            "catalog": str(catalog),
            "catalog_sha256": sha256_file(catalog),
            "candidate_count": len(candidates),
            "selected_counts": {
                "calibration": len(calibration),
                "dry_run": len(dry_run),
                "main": len(main),
                "sweep": len(sweep),
            },
            "selected_pair_ids": {
                "calibration": [row["pair_id"] for row in calibration],
                "dry_run": [row["pair_id"] for row in dry_run],
                "main": [row["pair_id"] for row in main],
                "sweep": [row["pair_id"] for row in sweep],
            },
            "excluded_pair_ids": [row["pair_id"] for row in excluded],
            "manifest_sha256": {
                name: sha256_file(path) for name, path in outputs.items()
            },
            "selection_rule": (
                "SHA-256 order under protocol/version/domain; first 2 calibration, "
                "next 2 dry-run, next 50 main; 10 lowest independent sweep scores"
            ),
            "outcome_blind": True,
            "report_identity": "",
        }
        report["report_identity"] = sha256_json(
            {key: value for key, value in report.items() if key != "report_identity"}
        )
        atomic_write_json(args.report.resolve(), report)
    except (FreezeDataError, OSError, ValueError) as error:
        print(f"FINAL-5J data freeze failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
