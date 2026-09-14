#!/usr/bin/env python3
"""Generate FINAL-5J publication figures from frozen analysis.json."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


METHOD_ORDER = ("C0", "C1", "C2", "C3_NP", "C3", "B1", "B2")
STAGE_ORDER = (
    "S0_COMPLETE",
    "S1_BASE_ONLY",
    "S2_HEADER_VALID_PARTIAL",
    "S3_PAYLOAD_ECC_FAILURE",
    "S4_HEADER_FAILURE",
    "S5_EXTRACTION_TRANSFORM_FAILURE",
    "S6_OPERATIONAL_FAILURE",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def method_map(analysis: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(record["method"]): record
        for record in analysis["method_summaries"]
    }


def save_figure(figure: plt.Figure, output: Path, stem: str) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / f"{stem}.png", output / f"{stem}.pdf"]
    figure.savefig(paths[0], dpi=240, bbox_inches="tight")
    figure.savefig(paths[1], bbox_inches="tight")
    plt.close(figure)
    return paths


def method_metric_figure(
    analysis: Mapping[str, Any],
    *,
    metric: str,
    ylabel: str,
    title: str,
    internal_only: bool = False,
) -> plt.Figure:
    summaries = method_map(analysis)
    methods = [
        method
        for method in METHOD_ORDER
        if method in summaries
        and (not internal_only or not method.startswith("B"))
        and summaries[method][metric]["mean"] is not None
    ]
    means = np.array(
        [float(summaries[method][metric]["mean"]) for method in methods]
    )
    q1 = np.array(
        [float(summaries[method][metric]["q1"]) for method in methods]
    )
    q3 = np.array(
        [float(summaries[method][metric]["q3"]) for method in methods]
    )
    lower = np.maximum(0.0, means - q1)
    upper = np.maximum(0.0, q3 - means)
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    positions = np.arange(len(methods))
    axis.bar(positions, means)
    axis.errorbar(
        positions,
        means,
        yerr=np.vstack([lower, upper]),
        fmt="none",
        capsize=4,
    )
    axis.set_xticks(positions, methods)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.grid(axis="y", alpha=0.25)
    return figure


def paired_ci_figure(analysis: Mapping[str, Any]) -> plt.Figure:
    records = [
        record
        for record in analysis["primary_comparisons"]
        if record["metric"] == "complete_recovery"
    ]
    labels = [f"{record['method_a']} - {record['method_b']}" for record in records]
    means = np.array(
        [float(record["cluster_bootstrap"]["mean_difference"]) for record in records]
    )
    lows = np.array(
        [float(record["cluster_bootstrap"]["ci95_low"]) for record in records]
    )
    highs = np.array(
        [float(record["cluster_bootstrap"]["ci95_high"]) for record in records]
    )
    figure, axis = plt.subplots(figsize=(8.2, 4.8))
    positions = np.arange(len(records))
    axis.errorbar(
        positions,
        means,
        yerr=np.vstack([means - lows, highs - means]),
        fmt="o",
        capsize=5,
    )
    axis.axhline(0.0, linewidth=1.0)
    axis.set_xticks(positions, labels, rotation=20, ha="right")
    axis.set_ylabel("Pair-level complete-recovery difference")
    axis.set_title("Preregistered C3 paired effects with cluster bootstrap 95% CI")
    axis.grid(axis="y", alpha=0.25)
    return figure


def failure_stage_figure(analysis: Mapping[str, Any]) -> plt.Figure:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[str, int] = defaultdict(int)
    for record in analysis["failure_stage_summary"]:
        method = str(record["method"])
        stage = str(record["failure_stage"])
        count = int(record["count"])
        counts[method][stage] += count
        totals[method] += count
    methods = [method for method in METHOD_ORDER if totals[method]]
    figure, axis = plt.subplots(figsize=(9.0, 5.2))
    bottom = np.zeros(len(methods), dtype=float)
    for stage in STAGE_ORDER:
        fractions = np.array(
            [
                counts[method][stage] / totals[method]
                if totals[method]
                else 0.0
                for method in methods
            ]
        )
        if np.allclose(fractions, 0.0):
            continue
        axis.bar(methods, fractions, bottom=bottom, label=stage)
        bottom += fractions
    axis.set_ylim(0.0, 1.0)
    axis.set_ylabel("Fraction of evaluations")
    axis.set_title("Failure-stage distribution across the main study")
    axis.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), fontsize=8)
    axis.grid(axis="y", alpha=0.25)
    return figure


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
        generated: list[Path] = []
        generated.extend(
            save_figure(
                method_metric_figure(
                    analysis,
                    metric="complete_recovery",
                    ylabel="Pair-level complete recovery rate",
                    title="Complete recovery by method (mean with IQR)",
                ),
                output,
                "figure_complete_recovery",
            )
        )
        generated.extend(
            save_figure(
                method_metric_figure(
                    analysis,
                    metric="valid_base_only_recovery",
                    ylabel="Pair-level valid Base-only rate",
                    title="Valid Base-only recovery for layered methods",
                    internal_only=True,
                ),
                output,
                "figure_base_only_recovery",
            )
        )
        generated.extend(
            save_figure(
                method_metric_figure(
                    analysis,
                    metric="payload_correct_fraction",
                    ylabel="Recovered payload fraction",
                    title="Payload recovery by method (mean with IQR)",
                ),
                output,
                "figure_payload_recovery",
            )
        )
        generated.extend(
            save_figure(
                method_metric_figure(
                    analysis,
                    metric="runtime_seconds",
                    ylabel="Runtime per evaluation (s)",
                    title="Runtime by method (mean with IQR)",
                ),
                output,
                "figure_runtime",
            )
        )
        generated.extend(
            save_figure(
                paired_ci_figure(analysis),
                output,
                "figure_primary_complete_recovery_effects",
            )
        )
        generated.extend(
            save_figure(
                failure_stage_figure(analysis),
                output,
                "figure_failure_stages",
            )
        )
        manifest = {
            "schema_version": 1,
            "protocol_id": "FINAL-5J-v1",
            "run_id": analysis["run_id"],
            "plan_id": analysis["plan_id"],
            "figures": [
                {
                    "path": path.name,
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in generated
            ],
        }
        manifest_path = output / "figures_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FINAL-5J figure build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
