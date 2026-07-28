"""Paired statistical comparison for two benchmark result sets."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import warnings
from typing import Any, Iterable, Mapping

import numpy as np
from scipy import stats

from .provenance import (
    environment_snapshot,
    git_state,
    sha256_file,
    sha256_json,
)


REQUIRED_RESULT_FIELDS = {
    "method",
    "method_version",
    "pair_id",
    "split",
    "seed",
    "scope",
    "attack",
    "parameter",
    "attack_value",
    "metric",
    "direction",
    "value",
}
GROUP_FIELDS = (
    "split",
    "scope",
    "attack",
    "parameter",
    "attack_value",
    "metric",
    "direction",
)
OBSERVATION_FIELDS = ("pair_id", "seed")
COMPARISON_FIELDS = (
    *GROUP_FIELDS,
    "baseline_method",
    "baseline_version",
    "proposed_method",
    "proposed_version",
    "n_total",
    "n_finite",
    "n_nonfinite",
    "n_seed_units_total",
    "n_seed_units_finite",
    "n_seed_units_nonfinite",
    "baseline_mean",
    "baseline_median",
    "baseline_std",
    "proposed_mean",
    "proposed_median",
    "proposed_std",
    "raw_mean_proposed_minus_baseline",
    "mean_improvement",
    "median_improvement",
    "improvement_ci95_low",
    "improvement_ci95_high",
    "rank_biserial",
    "sign_flip_mode",
    "p_sign_flip",
    "p_sign_flip_holm",
    "wilcoxon_statistic",
    "p_wilcoxon",
    "p_wilcoxon_holm",
)


def _read_results(
    path: str | Path,
) -> tuple[
    tuple[str, str],
    dict[tuple[str, ...], dict[tuple[str, ...], float]],
]:
    result_path = Path(path)
    if not result_path.is_file():
        raise FileNotFoundError(f"result CSV not found: {result_path}")
    groups: dict[tuple[str, ...], dict[tuple[str, ...], float]] = {}
    identities: set[tuple[str, str]] = set()
    with result_path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or ())
        missing = REQUIRED_RESULT_FIELDS - fields
        if missing:
            raise ValueError(
                f"{result_path} is missing result fields: {sorted(missing)}"
            )
        for line_number, row in enumerate(reader, start=2):
            identity = (row["method"], row["method_version"])
            identities.add(identity)
            direction = row["direction"]
            if direction not in {"higher", "lower"}:
                raise ValueError(
                    f"{result_path}:{line_number}: direction must be "
                    "'higher' or 'lower'"
                )
            try:
                value = float(row["value"])
            except ValueError as error:
                raise ValueError(
                    f"{result_path}:{line_number}: value is not numeric"
                ) from error
            group = tuple(row[field] for field in GROUP_FIELDS)
            observation = tuple(row[field] for field in OBSERVATION_FIELDS)
            group_values = groups.setdefault(group, {})
            if observation in group_values:
                raise ValueError(
                    f"{result_path}:{line_number}: duplicate observation "
                    f"{observation} in group {group}"
                )
            group_values[observation] = value

    if len(identities) != 1:
        raise ValueError(
            f"{result_path} must contain exactly one method/version identity"
        )
    return next(iter(identities)), groups


def paired_bootstrap_mean_ci(
    differences: np.ndarray,
    *,
    resamples: int = 10_000,
    confidence: float = 0.95,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Percentile paired-bootstrap interval for the mean difference."""

    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or not values.size:
        raise ValueError("differences must be a non-empty one-dimensional array")
    if not np.isfinite(values).all():
        raise ValueError("differences must be finite")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    generator = rng or np.random.default_rng()
    bootstrap_means = np.empty(resamples, dtype=np.float64)
    chunk_size = min(1_000, resamples)
    offset = 0
    while offset < resamples:
        count = min(chunk_size, resamples - offset)
        indices = generator.integers(
            0,
            values.size,
            size=(count, values.size),
        )
        bootstrap_means[offset : offset + count] = np.mean(
            values[indices],
            axis=1,
        )
        offset += count
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(bootstrap_means, [tail, 1.0 - tail])
    return float(low), float(high)


