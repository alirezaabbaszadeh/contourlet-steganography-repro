#!/usr/bin/env python3
"""Build the pre-specified manuscript image panel from published archives.

This is a publication utility. It does not rerun embedding, extraction, or any
scientific computation. It selects the first pair in the locked traceability
manifest and reuses the archived C0/C3 image objects.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, Iterable


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents and target != root:
                raise SystemExit(f"Unsafe archive path: {member.name}")
        tf.extractall(destination)


def find_one(root: Path, name: str) -> Path:
    matches = sorted(root.rglob(name))
    if len(matches) != 1:
        raise SystemExit(f"Expected one {name!r} under {root}, found {len(matches)}")
    return matches[0]


def normalise(value: Any) -> str:
    return str(value or "").strip()


def choose_field(row: dict[str, str], candidates: Iterable[str]) -> str:
    lowered = {key.lower(): normalise(value) for key, value in row.items()}
    for candidate in candidates:
        value = lowered.get(candidate.lower(), "")
        if value:
            return value
    return ""


def first_locked_pair(manifest: Path) -> dict[str, str]:
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        row = next(reader, None)
    if not row:
        raise SystemExit(f"Locked traceability manifest is empty: {manifest}")

    pair_id = choose_field(row, ("pair_id", "pair", "id", "case_id"))
    cover = choose_field(row, ("cover", "cover_path", "cover_file", "cover_image"))
    secret = choose_field(row, ("secret", "secret_path", "secret_file", "secret_image"))
    if not pair_id:
        pair_id = f"{Path(cover).stem}--{Path(secret).stem}"
    return {
        "pair_id": pair_id,
        "cover": cover,
        "secret": secret,
        "manifest": str(manifest),
        "row": json.dumps(row, sort_keys=True),
    }


def json_text(paths: Iterable[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            parts.append(json.dumps(data, sort_keys=True))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return "\n".join(parts).lower()


def token_present(text: str, token: str) -> bool:
    token = token.lower().strip()
    if not token:
        return False
    if token in text:
        return True
    stem = Path(token).stem.lower()
    return bool(stem and stem in text)


def method_score(text: str, method: str) -> int:
    method = method.upper()
    patterns = {
        "C0": (
            r'(?<![a-z0-9])c0(?![a-z0-9])',
            r'c0_fixed',
            r'"method(?:_id)?"\s*:\s*"c0',
        ),
        "C3": (
            r'(?<![a-z0-9])c3(?![a-z0-9])',
            r'c3_',
            r'"method(?:_id)?"\s*:\s*"c3',
        ),
    }
    return sum(1 for pattern in patterns[method] if re.search(pattern, text))


def candidate_objects(results_root: Path, pair: dict[str, str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for stego in sorted(results_root.rglob("payload/images/stego.png")):
        object_dir = stego.parents[2]
        payload = object_dir / "payload"
        metadata_paths = (
            object_dir / "task.json",
            object_dir / "result.json",
            object_dir / "producer_result.json",
            payload / "provenance.json",
            payload / "metrics.json",
            payload / "run_status.json",
            payload / "config.json",
        )
        text = json_text(metadata_paths)
        if not text:
            continue
        pair_score = sum(
            int(token_present(text, token))
            for token in (pair["pair_id"], pair["cover"], pair["secret"])
            if token
        )
        candidates.append(
            {
                "object_dir": object_dir,
                "object_id": object_dir.name,
                "payload": payload,
                "text": text,
                "pair_score": pair_score,
                "c0_score": method_score(text, "C0"),
                "c3_score": method_score(text, "C3"),
            }
        )
    return candidates


def select(candidates: list[dict[str, Any]], method: str) -> dict[str, Any]:
    key = f"{method.lower()}_score"
    ranked = sorted(
        (item for item in candidates if item[key] > 0),
        key=lambda item: (item["pair_score"], item[key], item["object_id"]),
        reverse=True,
    )
    if not ranked:
        raise SystemExit(f"No archived embedding object matched {method}")
    best = ranked[0]
    tied = [
        item
        for item in ranked
        if (item["pair_score"], item[key]) == (best["pair_score"], best[key])
    ]
    if best["pair_score"] == 0:
        preview = [
            {
                "object_id": item["object_id"],
                "pair_score": item["pair_score"],
                key: item[key],
            }
            for item in ranked[:10]
        ]
        raise SystemExit(
            f"{method} objects were found, but none matched the first locked pair: "
            + json.dumps(preview, indent=2)
        )
    if len(tied) > 1:
        # Embedding objects are expected to be unique per pair and method. Fail
        # rather than choosing by appearance or filesystem order.
        raise SystemExit(
            f"Ambiguous {method} embedding objects for the first locked pair: "
            + json.dumps([item["object_id"] for item in tied], indent=2)
        )
    return best


def require_image(payload: Path, name: str) -> Path:
    path = payload / "images" / name
    if not path.is_file():
        raise SystemExit(f"Missing archived image: {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capsule", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    capsule_root = args.work_dir / "capsule"
    results_root = args.work_dir / "results"
    safe_extract(args.capsule, capsule_root)
    safe_extract(args.results, results_root)

    manifest = find_one(capsule_root, "traceability-core-v2.csv")
    pair = first_locked_pair(manifest)
    candidates = candidate_objects(results_root, pair)
    c0 = select(candidates, "C0")
    c3 = select(candidates, "C3")

    cover = require_image(c0["payload"], "cover.png")
    secret = require_image(c0["payload"], "secret.png")
    stego_c0 = require_image(c0["payload"], "stego.png")
    stego_c3 = require_image(c3["payload"], "stego.png")
    recovered = require_image(c3["payload"], "recovered.png")

    command = [
        sys.executable,
        str(Path(__file__).with_name("build_representative_panel.py")),
        "--pair-id",
        pair["pair_id"],
        "--cover",
        str(cover),
        "--secret",
        str(secret),
        "--stego-c0",
        str(stego_c0),
        "--stego-c3",
        str(stego_c3),
        "--clean-recovered",
        str(recovered),
        "--output",
        str(args.output),
    ]
    subprocess.run(command, check=True)

    selection = {
        "selection_rule": "first row of traceability-core-v2.csv",
        "pair": pair,
        "c0_object_id": c0["object_id"],
        "c3_object_id": c3["object_id"],
        "source_archives": {
            "capsule": str(args.capsule),
            "results": str(args.results),
        },
    }
    args.output.with_name("representative-pair-selection.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(selection, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
