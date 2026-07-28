"""Manifest-driven C0--C3 benchmark with locked inputs and raw results."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from ctsteg.manifest import read_manifest
from ctsteg.provenance import (
    environment_snapshot,
    git_state,
    sha256_file,
    sha256_json,
)

from .calibration import StabilityProfile, load_stability_profile
from .config import DigitalADConfig
from .experiment import RESULT_FIELDS, run_digital_experiment
from .preprocessing import load_uint8_grayscale
from .types import MethodId


def _write_csv(
    path: Path,
    rows: Iterable[dict[str, object]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def _summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[float]] = {}
    keys = (
        "method",
        "split",
        "scope",
        "attack",
        "parameter",
        "attack_value",
        "metric",
        "direction",
    )
    for row in rows:
        groups.setdefault(tuple(row[key] for key in keys), []).append(
            float(row["value"])
        )
    output: list[dict[str, object]] = []
    for group, values in sorted(groups.items(), key=lambda item: str(item[0])):
        array = np.asarray(values, dtype=np.float64)
        finite = array[np.isfinite(array)]
        record = dict(zip(keys, group, strict=True))
        record.update(
            {
                "count_total": int(array.size),
                "count_finite": int(finite.size),
                "mean": float(np.mean(finite)) if finite.size else "",
                "median": float(np.median(finite)) if finite.size else "",
                "std": (
                    float(np.std(finite, ddof=1))
                    if finite.size > 1
                    else 0.0 if finite.size else ""
                ),
                "minimum": float(np.min(finite)) if finite.size else "",
                "maximum": float(np.max(finite)) if finite.size else "",
            }
        )
        output.append(record)
    return output


def run_digital_benchmark(
    manifest_path: str | Path,
    config: DigitalADConfig,
    output_dir: str | Path,
    *,
    methods: Sequence[MethodId | str | int] = tuple(MethodId),
    stability_path: str | Path | None = None,
    attack_profile: str = "final",
    continue_on_error: bool = False,
) -> dict[str, Any]:
    cfg = config.validate()
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"output directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    manifest = Path(manifest_path).resolve()
    pairs = read_manifest(manifest)
    selected_methods = tuple(MethodId.parse(method) for method in methods)
    if len(set(selected_methods)) != len(selected_methods):
        raise ValueError("digital benchmark method list contains duplicates")
    stability: StabilityProfile | None = None
    if stability_path is not None:
        stability = load_stability_profile(stability_path, config=cfg)
    if (
        attack_profile == "final"
        and any(method.uses_adaptive_allocation for method in selected_methods)
        and stability is None
    ):
        raise ValueError(
            "final benchmark includes C1/C3 but no calibration stability "
            "profile was supplied"
        )
    rows: list[dict[str, object]] = []
    units: list[dict[str, Any]] = []
    failed = 0
    for pair in pairs:
        effective_seed = cfg.master_seed if pair.seed is None else pair.seed
        pair_config = DigitalADConfig(
            **{**cfg.to_dict(), "master_seed": effective_seed}
        ).validate()
        cover = load_uint8_grayscale(pair.cover, size=pair_config.cover_size)
        secret = load_uint8_grayscale(pair.secret, size=pair_config.secret_size)
        for method in selected_methods:
            unit_dir = destination / "artifacts" / pair.unit_id / method.name
            try:
                result = run_digital_experiment(
                    cover,
                    secret,
                    pair_id=pair.pair_id,
                    method=method,
                    config=pair_config,
                    output_dir=unit_dir,
                    stability_profile=stability,
                    attack_profile=attack_profile,
                )
                for row in result["rows"]:
                    row["split"] = pair.split
                    row["seed"] = effective_seed
                    rows.append(row)
                units.append(
                    {
                        "pair_id": pair.pair_id,
                        "split": pair.split,
                        "seed": effective_seed,
                        "method": method.name,
                        "status": "ok" if result["success"] else "clean_failure",
                        "failure_reason": result["failure_reason"],
                        "cover_file_sha256": sha256_file(pair.cover),
                        "secret_file_sha256": sha256_file(pair.secret),
                        "artifact_dir": str(unit_dir.relative_to(destination)),
                    }
                )
                if not result["success"]:
                    failed += 1
            except Exception as error:
                failed += 1
                units.append(
                    {
                        "pair_id": pair.pair_id,
                        "split": pair.split,
                        "seed": effective_seed,
                        "method": method.name,
                        "status": "error",
                        "failure_reason": f"{type(error).__name__}: {error}",
                        "cover_file_sha256": sha256_file(pair.cover),
                        "secret_file_sha256": sha256_file(pair.secret),
                    }
                )
                if not continue_on_error:
                    raise
    _write_csv(destination / "results_long.csv", rows, RESULT_FIELDS)
    summaries = _summaries(rows)
    summary_fields = tuple(summaries[0]) if summaries else (
        "method",
        "metric",
        "count_total",
    )
    _write_csv(destination / "summary.csv", summaries, summary_fields)
    run_material = {
        "manifest_sha256": sha256_file(manifest),
        "config": cfg.to_dict(),
        "methods": [method.name for method in selected_methods],
        "attack_profile": attack_profile,
        "stability_sha256": (
            None if stability_path is None else sha256_file(stability_path)
        ),
    }
    run_id = sha256_json(run_material)[:16]
    benchmark = {
        "schema": 1,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "units": units,
        "result_rows": len(rows),
        "failed_units": failed,
        "successful_units": len(units) - failed,
    }
    provenance = {
        "schema": 1,
        "run_id": run_id,
        "manifest": {
            "path": str(manifest),
            "sha256": sha256_file(manifest),
        },
        "config": cfg.to_dict(),
        "config_sha256": sha256_json(cfg.to_dict()),
        "methods": [method.name for method in selected_methods],
        "attack_profile": attack_profile,
        "stability_profile_sha256": (
            None if stability_path is None else sha256_file(stability_path)
        ),
        "git": git_state(),
        "environment": environment_snapshot(),
    }
    for name, payload in (
        ("benchmark.json", benchmark),
        ("provenance.json", provenance),
    ):
        with (destination / name).open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    return {
        **benchmark,
        "files": {
            "results": "results_long.csv",
            "summary": "summary.csv",
            "benchmark": "benchmark.json",
            "provenance": "provenance.json",
        },
    }
