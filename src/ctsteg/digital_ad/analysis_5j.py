"""Deterministic pair-level analysis for FINAL-5J-v1 evaluation objects.

The image pair is the primary experimental unit. Attack realizations are
repeated observations within a pair and are aggregated before inference.
Scientific failures remain observations; operational failures are preserved
and are excluded only from the explicitly labelled sensitivity analysis.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy import stats

from ctsteg.runtime import ContentStore, read_json

from .runtime_5j import Runner5JError, validate_execution_plan


PROTOCOL_ID = "FINAL-5J-v1"
PRIMARY_COMPARISONS = (
    ("C3", "C0"),
    ("C3", "C3_NP"),
    ("C3", "B1"),
    ("C3", "B2"),
)
PRIMARY_METRICS = (
    "complete_recovery",
    "payload_correct_fraction",
    "raw_ber",
    "reconstruction_psnr",
    "reconstruction_ssim",
    "runtime_seconds",
)


class Analysis5JError(RuntimeError):
    """Raised when frozen result objects cannot support the declared analysis."""


@dataclass(frozen=True)
class AnalysisInputs:
    rows: tuple[dict[str, Any], ...]
    missing_object_ids: tuple[str, ...]
    invalid_object_ids: tuple[str, ...]


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _dig(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _condition_key(record: Mapping[str, Any]) -> str:
    channel = record["channel"]
    family = str(channel["family"])
    severity = channel.get("severity")
    if family == "clean":
        return "clean"
    return f"{family}:{severity}"


def normalize_evaluation(record: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten one typed evaluation object into a stable analysis row."""

    channel = record.get("channel")
    recovery = record.get("recovery")
    metrics = record.get("metrics")
    timing = record.get("timing")
    integrity = record.get("integrity")
    if not all(
        isinstance(value, Mapping)
        for value in (channel, recovery, metrics, timing, integrity)
    ):
        raise Analysis5JError("evaluation object lacks typed result sections")
    complete_metrics = metrics.get("complete_secret")
    base_metrics = metrics.get("base_only_secret")
    if not isinstance(complete_metrics, Mapping) or not isinstance(
        base_metrics, Mapping
    ):
        raise Analysis5JError("evaluation object lacks image metric sections")
    complete = bool(recovery.get("complete_recovery"))
    base_only_raw = recovery.get("valid_base_only_recovery")
    base_only = base_only_raw if isinstance(base_only_raw, bool) else None
    reconstruction = complete_metrics if complete else base_metrics
    if reconstruction.get("applicability") != "applicable":
        reconstruction = complete_metrics
    row = {
        "evaluation_id": str(record["object_id"]),
        "embedding_id": str(record["embedding_object_id"]),
        "component": str(record["component"]),
        "pair_id": str(record["pair_id"]),
        "method": str(record["method"]),
        "channel_instance_id": str(channel["instance_id"]),
        "channel_family": str(channel["family"]),
        "channel_severity": channel.get("severity"),
        "condition_key": _condition_key(record),
        "realization": int(channel["realization"]),
        "pair_seed": channel.get("pair_seed"),
        "status": str(record["status"]),
        "operational_failure": record["status"] == "operational_failure",
        "validity_state": str(record["validity_state"]),
        "failure_stage": str(record["failure_stage"]),
        "header_valid": bool(integrity["header_valid"]),
        "payload_crc_valid": bool(integrity["payload_crc_valid"]),
        "complete_recovery": float(complete),
        "valid_base_only_recovery": (
            None if base_only is None else float(base_only)
        ),
        "raw_ber": _number(recovery.get("raw_ber")),
        "payload_correct_fraction": _number(
            recovery.get("payload_correct_fraction")
        ),
        "raw_secret_correct_fraction": _number(
            recovery.get("raw_secret_correct_fraction")
        ),
        "base_correct_fraction": _number(
            recovery.get("base_correct_fraction")
        ),
        "detail_correct_fraction": _number(
            recovery.get("detail_correct_fraction")
        ),
        "base_ber": _number(recovery.get("base_ber")),
        "detail_ber": _number(recovery.get("detail_ber")),
        "unknown_bit_fraction": _number(
            recovery.get("unknown_bit_fraction")
        ),
        "reconstruction_psnr": _number(reconstruction.get("psnr")),
        "reconstruction_ssim": _number(reconstruction.get("ssim")),
        "reconstruction_ncc": _number(reconstruction.get("ncc")),
        "cover_stego_psnr": _number(
            _dig(metrics, "cover_stego", "psnr")
        ),
        "cover_stego_ssim": _number(
            _dig(metrics, "cover_stego", "ssim")
        ),
        "runtime_seconds": _number(timing.get("total_seconds")),
        "peak_memory_bytes": _number(timing.get("peak_rss_bytes")),
    }
    return row


