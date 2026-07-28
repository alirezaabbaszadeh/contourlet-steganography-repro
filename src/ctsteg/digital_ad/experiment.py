"""Stage-gated digital experiments and complete evidence artifacts."""

from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike

from ctsteg.metrics import bit_error_rate, metric_bundle
from ctsteg.provenance import environment_snapshot, git_state, sha256_array, sha256_json

from .attacks import DigitalAttack, final_attack_suite, pilot_attacks
from .bitplanes import bytes_to_nibbles, split_secret
from .calibration import StabilityProfile
from .config import DigitalADConfig
from .pipeline import DigitalExtraction, DigitalRun, extract, run_clean
from .preprocessing import save_uint8_grayscale
from .transform_audit import audit_transform
from .types import MethodId


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


def _safe_number(value: float) -> float | str:
    if math.isfinite(value):
        return value
    if math.isnan(value):
        return "nan"
    return "inf" if value > 0 else "-inf"


def _metric_direction(name: str) -> str:
    if name in {
        "mse",
        "ber",
        "raw_ber",
        "base_ber",
        "detail_ber",
        "failed_codewords",
        "effective_unrecovered_bit_rate",
    } or name.endswith("_mse") or name.endswith("_ber"):
        return "lower"
    return "higher"


def _metric_rows(
    *,
    method: MethodId,
    pair_id: str,
    scope: str,
    metrics: Mapping[str, float],
    attack: DigitalAttack | None = None,
) -> list[dict[str, object]]:
    return [
        {
            "method": method.name,
            "method_version": "digital-ad-v1",
            "pair_id": pair_id,
            "split": "",
            "seed": "",
            "scope": scope,
            "attack": "" if attack is None else attack.name,
            "parameter": "" if attack is None else attack.parameter,
            "attack_value": "" if attack is None else attack.value,
            "metric": name,
            "direction": _metric_direction(name),
            "value": value,
        }
        for name, value in metrics.items()
    ]


def _decode_metrics(
    extraction: DigitalExtraction,
    *,
    base_reference: bytes,
    detail_reference: bytes,
) -> dict[str, float]:
    outcome = extraction.decode
    total_layer_bits = len(base_reference) * 8
    recovered_correct_bits = 0
    known_bits = 0
    metrics = {
        "decode_success": float(outcome.success),
        "header_valid": float(outcome.header_valid),
        "payload_crc_valid": float(outcome.payload_crc_valid),
        "raw_ber": extraction.raw_ber,
        "failed_codewords": float(
            sum(
                failure.codeword_index is not None
                for failure in outcome.failures
            )
        ),
    }
    if outcome.base_bytes is not None:
        reference = np.frombuffer(base_reference, dtype=np.uint8)
        candidate = np.frombuffer(outcome.base_bytes, dtype=np.uint8)
        errors = int(np.unpackbits(np.bitwise_xor(reference, candidate)).sum())
        metrics["base_ber"] = float(errors / total_layer_bits)
        known_bits += total_layer_bits
        recovered_correct_bits += total_layer_bits - errors
    if outcome.detail_bytes is not None:
        reference = np.frombuffer(detail_reference, dtype=np.uint8)
        candidate = np.frombuffer(outcome.detail_bytes, dtype=np.uint8)
        errors = int(np.unpackbits(np.bitwise_xor(reference, candidate)).sum())
        metrics["detail_ber"] = float(errors / total_layer_bits)
        known_bits += total_layer_bits
        recovered_correct_bits += total_layer_bits - errors
    total_bits = total_layer_bits * 2
    metrics["known_bit_fraction"] = known_bits / total_bits
    metrics["correct_recovered_bit_fraction"] = (
        recovered_correct_bits / total_bits
    )
    metrics["effective_unrecovered_bit_rate"] = 1.0 - (
        recovered_correct_bits / total_bits
    )
    return metrics


