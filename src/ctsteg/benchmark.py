"""Batch benchmarking with paired inputs and machine-readable provenance."""

from __future__ import annotations

import csv
from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping

import numpy as np

from . import attacks as attacks_module
from .config import ExperimentConfig
from .experiment import attack_suite
from .image_io import load_grayscale, save_grayscale
from .manifest import ImagePair, read_manifest
from .methods import SteganographyMethod, build_method
from .metrics import metric_bundle
from .provenance import (
    environment_snapshot,
    git_state,
    run_identifier,
    sha256_array,
    sha256_file,
    sha256_json,
)


RESULT_FIELDS = (
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
)
GROUP_FIELDS = (
    "method",
    "method_version",
    "split",
    "scope",
    "attack",
    "parameter",
    "attack_value",
    "metric",
    "direction",
)
_SAFE_ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def metric_direction(metric: str) -> str:
    """Return the declared optimization direction for a benchmark metric."""

    if metric in {
        "mse",
        "ber",
        "embed_time_s",
        "extract_time_s",
        "total_time_s",
    }:
        return "lower"
    if metric in {
        "psnr_db",
        "ssim_global",
        "ssim_windowed",
        "ncc",
        "ncc_paper_equation",
    }:
        return "higher"
    raise ValueError(
        f"no optimization direction declared for metric {metric!r}; "
        "register it explicitly before comparison"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_number(value: float) -> float | str:
    if math.isfinite(value):
        return value
    if math.isnan(value):
        return "nan"
    return "inf" if value > 0 else "-inf"


def _validated_image(
    image: Any,
    *,
    name: str,
    shape: tuple[int, int],
) -> np.ndarray:
    values = np.asarray(image, dtype=np.float64)
    if values.ndim != 2 or values.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} contains NaN or infinity")
    return values


def _json_safe_tree(value: Any) -> Any:
    if isinstance(value, float):
        return _safe_number(value)
    if isinstance(value, np.floating):
        return _safe_number(float(value))
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe_tree(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_tree(item) for item in value]
    return value


def _rows_for_metrics(
    *,
    method: SteganographyMethod,
    pair: ImagePair,
    seed: int,
    scope: str,
    metrics: Mapping[str, float],
    attack: str = "",
    parameter: str = "",
    attack_value: float | str = "",
) -> list[dict[str, object]]:
    return [
        {
            "method": method.name,
            "method_version": method.version,
            "pair_id": pair.pair_id,
            "split": pair.split,
            "seed": seed,
            "scope": scope,
            "attack": attack,
            "parameter": parameter,
            "attack_value": attack_value,
            "metric": name,
            "direction": metric_direction(name),
            "value": value,
        }
        for name, value in metrics.items()
    ]


def _write_csv(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    fields: Iterable[str],
) -> None:
    fieldnames = list(fields)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _aggregate(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[float]] = {}
    for row in rows:
        key = tuple(row[field] for field in GROUP_FIELDS)
        grouped.setdefault(key, []).append(float(row["value"]))

    summaries: list[dict[str, object]] = []
    for key in sorted(grouped, key=lambda item: tuple(str(value) for value in item)):
        values = np.asarray(grouped[key], dtype=np.float64)
        finite = values[np.isfinite(values)]
        summary: dict[str, object] = dict(zip(GROUP_FIELDS, key, strict=True))
        summary["count_total"] = int(values.size)
        summary["count_finite"] = int(finite.size)
        summary["count_nonfinite"] = int(values.size - finite.size)
        if finite.size:
            summary.update(
                {
                    "mean": float(np.mean(finite)),
                    "median": float(np.median(finite)),
                    "std": float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0,
                    "minimum": float(np.min(finite)),
                    "maximum": float(np.max(finite)),
                }
            )
        else:
            summary.update(
                {
                    "mean": "",
                    "median": "",
                    "std": "",
                    "minimum": "",
                    "maximum": "",
                }
            )
        summaries.append(summary)
    return summaries


def _save_method_images(
    directory: Path,
    images: Mapping[str, Any],
) -> None:
    for name, image in images.items():
        if not _SAFE_ARTIFACT.fullmatch(name):
            raise ValueError(f"unsafe diagnostic image name: {name!r}")
        save_grayscale(directory / f"{name}.png", image)


