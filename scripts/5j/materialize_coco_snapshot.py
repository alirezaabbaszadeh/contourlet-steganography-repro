#!/usr/bin/env python3
"""Finalize the Git-tracked COCO snapshot for FINAL-5J-v1.

This command is run only after ``bootstrap_coco_data.py`` has produced the 54
preprocessed candidate pairs and frozen split manifests. It intentionally keeps
raw COCO downloads out of Git. The committed snapshot contains only the exact
512x512/128x128 PNG bytes used by the experiment, sanitized source provenance,
attribution, the candidate catalog, frozen manifests, and a content inventory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


PROTOCOL_ID = "FINAL-5J-v1"
EXPECTED_PAIRS = 54
EXPECTED_SOURCES = 108
CC_BY = {
    "http://creativecommons.org/licenses/by/2.0/",
    "https://creativecommons.org/licenses/by/2.0/",
}


class SnapshotError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, payload: object) -> None:
    atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SnapshotError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise SnapshotError(f"JSON root must be an object: {path}")
    return value


def repo_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise SnapshotError(f"snapshot file is outside repository: {path}") from error


def sanitize_role(
    role: Mapping[str, Any],
    *,
    derived_path: Path,
    root: Path,
) -> dict[str, Any]:
    license_url = str(role.get("license_url", "")).strip()
    if license_url not in CC_BY:
        raise SnapshotError(f"non-CC-BY source reached snapshot: {license_url!r}")
    if not derived_path.is_file():
        raise SnapshotError(f"derived image missing: {derived_path}")
    actual = sha256_file(derived_path)
    expected = str(role.get("derived_sha256", ""))
    if actual != expected:
        raise SnapshotError(f"derived SHA-256 mismatch: {derived_path}")
    return {
        "coco_image_id": int(role["id"]),
        "file_name": str(role["file_name"]),
        "original_width": int(role["width"]),
        "original_height": int(role["height"]),
        "coco_url": str(role.get("coco_url", "")),
        "flickr_url": str(role.get("flickr_url", "")),
        "date_captured": str(role.get("date_captured", "")),
        "license_id": int(role["license_id"]),
        "license_name": str(role.get("license_name", "")),
        "license_url": license_url,
        "source_sha256": str(role["source_sha256"]),
        "derived_path": repo_relative(derived_path, root),
        "derived_sha256": actual,
    }


def markdown_attribution(metadata: Mapping[str, Any]) -> str:
    lines = [
        "# FINAL-5J COCO Attribution",
        "",
        "This directory contains deterministic grayscale derivatives of COCO 2017 validation images used by FINAL-5J-v1.",
        "Only source records declaring Creative Commons Attribution 2.0 were admitted.",
        "Each derivative is center-fitted, converted to Pillow mode L, and resized with bicubic resampling.",
        "Original image copyright remains with the corresponding source licensor/contributor.",
        "",
        "License: https://creativecommons.org/licenses/by/2.0/",
        "",
        "| Pair | Role | COCO image ID | Source | License | Derived file |",
        "|---|---|---:|---|---|---|",
    ]
    for pair in metadata["pairs"]:
        for role_name in ("cover", "secret"):
            role = pair[role_name]
            source = role["flickr_url"] or role["coco_url"]
            lines.append(
                f"| {pair['pair_id']} | {role_name} | {role['coco_image_id']} | {source} | [CC BY 2.0]({role['license_url']}) | `{role['derived_path']}` |"
            )
    lines.extend([
        "",
        "The machine-readable `SOURCE_METADATA.json` is authoritative for source URLs and SHA-256 values.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=root)
    parser.add_argument("--prepared-dir", type=Path, default=root / "data/5j/coco2017/prepared")
    parser.add_argument("--preparation-report", type=Path, default=root / "data/5j/coco2017/prepared/preparation_report.json")
    parser.add_argument("--freeze-report", type=Path, default=root / "data-manifests/5j/data_freeze_report.json")
    parser.add_argument("--data-registry", type=Path, default=root / "configs/5j/data_registry_v1.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository_root.resolve()
    prepared = args.prepared_dir.resolve()
    try:
        report = load_json(args.preparation_report.resolve())
        freeze = load_json(args.freeze_report.resolve())
        if report.get("protocol_id") != PROTOCOL_ID or freeze.get("protocol_id") != PROTOCOL_ID:
            raise SnapshotError("protocol mismatch")
        if report.get("outcome_blind") is not True or freeze.get("outcome_blind") is not True:
            raise SnapshotError("data selection must be outcome-blind")
        if int(report.get("candidate_pair_count", -1)) != EXPECTED_PAIRS:
            raise SnapshotError("candidate pair count is not 54")
        if int(report.get("selected_source_count", -1)) != EXPECTED_SOURCES:
            raise SnapshotError("selected source count is not 108")
        pairs = report.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != EXPECTED_PAIRS:
            raise SnapshotError("preparation provenance must contain 54 pairs")

        sanitized_pairs: list[dict[str, Any]] = []
        source_ids: set[int] = set()
        for pair in pairs:
            if not isinstance(pair, Mapping):
                raise SnapshotError("invalid pair provenance")
            pair_id = str(pair.get("pair_id", ""))
            if not pair_id:
                raise SnapshotError("pair_id missing")
            cover_path = prepared / "covers" / f"{pair_id}.png"
            secret_path = prepared / "secrets" / f"{pair_id}.png"
            cover = sanitize_role(pair["cover"], derived_path=cover_path, root=root)
            secret = sanitize_role(pair["secret"], derived_path=secret_path, root=root)
            for item in (cover, secret):
                image_id = int(item["coco_image_id"])
                if image_id in source_ids:
                    raise SnapshotError(f"source image reused: {image_id}")
                source_ids.add(image_id)
            sanitized_pairs.append({"pair_id": pair_id, "cover": cover, "secret": secret})
        if len(source_ids) != EXPECTED_SOURCES:
            raise SnapshotError("source cardinality is not 108")

        manifests = {
            "calibration": root / "data-manifests/5j/calibration.csv",
            "dry_run": root / "data-manifests/5j/dry_run.csv",
            "main": root / "data-manifests/5j/main_50_pairs.csv",
            "sweep": root / "data-manifests/5j/sweep_10_pairs.csv",
        }
        manifest_hashes: dict[str, str] = {}
        declared_hashes = freeze.get("manifest_sha256", {})
        for name, path in manifests.items():
            if not path.is_file():
                raise SnapshotError(f"frozen manifest missing: {path}")
            digest = sha256_file(path)
            if digest != declared_hashes.get(name):
                raise SnapshotError(f"freeze report hash mismatch for {name}")
            manifest_hashes[name] = digest

        metadata = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "dataset": "COCO 2017 validation",
            "source_policy": "CC BY 2.0 only",
            "preprocessing_id": str(report.get("preprocessing_id", "")),
            "outcome_blind": True,
            "pair_count": EXPECTED_PAIRS,
            "unique_source_count": EXPECTED_SOURCES,
            "annotation_sha256": str(report.get("annotation_sha256", "")),
            "selection_rule": str(report.get("selection_rule", "")),
            "pairs": sanitized_pairs,
        }
        metadata_path = prepared / "SOURCE_METADATA.json"
        attribution_path = prepared / "ATTRIBUTION.md"
        atomic_json(metadata_path, metadata)
        atomic_text(attribution_path, markdown_attribution(metadata))

        tracked_files = sorted(
            [path for path in (prepared / "covers").glob("*.png")]
            + [path for path in (prepared / "secrets").glob("*.png")]
            + [prepared / "candidate_pairs.csv", metadata_path, attribution_path]
            + list(manifests.values())
        )
        inventory = [
            {
                "path": repo_relative(path, root),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in tracked_files
        ]
        snapshot = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "dataset": "COCO 2017 validation",
            "license_policy": "CC BY 2.0 only",
            "outcome_blind": True,
            "pair_count": EXPECTED_PAIRS,
            "unique_source_count": EXPECTED_SOURCES,
            "manifest_sha256": manifest_hashes,
            "file_count": len(inventory),
            "byte_count": sum(int(item["size"]) for item in inventory),
            "files": inventory,
        }
        atomic_json(prepared / "SNAPSHOT.json", snapshot)

        registry_path = args.data_registry.resolve()
        registry = load_json(registry_path)
        registry["status"] = "frozen"
        registry["main_run_authorized"] = True
        registry["blockers"] = []
        atomic_json(registry_path, registry)
    except (SnapshotError, OSError, ValueError, KeyError, TypeError) as error:
        print(f"FINAL-5J COCO snapshot finalization failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "status": "frozen",
        "pair_count": EXPECTED_PAIRS,
        "unique_source_count": EXPECTED_SOURCES,
        "snapshot": str((prepared / "SNAPSHOT.json").resolve()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
