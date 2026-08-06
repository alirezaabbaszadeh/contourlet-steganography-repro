#!/usr/bin/env python3
"""Generate FINAL-5J publication tables from frozen analysis.json."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


METHOD_ORDER = ("C0", "C1", "C2", "C3_NP", "C3", "B1", "B2")
METRIC_LABELS = {
    "complete_recovery": "Complete recovery rate",
    "valid_base_only_recovery": "Valid Base-only rate",
    "raw_ber": "Raw BER",
    "payload_correct_fraction": "Payload correct fraction",
    "reconstruction_psnr": "Reconstruction PSNR (dB)",
    "reconstruction_ssim": "Reconstruction SSIM",
    "cover_stego_psnr": "Cover-stego PSNR (dB)",
    "runtime_seconds": "Runtime (s)",
    "peak_memory_bytes": "Peak memory (bytes)",
}


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def number(value: object, digits: int = 4) -> str:
    if not isinstance(value, (int, float)):
        return "N/A"
    if isinstance(value, bool):
        return "N/A"
    if abs(float(value)) >= 100_000:
        return f"{float(value):.3e}"
    return f"{float(value):.{digits}f}"


def escape_latex(value: str) -> str:
    replacements = {
        "_": r"\_",
        "%": r"\%",
        "&": r"\&",
        "#": r"\#",
    }
    return "".join(replacements.get(character, character) for character in value)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def latex_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    caption: str,
    label: str,
) -> str:
    columns = "l" + "r" * (len(headers) - 1)
    body = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{{escape_latex(caption)}}}",
        rf"\label{{{escape_latex(label)}}}",
        rf"\begin{{tabular}}{{{columns}}}",
        r"\toprule",
        " & ".join(escape_latex(item) for item in headers) + r" \",
        r"\midrule",
    ]
    body.extend(
        " & ".join(escape_latex(item) for item in row) + r" \"
        for row in rows
    )
    body.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return "\n".join(body) + "\n"


def method_summary_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    summaries = {
        record["method"]: record for record in analysis["method_summaries"]
    }
    rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        record = summaries.get(method)
        if not isinstance(record, Mapping):
            continue
        rows.append(
            {
                "Method": method,
                "Pairs": record["pair_count"],
                "Complete recovery mean": number(
                    record["complete_recovery"]["mean"]
                ),
                "Base-only mean": number(
                    record["valid_base_only_recovery"]["mean"]
                ),
                "Payload correct mean": number(
                    record["payload_correct_fraction"]["mean"]
                ),
                "Raw BER mean": number(record["raw_ber"]["mean"]),
                "Secret PSNR mean": number(
                    record["reconstruction_psnr"]["mean"]
                ),
                "Secret SSIM mean": number(
                    record["reconstruction_ssim"]["mean"]
                ),
                "Cover PSNR mean": number(
                    record["cover_stego_psnr"]["mean"]
                ),
                "Runtime mean (s)": number(
                    record["runtime_seconds"]["mean"]
                ),
                "Operational failures": record["operational_failure_count"],
            }
        )
    return rows


def comparison_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in analysis["primary_comparisons"]:
        absolute = record["absolute_difference"]
        bootstrap = record["cluster_bootstrap"]
        direction = record["direction_count"]
        rows.append(
            {
                "Comparison": f"{record['method_a']} - {record['method_b']}",
                "Metric": METRIC_LABELS.get(record["metric"], record["metric"]),
                "Paired n": record["paired_n"],
                "Mean difference": number(absolute["mean"]),
                "Median difference": number(absolute["median"]),
                "95% CI low": number(bootstrap["ci95_low"]),
                "95% CI high": number(bootstrap["ci95_high"]),
                "Positive/zero/negative": (
                    f"{direction['positive']}/{direction['zero']}/"
                    f"{direction['negative']}"
                ),
                "Wilcoxon p": number(record["paired_wilcoxon_p"], 6),
                "Holm p": number(record["holm_adjusted_p"], 6),
            }
        )
    return rows


def write_table_set(
    output: Path,
    stem: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    caption: str,
    label: str,
) -> None:
    write_csv(output / f"{stem}.csv", rows)
    headers = list(rows[0]) if rows else []
    values = [[str(row[header]) for header in headers] for row in rows]
    atomic_write(
        output / f"{stem}.md",
        markdown_table(headers, values),
    )
    atomic_write(
        output / f"{stem}.tex",
        latex_table(
            headers,
            values,
            caption=caption,
            label=label,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
        if analysis.get("protocol_id") != "FINAL-5J-v1":
            raise ValueError("analysis protocol mismatch")
        output = args.output_dir.resolve()
        methods = method_summary_rows(analysis)
        comparisons = comparison_rows(analysis)
        if not methods or not comparisons:
            raise ValueError("analysis does not contain publication table rows")
        write_table_set(
            output,
            "table_method_summary",
            methods,
            caption="Pair-level FINAL-5J method summary.",
            label="tab:5j-method-summary",
        )
        write_table_set(
            output,
            "table_primary_comparisons",
            comparisons,
            caption="Preregistered paired FINAL-5J comparisons.",
            label="tab:5j-primary-comparisons",
        )
        manifest = {
            "protocol_id": "FINAL-5J-v1",
            "run_id": analysis["run_id"],
            "plan_id": analysis["plan_id"],
            "tables": [
                "table_method_summary.csv",
                "table_method_summary.md",
                "table_method_summary.tex",
                "table_primary_comparisons.csv",
                "table_primary_comparisons.md",
                "table_primary_comparisons.tex",
            ],
        }
        atomic_write(
            output / "tables_manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FINAL-5J table build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
