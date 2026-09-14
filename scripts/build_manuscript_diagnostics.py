#!/usr/bin/env python3
"""Build claim-safe diagnostic tables and figures from a locked result report.

The script is deliberately schema-tolerant but fail-closed: it accepts CSV,
JSON, JSONL, or Parquet, records the input SHA-256, normalises common field
aliases, and refuses to invent unavailable metrics. It is intended for the
private final-run capsule; no values are hard-coded in the manuscript.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ALIASES = {
    "method": ["method", "method_id", "configuration", "variant"],
    "channel": ["channel", "channel_id", "attack", "attack_id", "attack_name"],
    "severity": ["severity", "attack_severity", "profile", "attack_profile"],
    "pair_id": ["pair_id", "pair", "case_id", "traceability_pair"],
    "run_id": ["run_id", "research_run_id"],
    "base_ber": ["base_ber", "metrics_base_ber", "layer_metrics_base_ber"],
    "detail_ber": ["detail_ber", "metrics_detail_ber", "layer_metrics_detail_ber"],
    "raw_ber": ["raw_ber", "ber", "metrics_raw_ber"],
    "header_valid": ["header_valid", "header_success", "header_crc_valid"],
    "payload_valid": ["payload_valid", "payload_crc_valid", "decode_success", "valid_decode"],
    "failure_stage": ["failure_stage", "decode_failure_stage", "stage"],
    "base_corrected": [
        "base_corrected_symbols", "corrected_symbols_base",
        "decode_metadata_base_corrected_symbols",
    ],
    "detail_corrected": [
        "detail_corrected_symbols", "corrected_symbols_detail",
        "decode_metadata_detail_corrected_symbols",
    ],
    "base_failed_codewords": [
        "base_failed_codewords", "failed_base_codewords",
        "decode_metadata_base_failed_codeword_indices",
    ],
    "detail_failed_codewords": [
        "detail_failed_codewords", "failed_detail_codewords",
        "decode_metadata_detail_failed_codeword_indices",
    ],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}_{key}" if prefix else str(key)
            out.update(flatten(item, child))
    else:
        out[prefix] = value
    return out


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            return [dict(row) for row in csv.DictReader(f)]
    if suffix == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [dict(x) for x in data]
        for key in ("rows", "results", "records", "evaluations"):
            if isinstance(data, dict) and isinstance(data.get(key), list):
                return [dict(x) for x in data[key]]
        if isinstance(data, dict):
            return [data]
        raise ValueError("JSON must contain an object or a list of objects")
    if suffix in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet input requires the research extra: pip install -e '.[research]'") from exc
        return pq.read_table(path).to_pylist()
    raise ValueError(f"Unsupported input format: {suffix}")


def normalise_key(key: str) -> str:
    return "_".join(str(key).strip().lower().replace(".", "_").replace("-", "_").split())


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if text and text[0] in "[{" and text[-1] in "]}":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
    return value


def first(row: dict[str, Any], aliases: Iterable[str]) -> Any:
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return parse_jsonish(row[alias])
    return None


def as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "success", "valid", "ok"}:
        return True
    if text in {"0", "false", "no", "failure", "invalid", "failed"}:
        return False
    return None


def numeric_sum(value: Any) -> float | None:
    value = parse_jsonish(value)
    if isinstance(value, (list, tuple)):
        vals = [as_float(x) for x in value]
        vals = [x for x in vals if x is not None]
        return float(sum(vals)) if vals else None
    return as_float(value)


def list_count(value: Any) -> int | None:
    value = parse_jsonish(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if value in (None, ""):
        return None
    x = as_float(value)
    return int(x) if x is not None else None


def canonicalise(raw: dict[str, Any]) -> dict[str, Any]:
    flat = {normalise_key(k): v for k, v in flatten(raw).items()}
    row: dict[str, Any] = {}
    for name, aliases in ALIASES.items():
        row[name] = first(flat, aliases)
    row["base_ber"] = as_float(row["base_ber"])
    row["detail_ber"] = as_float(row["detail_ber"])
    row["raw_ber"] = as_float(row["raw_ber"])
    row["header_valid"] = as_bool(row["header_valid"])
    row["payload_valid"] = as_bool(row["payload_valid"])
    row["base_corrected"] = numeric_sum(row["base_corrected"])
    row["detail_corrected"] = numeric_sum(row["detail_corrected"])
    row["base_failed_codewords"] = list_count(row["base_failed_codewords"])
    row["detail_failed_codewords"] = list_count(row["detail_failed_codewords"])
    row["method"] = str(row["method"] or "unknown")
    row["channel"] = str(row["channel"] or "unknown")
    row["severity"] = str(row["severity"] or "")
    row["pair_id"] = str(row["pair_id"] or "")
    row["run_id"] = str(row["run_id"] or "")
    row["failure_stage"] = str(row["failure_stage"] or "")
    return row


def mean(values: Iterable[float | None]) -> float | None:
    vals = [x for x in values if x is not None]
    return sum(vals) / len(vals) if vals else None


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def ordered_methods(values: Iterable[str]) -> list[str]:
    preferred = ["C0", "C1", "C2", "C3"]
    unique = sorted(set(values))
    return [x for x in preferred if x in unique] + [x for x in unique if x not in preferred]


def plot_layer_ber(rows: list[dict[str, Any]], outdir: Path) -> bool:
    groups: dict[tuple[str, str], dict[str, list[float | None]]] = defaultdict(lambda: {"base": [], "detail": []})
    for r in rows:
        groups[(r["method"], r["channel"])]["base"].append(r["base_ber"])
        groups[(r["method"], r["channel"])]["detail"].append(r["detail_ber"])
    usable = [(k, mean(v["base"]), mean(v["detail"])) for k, v in groups.items()]
    usable = [x for x in usable if x[1] is not None or x[2] is not None]
    if not usable:
        return False
    usable.sort(key=lambda x: (x[0][1], x[0][0]))
    labels = [f"{m}\n{c}" for (m, c), _, _ in usable]
    base = [b if b is not None else float("nan") for _, b, _ in usable]
    detail = [d if d is not None else float("nan") for _, _, d in usable]
    x = list(range(len(labels)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.62), 4.8))
    ax.bar([i - width / 2 for i in x], base, width, label="Base BER")
    ax.bar([i + width / 2 for i in x], detail, width, label="Detail BER")
    ax.set_ylabel("Bit error rate")
    ax.set_xticks(x, labels, rotation=45, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(outdir / "layer_ber_by_method_channel.pdf")
    fig.savefig(outdir / "layer_ber_by_method_channel.png", dpi=200)
    plt.close(fig)
    return True


def plot_corrections(rows: list[dict[str, Any]], outdir: Path) -> bool:
    grouped: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        vals = [x for x in (r["base_corrected"], r["detail_corrected"]) if x is not None]
        if vals:
            grouped[r["method"]].append(sum(vals))
    if not grouped:
        return False
    methods = ordered_methods(grouped)
    values = [mean(grouped[m]) or 0.0 for m in methods]
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.bar(methods, values)
    ax.set_ylabel("Mean corrected symbols per evaluation")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(outdir / "corrected_symbols_by_method.pdf")
    fig.savefig(outdir / "corrected_symbols_by_method.png", dpi=200)
    plt.close(fig)
    return True


def plot_failures(rows: list[dict[str, Any]], outdir: Path) -> bool:
    counts = Counter(r["failure_stage"] for r in rows if r["failure_stage"])
    if not counts:
        return False
    labels, values = zip(*counts.most_common())
    fig, ax = plt.subplots(figsize=(7.0, max(3.5, len(labels) * 0.45)))
    y = list(range(len(labels)))
    ax.barh(y, values)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Evaluation count")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(outdir / "failure_stage_counts.pdf")
    fig.savefig(outdir / "failure_stage_counts.png", dpi=200)
    plt.close(fig)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="Locked CSV/JSON/JSONL/Parquet report")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-run-id", default="")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input does not exist: {args.input}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = load_rows(args.input)
    rows = [canonicalise(r) for r in raw_rows]
    if not rows:
        raise SystemExit("No rows found")

    observed_run_ids = sorted({r["run_id"] for r in rows if r["run_id"]})
    if args.expected_run_id and observed_run_ids and observed_run_ids != [args.expected_run_id]:
        raise SystemExit(f"Run-id mismatch: observed {observed_run_ids}, expected {args.expected_run_id}")

    fields = list(rows[0].keys())
    write_csv(args.output_dir / "diagnostic_rows.csv", rows, fields)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[(r["method"], r["channel"], r["severity"])].append(r)
    summaries: list[dict[str, Any]] = []
    for (method, channel, severity), items in sorted(grouped.items()):
        summaries.append({
            "method": method,
            "channel": channel,
            "severity": severity,
            "n": len(items),
            "base_ber_mean": mean(r["base_ber"] for r in items),
            "detail_ber_mean": mean(r["detail_ber"] for r in items),
            "raw_ber_mean": mean(r["raw_ber"] for r in items),
            "base_corrected_mean": mean(r["base_corrected"] for r in items),
            "detail_corrected_mean": mean(r["detail_corrected"] for r in items),
            "base_failed_codewords_mean": mean(r["base_failed_codewords"] for r in items),
            "detail_failed_codewords_mean": mean(r["detail_failed_codewords"] for r in items),
            "header_valid_rate": mean(float(v) for v in (r["header_valid"] for r in items) if v is not None),
            "payload_valid_rate": mean(float(v) for v in (r["payload_valid"] for r in items) if v is not None),
        })
    summary_fields = list(summaries[0].keys())
    write_csv(args.output_dir / "diagnostic_summary.csv", summaries, summary_fields)

    generated = {
        "layer_ber": plot_layer_ber(rows, args.output_dir),
        "corrected_symbols": plot_corrections(rows, args.output_dir),
        "failure_stages": plot_failures(rows, args.output_dir),
    }
    manifest = {
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "row_count": len(rows),
        "observed_run_ids": observed_run_ids,
        "generated": generated,
        "claim_boundary": "Exploratory diagnostics only; the locked primary EUR conclusion is unchanged.",
    }
    (args.output_dir / "diagnostic_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