def _attack_set(profile: str, seed: int) -> tuple[DigitalAttack, ...]:
    if profile == "none":
        return ()
    if profile == "pilot":
        return pilot_attacks(seed)
    if profile == "final":
        return final_attack_suite(seed)
    raise ValueError("attack_profile must be 'none', 'pilot', or 'final'")


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run_digital_experiment(
    cover: ArrayLike,
    secret: ArrayLike,
    *,
    pair_id: str,
    method: MethodId | str | int,
    config: DigitalADConfig,
    output_dir: str | Path,
    stability_profile: StabilityProfile | None = None,
    attack_profile: str = "pilot",
) -> dict[str, Any]:
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"output directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    cfg = config.validate()
    selected = MethodId.parse(method)
    if (
        selected.uses_adaptive_allocation
        and attack_profile == "final"
        and stability_profile is None
    ):
        raise ValueError(
            "final C1/C3 runs require a transform-matched calibration "
            "stability profile"
        )
    stability = None if stability_profile is None else stability_profile.values

    started = time.perf_counter()
    clean = run_clean(
        cover,
        secret,
        pair_id=pair_id,
        method=selected,
        config=cfg,
        stability_profile=stability,
    )
    clean_elapsed = time.perf_counter() - started
    base_reference = clean.embedding.encoded.base.raw_bytes
    detail_reference = clean.embedding.encoded.detail.raw_bytes
    rows: list[dict[str, object]] = []
    cover_metrics = metric_bundle(clean.embedding.cover, clean.embedding.stego)
    rows.extend(
        _metric_rows(
            method=selected,
            pair_id=pair_id,
            scope="cover_stego",
            metrics=cover_metrics,
        )
    )
    clean_decode_metrics = _decode_metrics(
        clean.extraction,
        base_reference=base_reference,
        detail_reference=detail_reference,
    )
    rows.extend(
        _metric_rows(
            method=selected,
            pair_id=pair_id,
            scope="clean_decode",
            metrics=clean_decode_metrics,
        )
    )
    secret_recovery_metrics: dict[str, float] = {}
    if clean.extraction.decode.recovered_secret is not None:
        secret_recovery_metrics = metric_bundle(
            clean.embedding.secret,
            clean.extraction.decode.recovered_secret,
        )
        rows.extend(
            _metric_rows(
                method=selected,
                pair_id=pair_id,
                scope="secret_recovery",
                metrics=secret_recovery_metrics,
            )
        )

    attack_records: list[dict[str, Any]] = []
    attack_started = time.perf_counter()
    for attack in _attack_set(attack_profile, cfg.master_seed):
        attacked = attack.apply(clean.embedding.stego)
        attacked_extraction = extract(
            attacked,
            clean.embedding.cover,
            pair_id=pair_id,
            method=selected,
            config=cfg,
            stability_profile=stability,
            expected_bits=clean.embedding.encoded.bits,
        )
        metrics = _decode_metrics(
            attacked_extraction,
            base_reference=base_reference,
            detail_reference=detail_reference,
        )
        if attacked_extraction.decode.recovered_secret is not None:
            metrics.update(
                {
                    f"secret_{name}": value
                    for name, value in metric_bundle(
                        clean.embedding.secret,
                        attacked_extraction.decode.recovered_secret,
                    ).items()
                }
            )
        rows.extend(
            _metric_rows(
                method=selected,
                pair_id=pair_id,
                scope="attacked_decode",
                metrics=metrics,
                attack=attack,
            )
        )
        attack_records.append(
            {
                "name": attack.name,
                "parameter": attack.parameter,
                "value": attack.value,
                "decode_success": attacked_extraction.decode.success,
                "raw_ber": _safe_number(attacked_extraction.raw_ber),
                "failures": [
                    asdict(failure)
                    for failure in attacked_extraction.decode.failures
                ],
                "attacked_sha256": sha256_array(attacked),
            }
        )
        attack_dir = destination / "images" / "attacks"
        save_uint8_grayscale(
            attack_dir / f"{attack.name}-{attack.parameter}-{attack.value}.png",
            attacked,
        )
    attack_elapsed = time.perf_counter() - attack_started

    images = destination / "images"
    save_uint8_grayscale(images / "cover.png", clean.embedding.cover)
    save_uint8_grayscale(images / "secret.png", clean.embedding.secret)
    save_uint8_grayscale(images / "stego.png", clean.embedding.stego)
    difference = np.abs(
        clean.embedding.stego.astype(np.int16)
        - clean.embedding.cover.astype(np.int16)
    ).astype(np.uint8)
    save_uint8_grayscale(images / "difference.png", difference)
    base_original, detail_original = split_secret(clean.embedding.secret)
    save_uint8_grayscale(images / "base_original.png", base_original * 17)
    save_uint8_grayscale(images / "detail_original.png", detail_original * 17)
    if clean.extraction.decode.recovered_secret is not None:
        recovered = clean.extraction.decode.recovered_secret
        save_uint8_grayscale(images / "recovered.png", recovered)
        recovered_base, recovered_detail = split_secret(recovered)
        save_uint8_grayscale(images / "base_recovered.png", recovered_base * 17)
        save_uint8_grayscale(
            images / "detail_recovered.png",
            recovered_detail * 17,
        )

    with (destination / "metrics.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    config_payload = cfg.to_dict()
    transform_report = audit_transform(cfg)
    plan = clean.embedding.slot_plan
    capacity_report = {
        "required_slots": plan.total_slots,
        "header_slots": len(plan.header_slots),
        "body_slots": len(plan.body_slots),
        "candidate_slots": sum(plan.per_band_capacity),
        "per_band_capacity": dict(zip(plan.band_ids, plan.per_band_capacity)),
        "per_band_body_slots": dict(zip(plan.band_ids, plan.per_band_body_slots)),
        "body_layout": plan.body_layout,
        "overlap_count": 0,
    }
    feature_rows = [asdict(feature) for feature in clean.embedding.features]
    failures = {
        "clean": [
            asdict(failure) for failure in clean.extraction.decode.failures
        ],
        "attacks": attack_records,
    }
    metrics_payload = {
        "schema": 1,
        "method": selected.name,
        "pair_id": pair_id,
        "clean_success": clean.success,
        "clean_failure_reason": clean.failure_reason,
        "cover_stego": {
            key: _safe_number(value) for key, value in cover_metrics.items()
        },
        "clean_decode": {
            key: _safe_number(value)
            for key, value in clean_decode_metrics.items()
        },
        "secret_recovery": {
            key: _safe_number(value)
            for key, value in secret_recovery_metrics.items()
        },
        "attacks": attack_records,
    }
    runtime = {
        "clean_pipeline_seconds": clean_elapsed,
        "attacks_seconds": attack_elapsed,
        "total_seconds": time.perf_counter() - started,
        "selected_lambda": clean.embedding.lambda_search.strength,
        "selected_lambda_psnr_db": clean.embedding.lambda_search.psnr_db,
        "lambda_trials": len(clean.embedding.lambda_search.trials),
        "embedding_breakdown": dict(clean.embedding.timings),
        "clean_extraction_breakdown": dict(clean.extraction.timings),
    }
    provenance = {
        "schema": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "git": git_state(),
        "environment": environment_snapshot(),
        "config_sha256": sha256_json(config_payload),
        "cover_array_sha256": sha256_array(clean.embedding.cover),
        "secret_array_sha256": sha256_array(clean.embedding.secret),
        "stego_array_sha256": sha256_array(clean.embedding.stego),
        "coefficient_map_sha256": plan.coefficient_map_sha256,
        "transform_fingerprint": clean.metadata["transform_fingerprint"],
    }
    _write_json(destination / "config.json", config_payload)
    _write_json(destination / "transform_audit.json", transform_report)
    _write_json(destination / "capacity_report.json", capacity_report)
    _write_json(
        destination / "bitstream_manifest.json",
        dict(clean.embedding.encoded.manifest),
    )
    _write_json(
        destination / "coefficient_map.json",
        {
            "sha256": plan.coefficient_map_sha256,
            "band_ids": list(plan.band_ids),
            "body_layout": plan.body_layout,
        },
    )
    _write_json(
        destination / "permutation_hashes.json",
        {
            "base": clean.embedding.encoded.base.permutation_sha256,
            "detail": clean.embedding.encoded.detail.permutation_sha256,
        },
    )
    _write_json(destination / "subband_features.json", feature_rows)
    _write_json(destination / "metrics.json", metrics_payload)
    _write_json(destination / "failures.json", failures)
    _write_json(destination / "runtime.json", runtime)
    _write_json(destination / "provenance.json", provenance)
    (destination / "stdout.log").write_text(
        json.dumps(
            {
                "method": selected.name,
                "pair_id": pair_id,
                "clean_success": clean.success,
                "output_dir": str(destination),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "stderr.log").write_text("", encoding="utf-8")
    if cfg.clean_decode_required and not clean.success:
        _write_json(
            destination / "run_status.json",
            {"status": "failed", "reason": clean.failure_reason},
        )
    else:
        _write_json(destination / "run_status.json", {"status": "ok"})
    return {
        "method": selected.name,
        "pair_id": pair_id,
        "success": clean.success,
        "failure_reason": clean.failure_reason,
        "rows": rows,
        "metrics": metrics_payload,
        "runtime": runtime,
        "output_dir": str(destination),
    }
