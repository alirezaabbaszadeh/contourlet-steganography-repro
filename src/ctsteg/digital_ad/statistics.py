"""Prospective 2x2 factorial analysis for C0, C1, C2, and C3."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from ctsteg.statistics import (
    holm_adjust,
    paired_bootstrap_mean_ci,
    paired_sign_flip_test,
    rank_biserial_paired,
)

from .types import MethodId


_GROUP_FIELDS = (
    "split",
    "scope",
    "attack",
    "parameter",
    "attack_value",
    "metric",
    "direction",
)


def _oriented(values: np.ndarray, direction: str) -> np.ndarray:
    if direction == "higher":
        return values
    if direction == "lower":
        return -values
    raise ValueError(f"unknown metric direction: {direction!r}")


def analyze_factorial(
    results_path: str | Path,
    output_dir: str | Path,
    *,
    bootstrap_resamples: int = 10_000,
    permutation_resamples: int = 10_000,
    seed: int = 2026,
) -> dict[str, Any]:
    source = Path(results_path)
    groups: dict[
        tuple[str, ...],
        dict[str, dict[str, dict[str, list[float]]]],
    ] = {}
    with source.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"method", "pair_id", "seed", *_GROUP_FIELDS, "value"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"factorial input is missing fields: {sorted(missing)}")
        for row in reader:
            group = tuple(row[field] for field in _GROUP_FIELDS)
            groups.setdefault(group, {}).setdefault(
                row["pair_id"],
                {},
            ).setdefault(row["seed"], {}).setdefault(row["method"], []).append(
                float(row["value"])
            )
    comparisons: list[dict[str, Any]] = []
    p_values: list[float] = []
    wilcoxon_p_values: list[float] = []
    rng = np.random.default_rng(seed)
    names = [method.name for method in MethodId]
    for group, units in sorted(groups.items()):
        pair_contrasts: dict[str, list[float]] = {
            "A_main": [],
            "D_main": [],
            "A_x_D": [],
            "C3_minus_C0": [],
            "C1_minus_C0": [],
            "C2_minus_C0": [],
            "C3_minus_C1": [],
            "C3_minus_C2": [],
        }
        direction = group[-1]
        for seeds in units.values():
            aligned = [
                methods
                for methods in seeds.values()
                if all(name in methods for name in names)
            ]
            if not aligned:
                continue
            values = {
                name: float(
                    np.mean(
                        [
                            float(np.mean(methods[name]))
                            for methods in aligned
                        ]
                    )
                )
                for name in names
            }
            if not all(np.isfinite(value) for value in values.values()):
                continue
            vector = _oriented(
                np.asarray([values[name] for name in names]),
                direction,
            )
            c0, c1, c2, c3 = vector
            pair_contrasts["A_main"].append(((c1 - c0) + (c3 - c2)) / 2.0)
            pair_contrasts["D_main"].append(((c2 - c0) + (c3 - c1)) / 2.0)
            pair_contrasts["A_x_D"].append(c3 - c2 - c1 + c0)
            pair_contrasts["C3_minus_C0"].append(c3 - c0)
            pair_contrasts["C1_minus_C0"].append(c1 - c0)
            pair_contrasts["C2_minus_C0"].append(c2 - c0)
            pair_contrasts["C3_minus_C1"].append(c3 - c1)
            pair_contrasts["C3_minus_C2"].append(c3 - c2)
        for contrast_name, contrast_values in pair_contrasts.items():
            if not contrast_values:
                continue
            values = np.asarray(contrast_values, dtype=np.float64)
            low, high = paired_bootstrap_mean_ci(
                values,
                resamples=bootstrap_resamples,
                rng=rng,
            )
            p_value, mode = paired_sign_flip_test(
                values,
                resamples=permutation_resamples,
                rng=rng,
            )
            p_values.append(p_value)
            if np.all(values == 0):
                wilcoxon_statistic = 0.0
                p_wilcoxon = 1.0
            else:
                wilcoxon = stats.wilcoxon(
                    values,
                    zero_method="wilcox",
                    correction=False,
                    alternative="two-sided",
                    method="auto",
                )
                wilcoxon_statistic = float(wilcoxon.statistic)
                p_wilcoxon = float(wilcoxon.pvalue)
            wilcoxon_p_values.append(p_wilcoxon)
            comparisons.append(
                {
                    **dict(zip(_GROUP_FIELDS, group, strict=True)),
                    "contrast": contrast_name,
                    "n_pairs": int(values.size),
                    "mean_improvement": float(np.mean(values)),
                    "median_improvement": float(np.median(values)),
                    "ci95_low": low,
                    "ci95_high": high,
                    "rank_biserial": rank_biserial_paired(values),
                    "sign_flip_mode": mode,
                    "p_sign_flip": p_value,
                    "wilcoxon_statistic": wilcoxon_statistic,
                    "p_wilcoxon": p_wilcoxon,
                }
            )
    adjusted = holm_adjust(p_values)
    wilcoxon_adjusted = holm_adjust(wilcoxon_p_values)
    for comparison, corrected, wilcoxon_corrected in zip(
        comparisons,
        adjusted,
        wilcoxon_adjusted,
        strict=True,
    ):
        comparison["p_sign_flip_holm"] = corrected
        comparison["p_wilcoxon_holm"] = wilcoxon_corrected
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"output directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    fields = tuple(comparisons[0]) if comparisons else (
        *_GROUP_FIELDS,
        "contrast",
        "n_pairs",
    )
    with (destination / "factorial.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(comparisons)
    payload = {
        "schema": 1,
        "positive_means_better": True,
        "comparisons": comparisons,
        "bootstrap_resamples": bootstrap_resamples,
        "permutation_resamples": permutation_resamples,
        "seed": seed,
    }
    with (destination / "factorial.json").open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    markdown = [
        "# DIGITAL_A_D factorial analysis",
        "",
        "Positive improvement means the candidate direction is better. "
        "This report is empirical evidence, not a universal proof.",
        "",
        "| Scope | Attack | Metric | Contrast | n | Mean improvement | "
        "95% CI | Holm sign-flip p | Holm Wilcoxon p |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in comparisons:
        attack = item["attack"] or "clean"
        interval = f"[{item['ci95_low']:.6g}, {item['ci95_high']:.6g}]"
        format_values = {**item, "attack": attack, "interval": interval}
        markdown.append(
            "| {scope} | {attack} | {metric} | {contrast} | {n_pairs} | "
            "{mean_improvement:.6g} | {interval} | {p_sign_flip_holm:.6g} | "
            "{p_wilcoxon_holm:.6g} |".format(**format_values)
        )
    (destination / "factorial.md").write_text(
        "\n".join(markdown) + "\n",
        encoding="utf-8",
    )
    return payload