def paired_sign_flip_test(
    differences: np.ndarray,
    *,
    resamples: int = 10_000,
    rng: np.random.Generator | None = None,
    exact_max_n: int = 16,
) -> tuple[float, str]:
    """Two-sided paired sign-flip test on the mean improvement.

    The null is enumerated exactly for at most ``exact_max_n`` paired units.
    Larger samples use a Monte Carlo estimate with the standard +1 correction.
    """

    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or not values.size:
        raise ValueError("differences must be a non-empty one-dimensional array")
    if not np.isfinite(values).all():
        raise ValueError("differences must be finite")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    if exact_max_n < 0:
        raise ValueError("exact_max_n must be non-negative")
    observed = abs(float(np.mean(values)))
    tolerance = np.finfo(np.float64).eps * max(1.0, observed) * 8

    if values.size <= exact_max_n:
        total = 1 << values.size
        extreme = 0
        bit_positions = np.arange(values.size, dtype=np.uint64)
        for start in range(0, total, 4_096):
            stop = min(start + 4_096, total)
            patterns = np.arange(start, stop, dtype=np.uint64)[:, None]
            bits = (patterns >> bit_positions) & np.uint64(1)
            signs = bits.astype(np.float64) * 2.0 - 1.0
            statistics = np.abs((signs @ values) / values.size)
            extreme += int(np.count_nonzero(statistics >= observed - tolerance))
        return float(extreme / total), "exact"

    generator = rng or np.random.default_rng()
    extreme = 0
    completed = 0
    while completed < resamples:
        count = min(1_000, resamples - completed)
        signs = generator.integers(
            0,
            2,
            size=(count, values.size),
            dtype=np.int8,
        )
        signs = signs.astype(np.float64) * 2.0 - 1.0
        statistics = np.abs((signs @ values) / values.size)
        extreme += int(np.count_nonzero(statistics >= observed - tolerance))
        completed += count
    return float((extreme + 1) / (resamples + 1)), "monte_carlo"


def rank_biserial_paired(differences: np.ndarray) -> float:
    """Matched-pairs rank-biserial effect size, positive when proposed wins."""

    values = np.asarray(differences, dtype=np.float64)
    nonzero = values[values != 0]
    if not nonzero.size:
        return 0.0
    ranks = stats.rankdata(np.abs(nonzero), method="average")
    positive = float(np.sum(ranks[nonzero > 0]))
    negative = float(np.sum(ranks[nonzero < 0]))
    return (positive - negative) / (positive + negative)