def load_analysis_inputs(
    plan: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    require_complete: bool = True,
) -> AnalysisInputs:
    """Load exactly the plan-declared evaluation objects from local cache."""

    index = validate_execution_plan(plan)
    store = ContentStore(cache_dir)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    invalid: list[str] = []
    for object_id, task in index["evaluation_by_id"].items():
        verification = store.verify(object_id, deep=True)
        if not verification.path.exists():
            missing.append(object_id)
            continue
        if not verification.valid:
            invalid.append(object_id)
            continue
        try:
            record = read_json(verification.path / "evaluation.json")
        except (OSError, UnicodeError, ValueError):
            invalid.append(object_id)
            continue
        if not isinstance(record, Mapping):
            invalid.append(object_id)
            continue
        if record.get("object_id") != object_id:
            invalid.append(object_id)
            continue
        for field in ("component", "pair_id", "method"):
            if record.get(field) != task.get(field):
                invalid.append(object_id)
                break
        else:
            rows.append(normalize_evaluation(record))
    if require_complete and (missing or invalid):
        raise Analysis5JError(
            f"analysis requires all evaluation objects: "
            f"missing={len(missing)} invalid={len(invalid)}"
        )
    return AnalysisInputs(
        rows=tuple(rows),
        missing_object_ids=tuple(missing),
        invalid_object_ids=tuple(invalid),
    )


def _median(values: Sequence[float]) -> float | None:
    return float(np.median(values)) if values else None


