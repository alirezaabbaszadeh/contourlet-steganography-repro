#!/usr/bin/env python3
"""Build the calibration-only FINAL-5J transform stability profile.

Only cover images from the frozen calibration manifest are used. Every file,
manifest, configuration, and output identity is hash-recorded. The command
refuses to overwrite an existing non-empty profile.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from ctsteg.digital_ad.calibration import (
    StabilityProfile,
    calibrate_stability,
    write_stability_profile,
)
from ctsteg.digital_ad.config import DigitalADConfig
from ctsteg.digital_ad.preprocessing import load_uint8_grayscale
from ctsteg.provenance import sha256_file, sha256_json


PROTOCOL_ID = "FINAL-5J-v1"


class StabilityBuildError(ValueError):
    """Raised when calibration provenance or input validation fails."""


def resolve_manifest_file(manifest: Path, declared: str) -> Path:
    candidate = Path(declared).expanduser()
    if not candidate.is_absolute():
        candidate = manifest.parent / candidate
    resolved = candidate.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise StabilityBuildError(
            f"calibration cover is not a regular file: {resolved}"
        )
    return resolved


def load_calibration_rows(manifest: Path) -> list[dict[str, str]]:
    try:
        stream = manifest.open("r", newline="", encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise StabilityBuildError(
            f"calibration manifest is missing: {manifest}"
        ) from error
    with stream:
        reader = csv.DictReader(stream)
        required = {"pair_id", "split", "cover", "cover_sha256"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise StabilityBuildError(
                "calibration manifest lacks pair_id/split/cover/cover_sha256"
            )
        rows: list[dict[str, str]] = []
        pair_ids: set[str] = set()
        hashes: set[str] = set()
        for line, raw in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in raw.items()}
            pair_id = row["pair_id"]
            if not pair_id or pair_id in pair_ids:
                raise StabilityBuildError(
                    f"line {line}: missing or duplicate pair_id"
                )
            if row["split"] != "calibration":
                raise StabilityBuildError(
                    f"line {line}: split must be calibration"
                )
            expected = row["cover_sha256"]
            if len(expected) != 64 or any(
                character not in "0123456789abcdef" for character in expected
            ):
                raise StabilityBuildError(
                    f"line {line}: invalid cover_sha256"
                )
            if expected in hashes:
                raise StabilityBuildError(
                    f"line {line}: duplicate calibration cover bytes"
                )
            pair_ids.add(pair_id)
            hashes.add(expected)
            rows.append(row)
    if len(rows) < 2:
        raise StabilityBuildError(
            "at least two calibration pairs are required"
        )
    return rows


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=root / "data-manifests/5j/calibration.csv",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=root / "configs/5j/format_v2_layer_integrity.toml",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = args.manifest.resolve()
        config_path = args.config.resolve()
        output = args.output.resolve()
        rows = load_calibration_rows(manifest)
        covers = []
        input_records: list[dict[str, Any]] = []
        for row in rows:
            cover_path = resolve_manifest_file(manifest, row["cover"])
            actual = sha256_file(cover_path)
            expected = row["cover_sha256"]
            if actual != expected:
                raise StabilityBuildError(
                    f"cover SHA-256 mismatch for {row['pair_id']}: "
                    f"{actual} != {expected}"
                )
            covers.append(load_uint8_grayscale(cover_path, size=512))
            input_records.append(
                {
                    "pair_id": row["pair_id"],
                    "cover": str(cover_path),
                    "cover_sha256": actual,
                }
            )
        config = DigitalADConfig.from_toml(config_path).validate()
        calibrated = calibrate_stability(covers, config=config)
        extended = dict(calibrated.artifact)
        extended.update(
            {
                "protocol_id": PROTOCOL_ID,
                "calibration_manifest": str(manifest),
                "calibration_manifest_sha256": sha256_file(manifest),
                "config": str(config_path),
                "config_sha256": sha256_file(config_path),
                "inputs": input_records,
                "input_set_sha256": sha256_json(input_records),
                "profile_identity": "",
            }
        )
        extended["profile_identity"] = sha256_json(
            {
                key: value
                for key, value in extended.items()
                if key != "profile_identity"
            }
        )
        profile = StabilityProfile(
            values=calibrated.values,
            artifact=extended,
        )
        write_stability_profile(output, profile)
        report = {
            "protocol_id": PROTOCOL_ID,
            "output": str(output),
            "output_sha256": sha256_file(output),
            "profile_identity": extended["profile_identity"],
            "image_count": len(covers),
            "transform_profile": extended["transform_profile"],
            "transform_fingerprint": extended["transform_fingerprint"],
        }
    except (
        StabilityBuildError,
        FileExistsError,
        OSError,
        ValueError,
    ) as error:
        print(f"FINAL-5J stability build failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