def holm_adjust(p_values: Iterable[float]) -> list[float]:
    """Holm step-down family-wise error correction."""

    values = np.asarray(list(p_values), dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("p-values must be a finite one-dimensional sequence")
    if ((values < 0) | (values > 1)).any():
        raise ValueError("p-values must be in [0, 1]")
    count = values.size
    if not count:
        return []
    order = np.argsort(values, kind="stable")
    adjusted = np.empty(count, dtype=np.float64)
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (count - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted.tolist()


def _descriptive(values: np.ndarray) -> tuple[float, float, float]:
    standard_deviation = (
        float(np.std(values, ddof=1)) if values.size > 1 else 0.0
    )
    return (
        float(np.mean(values)),
        float(np.median(values)),
        standard_deviation,
    )


def _wilcoxon(values: np.ndarray) -> tuple[float, float]:
    if np.all(values == 0):
        return 0.0, 1.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        result = stats.wilcoxon(
            values,
            zero_method="wilcox",
            correction=False,
            alternative="two-sided",
            method="auto",
        )
    return float(result.statistic), float(result.pvalue)


def _group_rng(seed: int, group: tuple[str, ...], stream: int) -> np.random.Generator:
    digest = hashlib.sha256(
        json.dumps(group, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).digest()
    group_seed = int.from_bytes(digest[:8], "little")
    sequence = np.random.SeedSequence([seed, group_seed, stream])
    return np.random.default_rng(sequence)


def _load_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return payload


def _input_fingerprints(
    benchmark: Mapping[str, Any] | None,
) -> dict[str, tuple[str, str]]:
    fingerprints: dict[str, tuple[str, str]] = {}
    if benchmark is None:
        return fingerprints
    for pair in benchmark.get("pairs", []):
        if pair.get("status") != "ok":
            continue
        inputs = pair.get("inputs", {})
        cover_hash = inputs.get("cover", {}).get("file_sha256")
        secret_hash = inputs.get("secret", {}).get("file_sha256")
        if not cover_hash or not secret_hash:
            continue
        unit = f"{pair.get('pair_id')}@{pair.get('seed')}"
        fingerprints[unit] = (cover_hash, secret_hash)
    return fingerprints


def _provenance_checks(
    baseline_path: Path,
    proposed_path: Path,
) -> dict[str, object]:
    baseline_provenance = _load_json_if_present(
        baseline_path.parent / "provenance.json"
    )
    proposed_provenance = _load_json_if_present(
        proposed_path.parent / "provenance.json"
    )
    baseline_benchmark = _load_json_if_present(
        baseline_path.parent / "benchmark.json"
    )
    proposed_benchmark = _load_json_if_present(
        proposed_path.parent / "benchmark.json"
    )
    checks: dict[str, object] = {
        "baseline_provenance_available": baseline_provenance is not None,
        "proposed_provenance_available": proposed_provenance is not None,
        "baseline_benchmark_available": baseline_benchmark is not None,
        "proposed_benchmark_available": proposed_benchmark is not None,
    }
    mismatches: list[str] = []
    if baseline_provenance is not None and proposed_provenance is not None:
        pairs = {
            "manifest_sha256": (
                baseline_provenance.get("manifest", {}).get("sha256"),
                proposed_provenance.get("manifest", {}).get("sha256"),
            ),
            "input_files_sha256": (
                baseline_provenance.get("manifest", {}).get(
                    "input_files_sha256"
                ),
                proposed_provenance.get("manifest", {}).get(
                    "input_files_sha256"
                ),
            ),
            "config_sha256": (
                baseline_provenance.get("config_sha256"),
                proposed_provenance.get("config_sha256"),
            ),
            "include_attacks": (
                baseline_provenance.get("options", {}).get("include_attacks"),
                proposed_provenance.get("options", {}).get("include_attacks"),
            ),
        }
        for label, (baseline_value, proposed_value) in pairs.items():
            equal = baseline_value == proposed_value
            checks[f"{label}_equal"] = equal
            if not equal:
                mismatches.append(label)

        baseline_environment = baseline_provenance.get("environment")
        proposed_environment = proposed_provenance.get("environment")
        checks["environment_equal"] = baseline_environment == proposed_environment
        evaluation_code_equal = (
            baseline_provenance.get("evaluation_code")
            == proposed_provenance.get("evaluation_code")
        )
        checks["evaluation_code_equal"] = evaluation_code_equal
        if not evaluation_code_equal:
            mismatches.append("evaluation_code")

    baseline_inputs = _input_fingerprints(baseline_benchmark)
    proposed_inputs = _input_fingerprints(proposed_benchmark)
    if baseline_inputs and proposed_inputs:
        shared_units = sorted(set(baseline_inputs) & set(proposed_inputs))
        input_mismatches = [
            unit
            for unit in shared_units
            if baseline_inputs[unit] != proposed_inputs[unit]
        ]
        checks["shared_input_unit_count"] = len(shared_units)
        checks["input_hashes_equal"] = not input_mismatches
        checks["input_hash_mismatch_units"] = input_mismatches
        if input_mismatches:
            mismatches.append("input_hashes")
    checks["mismatches"] = mismatches
    return checks


def _write_comparison_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _format_number(value: object) -> str:
    if not isinstance(value, (float, int)):
        return str(value)
    number = float(value)
    if number == 0:
        return "0"
    if abs(number) < 0.001 or abs(number) >= 10_000:
        return f"{number:.3e}"
    return f"{number:.5f}"


def _write_markdown(
    path: Path,
    *,
    baseline_identity: tuple[str, str],
    proposed_identity: tuple[str, str],
    rows: list[dict[str, object]],
    alignment: Mapping[str, object],
    provenance: Mapping[str, object],
    bootstrap_resamples: int,
    permutation_resamples: int,
    seed: int,
    analysis_id: str,
) -> None:
    lines = [
        "# Paired benchmark comparison",
        "",
        f"- Baseline: `{baseline_identity[0]}` v{baseline_identity[1]}",
        f"- Candidate: `{proposed_identity[0]}` v{proposed_identity[1]}",
        f"- Analysis ID: `{analysis_id}`",
        f"- Bootstrap resamples: {bootstrap_resamples}",
        f"- Monte Carlo sign flips: {permutation_resamples}",
        f"- Analysis seed: {seed}",
        (
            "- Alignment: "
            f"{alignment['common_group_count']} common metric groups; "
            f"{alignment['unmatched_observation_count']} unmatched observations"
        ),
        (
            "- Provenance mismatches: "
            f"{', '.join(provenance['mismatches']) or 'none detected'}"
        ),
        "",
        (
            "Positive improvement means the candidate is better after respecting "
            "the declared metric direction. Holm-adjusted p-values control the "
            "family represented by all rows in this file."
        ),
        "",
        (
            "| Split | Scope / attack | Metric | n | Baseline mean | "
            "Candidate mean | Mean improvement [95% CI] | Holm p | "
            "Rank-biserial |"
        ),
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        label = str(row["scope"])
        if row["attack"]:
            label += f" / {row['attack']}"
        interval = (
            f"{_format_number(row['mean_improvement'])} "
            f"[{_format_number(row['improvement_ci95_low'])}, "
            f"{_format_number(row['improvement_ci95_high'])}]"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["split"]),
                    label,
                    str(row["metric"]),
                    str(row["n_finite"]),
                    _format_number(row["baseline_mean"]),
                    _format_number(row["proposed_mean"]),
                    interval,
                    _format_number(row["p_sign_flip_holm"]),
                    _format_number(row["rank_biserial"]),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            (
                "These tests quantify paired empirical differences; they do not "
                "establish technical novelty or cryptographic security. Timing "
                "rows require identical hardware and process controls. Any "
                "non-finite pair is excluded and counted explicitly."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def compare_benchmarks(
    baseline_results: str | Path,
    proposed_results: str | Path,
    output_dir: str | Path,
    *,
    bootstrap_resamples: int = 10_000,
    permutation_resamples: int = 10_000,
    seed: int = 2026,
    allow_incomplete_pairs: bool = False,
    allow_provenance_mismatch: bool = False,
) -> dict[str, object]:
    """Compare two long-form benchmark CSV files on paired units."""

    if bootstrap_resamples < 1 or permutation_resamples < 1:
        raise ValueError("resample counts must be positive")
    if seed < 0:
        raise ValueError("seed must be non-negative")
    started_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    baseline_path = Path(baseline_results).resolve()
    proposed_path = Path(proposed_results).resolve()
    baseline_identity, baseline_groups = _read_results(baseline_path)
    proposed_identity, proposed_groups = _read_results(proposed_path)
    destination = Path(output_dir).resolve()
    if destination.exists():
        if not destination.is_dir():
            raise NotADirectoryError(
                f"comparison output path is not a directory: {destination}"
            )
        if any(destination.iterdir()):
            raise FileExistsError(
                f"comparison output directory is not empty: {destination}"
            )

    provenance = _provenance_checks(baseline_path, proposed_path)
    if provenance["mismatches"] and not allow_provenance_mismatch:
        raise ValueError(
            "benchmark provenance mismatch: "
            + ", ".join(provenance["mismatches"])
        )

    common_groups = sorted(set(baseline_groups) & set(proposed_groups))
    if not common_groups:
        raise ValueError("the result files have no common metric groups")

    unmatched_observations: list[dict[str, object]] = []
    comparison_rows: list[dict[str, object]] = []
    for group in common_groups:
        baseline_units = baseline_groups[group]
        proposed_units = proposed_groups[group]
        missing_in_proposed = sorted(set(baseline_units) - set(proposed_units))
        missing_in_baseline = sorted(set(proposed_units) - set(baseline_units))
        if missing_in_proposed or missing_in_baseline:
            unmatched_observations.append(
                {
                    "group": dict(zip(GROUP_FIELDS, group, strict=True)),
                    "missing_in_proposed": missing_in_proposed,
                    "missing_in_baseline": missing_in_baseline,
                }
            )
            if not allow_incomplete_pairs:
                continue
        shared = sorted(set(baseline_units) & set(proposed_units))
        if not shared:
            continue
        baseline_seed_values = np.asarray(
            [baseline_units[unit] for unit in shared],
            dtype=np.float64,
        )
        proposed_seed_values = np.asarray(
            [proposed_units[unit] for unit in shared],
            dtype=np.float64,
        )
        finite_seed_mask = np.isfinite(baseline_seed_values) & np.isfinite(
            proposed_seed_values
        )
        pair_indices: dict[str, list[int]] = {}
        for index, observation in enumerate(shared):
            pair_indices.setdefault(observation[0], []).append(index)
        baseline_pair_means: list[float] = []
        proposed_pair_means: list[float] = []
        for pair_id in sorted(pair_indices):
            indices = np.asarray(pair_indices[pair_id], dtype=np.int64)
            if not finite_seed_mask[indices].all():
                continue
            baseline_pair_means.append(
                float(np.mean(baseline_seed_values[indices]))
            )
            proposed_pair_means.append(
                float(np.mean(proposed_seed_values[indices]))
            )
        baseline_finite = np.asarray(
            baseline_pair_means,
            dtype=np.float64,
        )
        proposed_finite = np.asarray(
            proposed_pair_means,
            dtype=np.float64,
        )
        if not baseline_pair_means:
            continue
        direction = group[GROUP_FIELDS.index("direction")]
        raw_differences = proposed_finite - baseline_finite
        improvements = (
            raw_differences if direction == "higher" else -raw_differences
        )
        baseline_mean, baseline_median, baseline_std = _descriptive(
            baseline_finite
        )
        proposed_mean, proposed_median, proposed_std = _descriptive(
            proposed_finite
        )
        ci_low, ci_high = paired_bootstrap_mean_ci(
            improvements,
            resamples=bootstrap_resamples,
            rng=_group_rng(seed, group, 1),
        )
        p_sign_flip, sign_flip_mode = paired_sign_flip_test(
            improvements,
            resamples=permutation_resamples,
            rng=_group_rng(seed, group, 2),
        )
        wilcoxon_statistic, p_wilcoxon = _wilcoxon(improvements)
        row: dict[str, object] = dict(
            zip(GROUP_FIELDS, group, strict=True)
        )
        row.update(
            {
                "baseline_method": baseline_identity[0],
                "baseline_version": baseline_identity[1],
                "proposed_method": proposed_identity[0],
                "proposed_version": proposed_identity[1],
                "n_total": len(pair_indices),
                "n_finite": len(baseline_pair_means),
                "n_nonfinite": len(pair_indices) - len(baseline_pair_means),
                "n_seed_units_total": len(shared),
                "n_seed_units_finite": int(finite_seed_mask.sum()),
                "n_seed_units_nonfinite": int((~finite_seed_mask).sum()),
                "baseline_mean": baseline_mean,
                "baseline_median": baseline_median,
                "baseline_std": baseline_std,
                "proposed_mean": proposed_mean,
                "proposed_median": proposed_median,
                "proposed_std": proposed_std,
                "raw_mean_proposed_minus_baseline": float(
                    np.mean(raw_differences)
                ),
                "mean_improvement": float(np.mean(improvements)),
                "median_improvement": float(np.median(improvements)),
                "improvement_ci95_low": ci_low,
                "improvement_ci95_high": ci_high,
                "rank_biserial": rank_biserial_paired(improvements),
                "sign_flip_mode": sign_flip_mode,
                "p_sign_flip": p_sign_flip,
                "p_sign_flip_holm": 0.0,
                "wilcoxon_statistic": wilcoxon_statistic,
                "p_wilcoxon": p_wilcoxon,
                "p_wilcoxon_holm": 0.0,
            }
        )
        comparison_rows.append(row)

    if unmatched_observations and not allow_incomplete_pairs:
        raise ValueError(
            "paired observations do not align in "
            f"{len(unmatched_observations)} common metric groups"
        )
    if not comparison_rows:
        raise ValueError("no finite paired observations are available")

    sign_flip_adjusted = holm_adjust(
        float(row["p_sign_flip"]) for row in comparison_rows
    )
    wilcoxon_adjusted = holm_adjust(
        float(row["p_wilcoxon"]) for row in comparison_rows
    )
    for row, sign_flip, wilcoxon in zip(
        comparison_rows,
        sign_flip_adjusted,
        wilcoxon_adjusted,
        strict=True,
    ):
        row["p_sign_flip_holm"] = sign_flip
        row["p_wilcoxon_holm"] = wilcoxon

    exclusive_baseline = sorted(set(baseline_groups) - set(proposed_groups))
    exclusive_proposed = sorted(set(proposed_groups) - set(baseline_groups))
    alignment: dict[str, object] = {
        "common_group_count": len(common_groups),
        "baseline_only_group_count": len(exclusive_baseline),
        "proposed_only_group_count": len(exclusive_proposed),
        "unmatched_group_count": len(unmatched_observations),
        "unmatched_observation_count": sum(
            len(item["missing_in_proposed"]) + len(item["missing_in_baseline"])
            for item in unmatched_observations
        ),
        "unmatched_observations": unmatched_observations,
    }
    analysis_code_hash = sha256_file(Path(__file__))
    analysis_id = sha256_json(
        {
            "schema": 1,
            "baseline_results_sha256": sha256_file(baseline_path),
            "proposed_results_sha256": sha256_file(proposed_path),
            "statistics_sha256": analysis_code_hash,
            "bootstrap_resamples": bootstrap_resamples,
            "permutation_resamples": permutation_resamples,
            "seed": seed,
            "allow_incomplete_pairs": allow_incomplete_pairs,
            "allow_provenance_mismatch": allow_provenance_mismatch,
        }
    )[:16]
    result: dict[str, object] = {
        "schema_version": 1,
        "analysis_id": analysis_id,
        "baseline": {
            "method": baseline_identity[0],
            "version": baseline_identity[1],
            "results_file": baseline_path.name,
        },
        "proposed": {
            "method": proposed_identity[0],
            "version": proposed_identity[1],
            "results_file": proposed_path.name,
        },
        "analysis": {
            "bootstrap_resamples": bootstrap_resamples,
            "permutation_resamples": permutation_resamples,
            "seed": seed,
            "improvement_convention": (
                "positive means proposed is better after metric-direction alignment"
            ),
            "multiplicity": "Holm correction across all comparison rows",
        },
        "analysis_provenance": {
            "started_utc": started_utc,
            "completed_utc": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "statistics_sha256": analysis_code_hash,
            "baseline_results_sha256": sha256_file(baseline_path),
            "proposed_results_sha256": sha256_file(proposed_path),
            "source": git_state(Path(__file__).resolve().parent),
            "environment": environment_snapshot(),
        },
        "provenance_checks": provenance,
        "alignment": alignment,
        "comparisons": comparison_rows,
    }

    destination.mkdir(parents=True, exist_ok=True)
    _write_comparison_csv(destination / "comparison.csv", comparison_rows)
    with (destination / "comparison.json").open("w", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    _write_markdown(
        destination / "comparison.md",
        baseline_identity=baseline_identity,
        proposed_identity=proposed_identity,
        rows=comparison_rows,
        alignment=alignment,
        provenance=provenance,
        bootstrap_resamples=bootstrap_resamples,
        permutation_resamples=permutation_resamples,
        seed=seed,
        analysis_id=analysis_id,
    )
    return result