def _mean(values: Sequence[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _std(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _quantile(values: Sequence[float], probability: float) -> float | None:
    return float(np.quantile(values, probability)) if values else None


def describe(values: Iterable[object]) -> dict[str, Any]:
    observed = [
        result for value in values if (result := _number(value)) is not None
    ]
    return {
        "n": len(observed),
        "mean": _mean(observed),
        "median": _median(observed),
        "standard_deviation": _std(observed),
        "q1": _quantile(observed, 0.25),
        "q3": _quantile(observed, 0.75),
        "iqr": (
            None
            if not observed
            else float(
                np.quantile(observed, 0.75) - np.quantile(observed, 0.25)
            )
        ),
        "minimum": min(observed) if observed else None,
        "maximum": max(observed) if observed else None,
    }


def aggregate_pair_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    component: str = "main",
    exclude_operational: bool = False,
) -> list[dict[str, Any]]:
    """Aggregate repeated channels within pair/method and condition."""

    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("component") != component:
            continue
        if exclude_operational and row.get("operational_failure") is True:
            continue
        grouped[
            (
                str(row["pair_id"]),
                str(row["method"]),
                str(row["condition_key"]),
            )
        ].append(row)
    output: list[dict[str, Any]] = []
    metrics = (
        "complete_recovery",
        "valid_base_only_recovery",
        "raw_ber",
        "payload_correct_fraction",
        "raw_secret_correct_fraction",
        "base_correct_fraction",
        "detail_correct_fraction",
        "base_ber",
        "detail_ber",
        "unknown_bit_fraction",
        "reconstruction_psnr",
        "reconstruction_ssim",
        "reconstruction_ncc",
        "cover_stego_psnr",
        "cover_stego_ssim",
        "runtime_seconds",
        "peak_memory_bytes",
    )
    for (pair_id, method, condition), group in sorted(grouped.items()):
        record: dict[str, Any] = {
            "pair_id": pair_id,
            "method": method,
            "condition_key": condition,
            "observation_count": len(group),
            "operational_failure_count": sum(
                row.get("operational_failure") is True for row in group
            ),
        }
        for metric in metrics:
            record[metric] = _mean(
                [
                    value
                    for row in group
                    if (value := _number(row.get(metric))) is not None
                ]
            )
        stages = Counter(str(row["failure_stage"]) for row in group)
        record["failure_stage_counts"] = dict(sorted(stages.items()))
        output.append(record)
    return output


def aggregate_pair_overall(
    pair_condition_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate condition-level values into one row per pair and method."""

    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in pair_condition_rows:
        grouped[(str(row["pair_id"]), str(row["method"]))].append(row)
    metrics = (
        "complete_recovery",
        "valid_base_only_recovery",
        "raw_ber",
        "payload_correct_fraction",
        "raw_secret_correct_fraction",
        "base_correct_fraction",
        "detail_correct_fraction",
        "base_ber",
        "detail_ber",
        "unknown_bit_fraction",
        "reconstruction_psnr",
        "reconstruction_ssim",
        "reconstruction_ncc",
        "cover_stego_psnr",
        "cover_stego_ssim",
        "runtime_seconds",
        "peak_memory_bytes",
    )
    output: list[dict[str, Any]] = []
    for (pair_id, method), group in sorted(grouped.items()):
        record: dict[str, Any] = {
            "pair_id": pair_id,
            "method": method,
            "condition_count": len(group),
            "observation_count": sum(int(row["observation_count"]) for row in group),
            "operational_failure_count": sum(
                int(row["operational_failure_count"]) for row in group
            ),
        }
        for metric in metrics:
            values = [
                value
                for row in group
                if (value := _number(row.get(metric))) is not None
            ]
            record[metric] = _mean(values)
        output.append(record)
    return output


def method_summaries(
    pair_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in pair_rows:
        grouped[str(row["method"])].append(row)
    output: list[dict[str, Any]] = []
    metrics = (
        "complete_recovery",
        "valid_base_only_recovery",
        "raw_ber",
        "payload_correct_fraction",
        "reconstruction_psnr",
        "reconstruction_ssim",
        "cover_stego_psnr",
        "runtime_seconds",
        "peak_memory_bytes",
    )
    for method, group in sorted(grouped.items()):
        record: dict[str, Any] = {
            "method": method,
            "pair_count": len(group),
            "operational_failure_count": sum(
                int(row["operational_failure_count"]) for row in group
            ),
        }
        for metric in metrics:
            record[metric] = describe(row.get(metric) for row in group)
        output.append(record)
    return output


def _bootstrap_seed(plan_id: str, label: str) -> int:
    payload = f"{PROTOCOL_ID}:{plan_id}:{label}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def cluster_bootstrap_difference(
    differences: Sequence[float],
    *,
    seed: int,
    repetitions: int = 10_000,
) -> dict[str, Any]:
    values = np.asarray(differences, dtype=np.float64)
    if values.size == 0:
        return {
            "repetitions": repetitions,
            "mean_difference": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    generator = np.random.default_rng(seed)
    indices = generator.integers(
        0,
        values.size,
        size=(repetitions, values.size),
    )
    samples = values[indices].mean(axis=1)
    return {
        "repetitions": repetitions,
        "mean_difference": float(values.mean()),
        "ci95_low": float(np.quantile(samples, 0.025)),
        "ci95_high": float(np.quantile(samples, 0.975)),
    }


def _paired_pvalue(differences: Sequence[float]) -> float | None:
    values = np.asarray(differences, dtype=np.float64)
    if values.size == 0:
        return None
    if np.allclose(values, 0.0):
        return 1.0
    try:
        result = stats.wilcoxon(
            values,
            zero_method="pratt",
            alternative="two-sided",
            method="auto",
        )
    except ValueError:
        return 1.0
    return float(result.pvalue)


def paired_comparison(
    pair_rows: Sequence[Mapping[str, Any]],
    *,
    method_a: str,
    method_b: str,
    metric: str,
    plan_id: str,
    bootstrap_repetitions: int = 10_000,
) -> dict[str, Any]:
    by_pair: dict[str, dict[str, float]] = defaultdict(dict)
    for row in pair_rows:
        method = str(row["method"])
        if method not in {method_a, method_b}:
            continue
        value = _number(row.get(metric))
        if value is not None:
            by_pair[str(row["pair_id"])][method] = value
    pair_ids = sorted(
        pair_id
        for pair_id, values in by_pair.items()
        if method_a in values and method_b in values
    )
    differences = [
        by_pair[pair_id][method_a] - by_pair[pair_id][method_b]
        for pair_id in pair_ids
    ]
    relative = [
        difference / abs(by_pair[pair_id][method_b])
        for pair_id, difference in zip(pair_ids, differences, strict=True)
        if by_pair[pair_id][method_b] != 0
    ]
    bootstrap = cluster_bootstrap_difference(
        differences,
        seed=_bootstrap_seed(
            plan_id,
            f"{method_a}:{method_b}:{metric}",
        ),
        repetitions=bootstrap_repetitions,
    )
    return {
        "method_a": method_a,
        "method_b": method_b,
        "metric": metric,
        "paired_n": len(pair_ids),
        "pair_ids": pair_ids,
        "absolute_difference": describe(differences),
        "relative_difference": describe(relative),
        "direction_count": {
            "positive": sum(value > 0 for value in differences),
            "zero": sum(value == 0 for value in differences),
            "negative": sum(value < 0 for value in differences),
        },
        "cluster_bootstrap": bootstrap,
        "paired_wilcoxon_p": _paired_pvalue(differences),
        "holm_adjusted_p": None,
    }


def holm_adjust(pvalues: Sequence[float | None]) -> list[float | None]:
    output: list[float | None] = [None] * len(pvalues)
    valid = [(index, value) for index, value in enumerate(pvalues) if value is not None]
    ordered = sorted(valid, key=lambda item: float(item[1]))
    previous = 0.0
    count = len(ordered)
    for rank, (index, value) in enumerate(ordered):
        adjusted = min(1.0, (count - rank) * float(value))
        adjusted = max(previous, adjusted)
        output[index] = adjusted
        previous = adjusted
    return output


def primary_comparisons(
    pair_rows: Sequence[Mapping[str, Any]],
    *,
    plan_id: str,
    bootstrap_repetitions: int = 10_000,
) -> list[dict[str, Any]]:
    output = [
        paired_comparison(
            pair_rows,
            method_a=method_a,
            method_b=method_b,
            metric=metric,
            plan_id=plan_id,
            bootstrap_repetitions=bootstrap_repetitions,
        )
        for method_a, method_b in PRIMARY_COMPARISONS
        for metric in PRIMARY_METRICS
    ]
    adjusted = holm_adjust(
        [record["paired_wilcoxon_p"] for record in output]
    )
    for record, value in zip(output, adjusted, strict=True):
        record["holm_adjusted_p"] = value
    return output


def failure_stage_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    component: str = "main",
) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    totals: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row.get("component") != component:
            continue
        key = (str(row["method"]), str(row["condition_key"]))
        stage = str(row["failure_stage"])
        counts[(key[0], key[1], stage)] += 1
        totals[key] += 1
    return [
        {
            "method": method,
            "condition_key": condition,
            "failure_stage": stage,
            "count": count,
            "fraction": count / totals[(method, condition)],
        }
        for (method, condition, stage), count in sorted(counts.items())
    ]


def build_analysis_payload(
    plan: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_repetitions: int = 10_000,
) -> dict[str, Any]:
    index = validate_execution_plan(plan)
    pair_condition = aggregate_pair_rows(rows)
    pair_overall = aggregate_pair_overall(pair_condition)
    sensitivity_condition = aggregate_pair_rows(
        rows,
        exclude_operational=True,
    )
    sensitivity_overall = aggregate_pair_overall(sensitivity_condition)
    return {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": index["run_id"],
        "plan_id": index["plan_id"],
        "analysis_unit": "image_pair",
        "repeat_handling": "aggregate within pair/method/condition before inference",
        "bootstrap_repetitions": bootstrap_repetitions,
        "raw_row_count": len(rows),
        "pair_condition_rows": pair_condition,
        "pair_overall_rows": pair_overall,
        "method_summaries": method_summaries(pair_overall),
        "primary_comparisons": primary_comparisons(
            pair_overall,
            plan_id=index["plan_id"],
            bootstrap_repetitions=bootstrap_repetitions,
        ),
        "failure_stage_summary": failure_stage_summary(rows),
        "operational_failure_sensitivity": {
            "pair_condition_rows": sensitivity_condition,
            "pair_overall_rows": sensitivity_overall,
            "method_summaries": method_summaries(sensitivity_overall),
            "primary_comparisons": primary_comparisons(
                sensitivity_overall,
                plan_id=index["plan_id"] + ":exclude-operational",
                bootstrap_repetitions=bootstrap_repetitions,
            ),
        },
    }