def _run_pair(
    *,
    pair: ImagePair,
    base_config: ExperimentConfig,
    method: SteganographyMethod,
    include_attacks: bool,
    save_artifacts: bool,
    destination: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    effective_seed = base_config.random_seed if pair.seed is None else pair.seed
    config = replace(base_config, random_seed=effective_seed).validate()
    cover = load_grayscale(pair.cover, size=config.image_size)
    secret = load_grayscale(pair.secret, size=config.image_size)
    expected_shape = (config.image_size, config.image_size)

    embed_started = time.perf_counter()
    embedded = method.embed(cover.copy(), secret.copy(), config)
    embed_seconds = time.perf_counter() - embed_started
    returned_cover = _validated_image(
        embedded.cover,
        name="method-returned cover",
        shape=expected_shape,
    )
    returned_secret = _validated_image(
        embedded.secret,
        name="method-returned secret",
        shape=expected_shape,
    )
    if not np.array_equal(returned_cover, cover):
        raise ValueError("method must not alter or replace the cover reference")
    if not np.array_equal(returned_secret, secret):
        raise ValueError("method must not alter or replace the secret reference")
    stego = _validated_image(
        embedded.stego,
        name="stego",
        shape=expected_shape,
    )

    extract_started = time.perf_counter()
    extracted = method.extract(
        stego.copy(),
        cover.copy(),
        config,
        context=embedded.extraction_context,
    )
    extract_seconds = time.perf_counter() - extract_started
    recovered_secret = _validated_image(
        extracted.recovered_secret,
        name="recovered secret",
        shape=expected_shape,
    )

    result_rows = _rows_for_metrics(
        method=method,
        pair=pair,
        seed=effective_seed,
        scope="imperceptibility",
        metrics=metric_bundle(cover, stego),
    )
    result_rows.extend(
        _rows_for_metrics(
            method=method,
            pair=pair,
            seed=effective_seed,
            scope="recovery",
            metrics=metric_bundle(secret, recovered_secret),
        )
    )
    result_rows.extend(
        _rows_for_metrics(
            method=method,
            pair=pair,
            seed=effective_seed,
            scope="efficiency",
            metrics={
                "embed_time_s": embed_seconds,
                "extract_time_s": extract_seconds,
                "total_time_s": embed_seconds + extract_seconds,
            },
        )
    )

    artifact_directory: Path | None = None
    if save_artifacts:
        artifact_directory = (
            destination
            / "artifacts"
            / pair.pair_id
            / f"seed-{effective_seed}"
        )
        artifact_directory.mkdir(parents=True, exist_ok=False)
        save_grayscale(artifact_directory / "cover.png", cover)
        save_grayscale(artifact_directory / "secret.png", secret)
        save_grayscale(artifact_directory / "stego.png", stego)
        save_grayscale(
            artifact_directory / "recovered_secret.png",
            recovered_secret,
        )
        _save_method_images(
            artifact_directory / "diagnostics" / "embed",
            embedded.diagnostic_images,
        )
        _save_method_images(
            artifact_directory / "diagnostics" / "extract",
            extracted.diagnostic_images,
        )

    attacks: list[dict[str, object]] = []
    if include_attacks:
        for name, parameter, value, attack in attack_suite(config):
            attacked_stego = attack(stego)
            attack_started = time.perf_counter()
            attacked_extraction = method.extract(
                attacked_stego.copy(),
                cover.copy(),
                config,
                context=embedded.extraction_context,
            )
            attack_seconds = time.perf_counter() - attack_started
            attacked_recovered = _validated_image(
                attacked_extraction.recovered_secret,
                name=f"recovered secret after {name}",
                shape=expected_shape,
            )
            metrics = metric_bundle(
                secret,
                attacked_recovered,
            )
            result_rows.extend(
                _rows_for_metrics(
                    method=method,
                    pair=pair,
                    seed=effective_seed,
                    scope="attack_recovery",
                    metrics=metrics,
                    attack=name,
                    parameter=parameter,
                    attack_value=value,
                )
            )
            attack_record = {
                "attack": name,
                "parameter": parameter,
                "value": value,
                "extract_time_s": attack_seconds,
                "attacked_stego_sha256": sha256_array(attacked_stego),
                "recovered_secret_sha256": sha256_array(
                    attacked_recovered
                ),
            }
            attacks.append(attack_record)
            if artifact_directory is not None:
                attack_directory = artifact_directory / "attacks"
                attack_directory.mkdir(exist_ok=True)
                save_grayscale(
                    attack_directory / f"{name}.png",
                    attacked_recovered,
                )

    pair_record: dict[str, object] = {
        "pair_id": pair.pair_id,
        "split": pair.split,
        "seed": effective_seed,
        "status": "ok",
        "inputs": {
            "cover": {
                "declared_path": pair.declared_cover,
                "file_sha256": sha256_file(pair.cover),
                "decoded_array_sha256": sha256_array(cover),
            },
            "secret": {
                "declared_path": pair.declared_secret,
                "file_sha256": sha256_file(pair.secret),
                "decoded_array_sha256": sha256_array(secret),
            },
            "metadata": dict(pair.metadata),
        },
        "outputs": {
            "stego_array_sha256": sha256_array(stego),
            "recovered_secret_array_sha256": sha256_array(recovered_secret),
        },
        "timing_seconds": {
            "embed": embed_seconds,
            "extract": extract_seconds,
            "total": embed_seconds + extract_seconds,
        },
        "method_metadata": dict(embedded.metadata),
        "extraction_metadata": dict(extracted.metadata),
        "attacks": attacks,
    }
    return result_rows, pair_record


def run_benchmark(
    manifest_path: str | Path,
    config: ExperimentConfig,
    output_dir: str | Path,
    *,
    method_name: str = "paper_baseline",
    include_attacks: bool = True,
    save_artifacts: bool = False,
    continue_on_error: bool = False,
    repository_cwd: str | Path | None = None,
) -> dict[str, object]:
    """Run a registered method over every declared manifest unit.

    The destination must be absent or empty.  This prevents stale files from a
    prior run from being mistaken for outputs of the current configuration.
    """

    cfg = config.validate()
    manifest = Path(manifest_path).resolve()
    pairs = read_manifest(manifest)
    method = build_method(method_name)
    destination = Path(output_dir).resolve()
    if destination.exists():
        if not destination.is_dir():
            raise NotADirectoryError(
                f"benchmark output path is not a directory: {destination}"
            )
        if any(destination.iterdir()):
            raise FileExistsError(
                f"benchmark output directory is not empty: {destination}"
            )

    manifest_hash = sha256_file(manifest)
    input_files_hash = sha256_json(
        [
            {
                "pair_id": pair.pair_id,
                "seed": cfg.random_seed if pair.seed is None else pair.seed,
                "cover_sha256": sha256_file(pair.cover),
                "secret_sha256": sha256_file(pair.secret),
            }
            for pair in pairs
        ]
    )
    config_payload = cfg.to_dict()
    config_hash = sha256_json(config_payload)
    run_options = {
        "include_attacks": include_attacks,
        "save_artifacts": save_artifacts,
    }
    evaluation_code = {
        "attacks_sha256": sha256_file(Path(attacks_module.__file__)),
        "attack_suite_sha256": sha256_file(
            Path(attack_suite.__code__.co_filename)
        ),
        "benchmark_sha256": sha256_file(Path(run_benchmark.__code__.co_filename)),
        "image_io_sha256": sha256_file(Path(load_grayscale.__code__.co_filename)),
        "manifest_sha256": sha256_file(Path(read_manifest.__code__.co_filename)),
        "metrics_sha256": sha256_file(Path(metric_bundle.__code__.co_filename)),
    }
    method_source = inspect.getsourcefile(type(method))
    method_implementation_hash = (
        sha256_file(method_source)
        if method_source is not None and Path(method_source).is_file()
        else None
    )
    run_id = run_identifier(
        manifest_sha256=manifest_hash,
        input_files_sha256=input_files_hash,
        config_sha256=config_hash,
        evaluation_code_sha256=sha256_json(evaluation_code),
        method=method.name,
        method_version=method.version,
        method_implementation_sha256=method_implementation_hash,
        options=run_options,
    )
    started_utc = _utc_now()
    source_state = git_state(
        repository_cwd
        if repository_cwd is not None
        else Path(__file__).resolve().parent
    )
    environment = environment_snapshot()
    destination.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    pair_records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for pair in pairs:
        try:
            pair_rows, pair_record = _run_pair(
                pair=pair,
                base_config=cfg,
                method=method,
                include_attacks=include_attacks,
                save_artifacts=save_artifacts,
                destination=destination,
            )
            rows.extend(pair_rows)
            pair_records.append(pair_record)
        except Exception as error:
            effective_seed = cfg.random_seed if pair.seed is None else pair.seed
            failure = {
                "pair_id": pair.pair_id,
                "split": pair.split,
                "seed": effective_seed,
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
            failures.append(failure)
            pair_records.append(failure)
            if not continue_on_error:
                break

    summary_rows = _aggregate(rows)
    _write_csv(destination / "results_long.csv", rows, RESULT_FIELDS)
    summary_fields = (
        *GROUP_FIELDS,
        "count_total",
        "count_finite",
        "count_nonfinite",
        "mean",
        "median",
        "std",
        "minimum",
        "maximum",
    )
    _write_csv(destination / "summary.csv", summary_rows, summary_fields)

    provenance: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "started_utc": started_utc,
        "completed_utc": _utc_now(),
        "method": {
            "name": method.name,
            "version": method.version,
            "implementation_sha256": method_implementation_hash,
        },
        "manifest": {
            "filename": manifest.name,
            "sha256": manifest_hash,
            "input_files_sha256": input_files_hash,
            "unit_count": len(pairs),
        },
        "config": config_payload,
        "config_sha256": config_hash,
        "options": run_options,
        "evaluation_code": evaluation_code,
        "source": source_state,
        "environment": environment,
    }
    with (destination / "provenance.json").open("w", encoding="utf-8") as stream:
        json.dump(
            _json_safe_tree(provenance),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")

    result: dict[str, object] = {
        "schema_version": 1,
        "run_id": run_id,
        "method": {"name": method.name, "version": method.version},
        "successful_units": len(pair_records) - len(failures),
        "failed_units": len(failures),
        "result_row_count": len(rows),
        "pairs": pair_records,
        "failures": failures,
        "files": {
            "results": "results_long.csv",
            "summary": "summary.csv",
            "provenance": "provenance.json",
        },
    }
    with (destination / "benchmark.json").open("w", encoding="utf-8") as stream:
        json.dump(
            _json_safe_tree(result),
            stream,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")

    if failures and not continue_on_error:
        first = failures[0]
        raise RuntimeError(
            f"benchmark stopped at {first['pair_id']}: "
            f"{first['error_type']}: {first['error']}"
        )
    return _json_safe_tree(result)
