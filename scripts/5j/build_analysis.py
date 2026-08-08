#!/usr/bin/env python3
"""Build frozen FINAL-5J raw and pair-level statistical analysis outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence

from ctsteg.digital_ad.analysis_5j import (
    Analysis5JError,
    build_analysis_payload,
    load_analysis_inputs,
)
from ctsteg.digital_ad.runtime_5j import load_json_object


PROTOCOL_ID = "FINAL-5J-v1"


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def write_json(path: Path, payload: object) -> None:
    atomic_write_bytes(
        path,
        (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8"),
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    payload = b"".join(
        (
            json.dumps(
                dict(row),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        for row in rows
    )
    atomic_write_bytes(path, payload)


def scalar(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    return value


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalar(row.get(key)) for key in fields})
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parquet_status(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return {
            "status": "not_written",
            "reason": "pyarrow_not_installed",
            "path": str(path),
        }
    table = pa.Table.from_pylist([dict(row) for row in rows])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, path)
    return {
        "status": "written",
        "path": str(path),
        "sha256": sha256_file(path),
        "row_count": len(rows),
    }


def flatten_comparisons(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        absolute = record["absolute_difference"]
        relative = record["relative_difference"]
        direction = record["direction_count"]
        bootstrap = record["cluster_bootstrap"]
        output.append(
            {
                "method_a": record["method_a"],
                "method_b": record["method_b"],
                "metric": record["metric"],
                "paired_n": record["paired_n"],
                "absolute_mean": absolute["mean"],
                "absolute_median": absolute["median"],
                "absolute_iqr": absolute["iqr"],
                "absolute_minimum": absolute["minimum"],
                "absolute_maximum": absolute["maximum"],
                "relative_mean": relative["mean"],
                "positive_pairs": direction["positive"],
                "zero_pairs": direction["zero"],
                "negative_pairs": direction["negative"],
                "bootstrap_mean": bootstrap["mean_difference"],
                "ci95_low": bootstrap["ci95_low"],
                "ci95_high": bootstrap["ci95_high"],
                "paired_wilcoxon_p": record["paired_wilcoxon_p"],
                "holm_adjusted_p": record["holm_adjusted_p"],
            }
        )
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Build a diagnostic partial analysis and record missing objects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.bootstrap_repetitions < 100:
            raise ValueError("bootstrap repetitions must be at least 100")
        plan = load_json_object(args.plan)
        inputs = load_analysis_inputs(
            plan,
            cache_dir=args.cache_dir,
            require_complete=not args.allow_incomplete,
        )
        rows = list(inputs.rows)
        analysis = build_analysis_payload(
            plan,
            rows,
            bootstrap_repetitions=args.bootstrap_repetitions,
        )
        output = args.output_dir.resolve()
        files = {
            "raw_jsonl": output / "raw_evaluations.jsonl",
            "raw_csv": output / "raw_evaluations.csv",
            "raw_parquet": output / "raw_evaluations.parquet",
            "analysis_json": output / "analysis.json",
            "pair_condition_csv": output / "pair_condition_rows.csv",
            "pair_overall_csv": output / "pair_overall_rows.csv",
            "primary_comparisons_csv": output / "primary_comparisons.csv",
            "failure_stage_csv": output / "failure_stage_summary.csv",
            "missing_json": output / "missing_objects.json",
        }
        write_jsonl(files["raw_jsonl"], rows)
        write_csv(files["raw_csv"], rows)
        write_json(files["analysis_json"], analysis)
        write_csv(
            files["pair_condition_csv"],
            analysis["pair_condition_rows"],
        )
        write_csv(files["pair_overall_csv"], analysis["pair_overall_rows"])
        write_csv(
            files["primary_comparisons_csv"],
            flatten_comparisons(analysis["primary_comparisons"]),
        )
        write_csv(
            files["failure_stage_csv"],
            analysis["failure_stage_summary"],
        )
        write_json(
            files["missing_json"],
            {
                "protocol_id": PROTOCOL_ID,
                "missing_object_ids": list(inputs.missing_object_ids),
                "invalid_object_ids": list(inputs.invalid_object_ids),
                "partial_analysis": bool(args.allow_incomplete),
            },
        )
        parquet = parquet_status(files["raw_parquet"], rows)
        inventory = {
            "schema_version": 1,
            "protocol_id": PROTOCOL_ID,
            "run_id": analysis["run_id"],
            "plan_id": analysis["plan_id"],
            "raw_row_count": len(rows),
            "missing_count": len(inputs.missing_object_ids),
            "invalid_count": len(inputs.invalid_object_ids),
            "partial_analysis": bool(args.allow_incomplete),
            "bootstrap_repetitions": args.bootstrap_repetitions,
            "parquet": parquet,
            "files": [],
        }
        for name, path in files.items():
            if name == "raw_parquet" or not path.is_file():
                continue
            inventory["files"].append(
                {
                    "name": name,
                    "path": str(path),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
        inventory_path = output / "analysis_inventory.json"
        write_json(inventory_path, inventory)
    except (
        Analysis5JError,
        Runner5JError,
        OSError,
        ValueError,
    ) as error:
        print(f"FINAL-5J analysis failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(inventory, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
