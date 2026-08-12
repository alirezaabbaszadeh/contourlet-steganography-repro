"""Durable numerical workers for the five internal FINAL-5J-v1 methods.

B1 and B2 are intentionally unsupported here. Their approved adapters must
implement the same artifact contract before the main runner may dispatch them.
Scientific decode failures are committed as valid evidence objects; operational
exceptions remain failed attempts and never masquerade as results.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback
from typing import Any, Mapping

import numpy as np

try:
    import resource
except ImportError:  # pragma: no cover - Ubuntu is the scientific target
    resource = None

from ctsteg.metrics import metric_bundle
from ctsteg.provenance import sha256_array, sha256_file, sha256_json
from ctsteg.runtime import (
    ContentStore,
    atomic_write_bytes,
    atomic_write_json,
)

from .attacks import gaussian, jpeg, salt_and_pepper
from .bitplanes import progressive_reference
from .bitstream import encode_bitstream
from .calibration import load_stability_profile
from .config import DigitalADConfig, OCTAVE_PDFB_PROFILE
from .failure_severity import evaluate_internal_failure_severity
from .pipeline import extract, run_clean
from .preprocessing import load_uint8_grayscale, save_uint8_grayscale
from .transform_adapter import make_transform_adapter
from .types import MethodId


PROTOCOL_ID = "FINAL-5J-v1"
_INTERNAL_METHODS = {
    "C0": MethodId.C0_FIXED,
    "C1": MethodId.C1_A,
    "C2": MethodId.C2_D,
    "C3_NP": MethodId.C3_NP,
    "C3": MethodId.C3_A_D,
}
_BASELINE_METHODS = {"B1", "B2"}


class Worker5JError(RuntimeError):
    """Fail-closed operational error in a 5J numerical worker."""


def _peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (AttributeError, ValueError):
        return None
    if os.uname().sysname == "Darwin":
        return value
    return value * 1024


def _finite(value: float) -> float | None:
    result = float(value)
    return result if math.isfinite(result) else None


def _image_metrics(
    reference: np.ndarray,
    candidate: np.ndarray | None,
    *,
    missing: str = "not_recovered",
) -> dict[str, Any]:
    if candidate is None:
        return {
            "applicability": missing,
            "mse": None,
            "psnr": None,
            "ssim": None,
            "ncc": None,
        }
    values = metric_bundle(reference, candidate)
    return {
        "applicability": "applicable",
        "mse": _finite(values["mse"]),
        "psnr": _finite(values["psnr_db"]),
        "ssim": _finite(values["ssim_windowed"]),
        "ncc": _finite(values["ncc"]),
    }


def _bit_correct_fraction(reference: np.ndarray, candidate: np.ndarray | None) -> float | None:
    if candidate is None:
        return None
    first = np.asarray(reference, dtype=np.uint8)
    second = np.asarray(candidate, dtype=np.uint8)
    if first.shape != second.shape:
        raise Worker5JError("recovered image shape differs from the secret")
    errors = int(np.unpackbits(np.bitwise_xor(first, second)).sum())
    return float(1.0 - errors / (first.size * 8))


def _byte_ber(reference: bytes, candidate: bytes | None) -> float | None:
    if candidate is None:
        return None
    if len(reference) != len(candidate):
        raise Worker5JError("decoded layer length differs from its reference")
    if not reference:
        return None
    first = np.frombuffer(reference, dtype=np.uint8)
    second = np.frombuffer(candidate, dtype=np.uint8)
    errors = int(np.unpackbits(np.bitwise_xor(first, second)).sum())
    return float(errors / (len(reference) * 8))


def _codeword_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "applicability": value["applicability"],
        "total": value["total"],
        "successful": value["successful"],
        "failed": value["failed"],
        "corrected_symbols": value["corrected_symbols"],
        "fraction_at_or_below_radius": value["fraction_at_or_below_radius"],
        "overload_mean": value["overload_mean"],
        "overload_median": value["overload_median"],
        "overload_max": value["overload_max"],
    }


def _source_bundle_fingerprint(paths: tuple[Path, ...]) -> str:
    return sha256_json(
        {
            "schema": 1,
            "files": [
                {"path": path.name, "sha256": sha256_file(path)}
                for path in paths
            ],
        }
    )


def decoder_fingerprint() -> str:
    root = Path(__file__).resolve().parent
    return _source_bundle_fingerprint(
        tuple(
            root / name
            for name in (
                "bitplanes.py",
                "bitstream.py",
                "failure_severity.py",
                "header.py",
                "randomization.py",
                "reed_solomon.py",
            )
        )
    )


def metric_fingerprint() -> str:
    import ctsteg.metrics as metrics_module

    path = Path(str(metrics_module.__file__)).resolve()
    return sha256_file(path)


def _internal_method(task: Mapping[str, Any], source_fingerprint: str) -> MethodId:
    name = str(task.get("method", ""))
    if name in _BASELINE_METHODS:
        raise Worker5JError(
            f"{name} requires an approved external adapter; internal dispatch is forbidden"
        )
    try:
        selected = _INTERNAL_METHODS[name]
    except KeyError as error:
        raise Worker5JError(f"unknown FINAL-5J method: {name!r}") from error
    expected = sha256_json(
        {
            "protocol_id": PROTOCOL_ID,
            "payload_format_version": 2,
            "method": name,
            "source_fingerprint": source_fingerprint,
        }
    )
    if task.get("method_fingerprint") != expected:
        raise Worker5JError(f"method fingerprint mismatch for {name}")
    return selected


def _context_value(context: Mapping[str, Any], key: str) -> Any:
    if key not in context:
        raise Worker5JError(f"worker context is missing {key}")
    return context[key]


def _configure_external_runtime(context: Mapping[str, Any], config: DigitalADConfig) -> None:
    if config.transform_profile != OCTAVE_PDFB_PROFILE:
        return
    report = _context_value(context, "runtime_binding_report")
    if not isinstance(report, Mapping):
        raise Worker5JError("runtime_binding_report must be an object")
    values = {
        "CTSTEG_PDFB_RUNTIME": report.get("runtime_executable"),
        "CTSTEG_PDFB_TOOLBOX_PATH": report.get("toolbox"),
        "CTSTEG_PDFB_STAGE0_EVIDENCE": report.get("stage0_evidence"),
    }
    for name, value in values.items():
        if not isinstance(value, str) or not value:
            raise Worker5JError(f"runtime binding report is missing {name}")
        os.environ[name] = value


def _load_config(task: Mapping[str, Any], context: Mapping[str, Any]) -> DigitalADConfig:
    path = Path(str(_context_value(context, "config_path"))).resolve()
    expected = str(_context_value(context, "base_config_sha256"))
    actual = sha256_file(path)
    if actual != expected:
        raise Worker5JError(f"configuration file SHA-256 mismatch: {actual} != {expected}")
    config = DigitalADConfig.from_toml(path)
    if config.format_version != 2:
        raise Worker5JError("FINAL-5J worker requires payload format version 2")
    config = replace(config, psnr_target_db=float(task["target_psnr_db"])).validate()
    _configure_external_runtime(context, config)
    return config


def _pair(task: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    pairs = _context_value(context, "pair_inputs")
    if not isinstance(pairs, Mapping):
        raise Worker5JError("pair_inputs must be an object")
    pair_id = str(task["pair_id"])
    item = pairs.get(pair_id)
    if not isinstance(item, Mapping):
        raise Worker5JError(f"worker context does not resolve pair {pair_id}")
    cover_path = Path(str(item.get("cover", ""))).resolve()
    secret_path = Path(str(item.get("secret", ""))).resolve()
    for role, path in (("cover", cover_path), ("secret", secret_path)):
        if not path.is_file() or path.is_symlink():
            raise Worker5JError(f"{role} input is not a regular file: {path}")
        expected = str(task[f"{role}_sha256"])
        actual = sha256_file(path)
        if actual != expected:
            raise Worker5JError(
                f"{role} SHA-256 mismatch for {pair_id}: {actual} != {expected}"
            )
    return (
        load_uint8_grayscale(cover_path, size=512),
        load_uint8_grayscale(secret_path, size=128),
    )


def _stability(
    method: MethodId,
    config: DigitalADConfig,
    context: Mapping[str, Any],
) -> Mapping[str, float] | None:
    if not method.uses_adaptive_allocation:
        return None
    path = Path(str(_context_value(context, "stability_path"))).resolve()
    expected = str(_context_value(context, "stability_sha256"))
    actual = sha256_file(path)
    if actual != expected:
        raise Worker5JError(f"stability SHA-256 mismatch: {actual} != {expected}")
    return load_stability_profile(path, config=config).values


def _packed_bits(bits: np.ndarray) -> bytes:
    return np.packbits(np.asarray(bits, dtype=np.uint8), bitorder="big").tobytes()


def _embedding_object(
    task: Mapping[str, Any],
    destination: Path,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    source_fingerprint = str(_context_value(context, "source_fingerprint"))
    method = _internal_method(task, source_fingerprint)
    config = _load_config(task, context)
    cover, secret = _pair(task, context)
    stability = _stability(method, config, context)
    started = time.perf_counter()
    run = run_clean(
        cover,
        secret,
        pair_id=str(task["pair_id"]),
        method=method,
        config=config,
        stability_profile=stability,
        payload_fraction=float(task["payload_fraction"]),
    )
    total_seconds = time.perf_counter() - started
    embedding = run.embedding
    encoded_payload = _packed_bits(embedding.encoded.bits)
    realized_config = config.to_dict()
    realized_config_sha256 = sha256_json(realized_config)
    cover_stego = metric_bundle(embedding.cover, embedding.stego)
    transform_fingerprint = make_transform_adapter(config).fingerprint()

    images = destination / "images"
    save_uint8_grayscale(images / "stego.png", embedding.stego)
    atomic_write_bytes(destination / "protected_bits.bin", encoded_payload)
    atomic_write_json(
        destination / "protected_bits.json",
        {
            "schema_version": 1,
            "bit_count": int(embedding.encoded.bits.size),
            "byte_count": len(encoded_payload),
            "sha256": hashlib.sha256(encoded_payload).hexdigest(),
            "manifest": dict(embedding.encoded.manifest),
        },
    )
    atomic_write_json(destination / "realized_config.json", realized_config)
    atomic_write_json(
        destination / "coefficient_map.json",
        {
            "schema_version": 1,
            "sha256": embedding.slot_plan.coefficient_map_sha256,
            "body_layout": embedding.slot_plan.body_layout,
            "band_ids": list(embedding.slot_plan.band_ids),
            "per_band_body_slots": list(embedding.slot_plan.per_band_body_slots),
        },
    )
    failures = [asdict(item) for item in run.extraction.decode.failures]
    clean_severity = None
    if not run.success:
        clean_severity = evaluate_internal_failure_severity(
            encoded=run.embedding.encoded,
            extracted_bits=run.extraction.extracted_bits,
            outcome=run.extraction.decode,
        )
    record = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": str(_context_value(context, "run_id")),
        "object_id": str(task["embedding_id"]),
        "component": task["component"],
        "pair_id": task["pair_id"],
        "method": task["method"],
        "payload_format_version": 2,
        "payload_fraction": float(task["payload_fraction"]),
        "target_psnr_db": float(task["target_psnr_db"]),
        "protected_payload_bits": int(embedding.encoded.bits.size),
        "cover_sha256": task["cover_sha256"],
        "secret_sha256": task["secret_sha256"],
        "config_sha256": realized_config_sha256,
        "transform_fingerprint": transform_fingerprint,
        "method_fingerprint": task["method_fingerprint"],
        "source_fingerprint": source_fingerprint,
        "stego_sha256": sha256_array(embedding.stego),
        "coefficient_map_sha256": embedding.slot_plan.coefficient_map_sha256,
        "realized_cover_stego": {
            "mse": _finite(cover_stego["mse"]),
            "psnr": _finite(cover_stego["psnr_db"]),
            "ssim": _finite(cover_stego["ssim_windowed"]),
        },
        "timing": {
            "total_seconds": total_seconds,
            "peak_rss_bytes": _peak_rss_bytes(),
            "breakdown": {
                **dict(embedding.timings),
                **dict(run.extraction.timings),
            },
        },
        "status": "complete" if run.success else "scientific_failure",
        "failure": None if run.success else {
            "kind": "clean_decode_scientific_failure",
            "reason": run.failure_reason or "clean decode failed",
            "validity_state": run.extraction.decode.validity_state,
            "failure_stage": clean_severity["failure_stage"],
            "integrity": {
                "header_valid": bool(run.extraction.decode.header_valid),
                "payload_crc_valid": bool(run.extraction.decode.payload_crc_valid),
                "base_crc_valid": run.extraction.decode.base_crc_valid,
                "detail_crc_valid": run.extraction.decode.detail_crc_valid,
            },
            "failures": failures,
            "prerequisite_unreachable": True,
            "missingness": "not_evaluated",
        },
        "backup_state": "local_only",
    }
    atomic_write_json(destination / "embedding.json", record)
    atomic_write_json(destination / "clean_failures.json", failures)
    return record


def _unavailable_internal_codewords() -> dict[str, Any]:
    return {
        "applicability": "applicable",
        "total": None,
        "successful": None,
        "failed": None,
        "corrected_symbols": None,
        "fraction_at_or_below_radius": None,
        "overload_mean": None,
        "overload_median": None,
        "overload_max": None,
    }


def _recognized_clean_scientific_failure(
    record: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    if record.get("status") != "scientific_failure":
        return None
    failure = record.get("failure")
    if not isinstance(failure, Mapping):
        return None
    if (
        failure.get("kind") != "clean_decode_scientific_failure"
        or failure.get("prerequisite_unreachable") is not True
        or failure.get("missingness") != "not_evaluated"
    ):
        return None
    stage = str(failure.get("failure_stage", ""))
    validity = str(failure.get("validity_state", ""))
    if stage not in {
        "S1_BASE_ONLY",
        "S2_HEADER_VALID_PARTIAL",
        "S3_PAYLOAD_ECC_FAILURE",
        "S4_HEADER_FAILURE",
        "S5_EXTRACTION_TRANSFORM_FAILURE",
    }:
        return None
    if validity not in {
        "valid_base_only_recovery",
        "header_valid_no_valid_layer",
        "header_failure",
        "extraction_failure",
    }:
        return None
    integrity = failure.get("integrity")
    if not isinstance(integrity, Mapping):
        return None
    return failure


def _not_evaluated_internal_evaluation(
    task: Mapping[str, Any],
    destination: Path,
    context: Mapping[str, Any],
    *,
    cover: np.ndarray,
    secret: np.ndarray,
    stego: np.ndarray,
    embedding_record: Mapping[str, Any],
    failure: Mapping[str, Any],
) -> dict[str, Any]:
    reason = (
        "not_evaluated: prerequisite clean embedding scientific failure: "
        + str(failure.get("reason", "clean decode failed"))
    )
    integrity = failure["integrity"]
    record = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": str(_context_value(context, "run_id")),
        "object_id": str(task["evaluation_id"]),
        "embedding_object_id": str(task["embedding_id"]),
        "component": task["component"],
        "pair_id": task["pair_id"],
        "method": task["method"],
        "channel": {
            "instance_id": task["channel_instance_id"],
            "family": task["family"],
            "parameter": {
                "clean": None,
                "jpeg": "quality",
                "gaussian": "variance",
                "salt_pepper": "density",
            }[str(task["family"])],
            "severity": task["severity"],
            "realization": task["realization"],
            "pair_seed": task["pair_seed"],
        },
        "status": "scientific_failure",
        "validity_state": str(failure["validity_state"]),
        "failure_stage": str(failure["failure_stage"]),
        "integrity": {
            "header_valid": bool(integrity.get("header_valid", False)),
            "payload_crc_valid": bool(integrity.get("payload_crc_valid", False)),
            "base_crc_valid": integrity.get("base_crc_valid"),
            "detail_crc_valid": integrity.get("detail_crc_valid"),
        },
        "recovery": {
            "complete_recovery": False,
            "valid_base_only_recovery": None,
            "raw_ber": None,
            "payload_correct_fraction": None,
            "raw_secret_correct_fraction": None,
            "base_correct_fraction": None,
            "detail_correct_fraction": None,
            "base_ber": None,
            "detail_ber": None,
            "unknown_bit_fraction": None,
        },
        "codewords": {
            "base": _unavailable_internal_codewords(),
            "detail": _unavailable_internal_codewords(),
            "diagnostics_object_id": None,
        },
        "metrics": {
            "cover_stego": _image_metrics(cover, stego),
            "complete_secret": _image_metrics(secret, None),
            "base_only_secret": _image_metrics(secret, None),
        },
        "timing": {
            "attack_seconds": None,
            "extraction_seconds": None,
            "total_seconds": None,
            "peak_rss_bytes": _peak_rss_bytes(),
        },
        "failures": [
            {
                "stage": str(failure["failure_stage"]),
                "reason": reason,
                "layer": None,
                "codeword_index": None,
            }
        ],
        "provenance": {
            "source_fingerprint": str(_context_value(context, "source_fingerprint")),
            "config_sha256": str(embedding_record["config_sha256"]),
            "decoder_fingerprint": decoder_fingerprint(),
            "metric_fingerprint": metric_fingerprint(),
            "attacked_sha256": None,
        },
        "backup_state": "local_only",
    }
    atomic_write_json(destination / "evaluation.json", record)
    return record


def _apply_channel(image: np.ndarray, task: Mapping[str, Any]) -> np.ndarray:
    family = str(task["family"])
    severity = task.get("severity")
    seed = task.get("pair_seed")
    if family == "clean":
        return image.copy()
    if family == "jpeg":
        return jpeg(image, quality=int(severity))
    if family == "gaussian":
        if not isinstance(seed, int):
            raise Worker5JError("gaussian channel requires a pair seed")
        return gaussian(image, variance=float(severity), seed=seed)
    if family == "salt_pepper":
        if not isinstance(seed, int):
            raise Worker5JError("salt-pepper channel requires a pair seed")
        return salt_and_pepper(image, density=float(severity), seed=seed)
    raise Worker5JError(f"unsupported channel family: {family}")


def _evaluation_object(
    task: Mapping[str, Any],
    destination: Path,
    context: Mapping[str, Any],
    store: ContentStore,
) -> dict[str, Any]:
    source_fingerprint = str(_context_value(context, "source_fingerprint"))
    method = _internal_method(task, source_fingerprint)
    cover, secret = _pair(task, context)
    embedding_id = str(task["embedding_id"])
    verification = store.verify(embedding_id, deep=True)
    if not verification.valid:
        raise Worker5JError(
            f"embedding object {embedding_id} is invalid: {verification.reason}"
        )
    embedding_record = json.loads(
        (verification.path / "embedding.json").read_text(encoding="utf-8")
    )
    stego = load_uint8_grayscale(
        verification.path / "images" / "stego.png",
        size=512,
    )
    if embedding_record.get("status") == "scientific_failure":
        failure = _recognized_clean_scientific_failure(embedding_record)
        if failure is None:
            raise Worker5JError(
                f"unsupported scientific embedding failure {embedding_id}"
            )
        return _not_evaluated_internal_evaluation(
            task,
            destination,
            context,
            cover=cover,
            secret=secret,
            stego=stego,
            embedding_record=embedding_record,
            failure=failure,
        )
    if embedding_record.get("status") != "complete":
        raise Worker5JError(
            f"evaluation is blocked by non-complete embedding {embedding_id}"
        )
    config = _load_config(task, context)
    stability = _stability(method, config, context)
    encoded = encode_bitstream(
        secret,
        pair_id=str(task["pair_id"]),
        method=method,
        config=config,
        payload_fraction=float(embedding_record["payload_fraction"]),
    )
    packed = _packed_bits(encoded.bits)
    protected_manifest = json.loads(
        (verification.path / "protected_bits.json").read_text(encoding="utf-8")
    )
    if hashlib.sha256(packed).hexdigest() != protected_manifest.get("sha256"):
        raise Worker5JError("recomputed protected bitstream differs from embedding")

    total_started = time.perf_counter()
    attack_started = time.perf_counter()
    attacked = _apply_channel(stego, task)
    attack_seconds = time.perf_counter() - attack_started
    extraction_started = time.perf_counter()
    extraction = extract(
        attacked,
        cover,
        pair_id=str(task["pair_id"]),
        method=method,
        config=config,
        stability_profile=stability,
        expected_bits=encoded.bits,
        expected_payload_fraction=float(embedding_record["payload_fraction"]),
    )
    extraction_seconds = time.perf_counter() - extraction_started
    total_seconds = time.perf_counter() - total_started
    outcome = extraction.decode
    severity = evaluate_internal_failure_severity(
        encoded=encoded,
        extracted_bits=extraction.extracted_bits,
        outcome=outcome,
    )
    candidate = (
        outcome.recovered_secret
        if outcome.recovered_secret is not None
        else outcome.base_reconstruction
        if outcome.base_only_success
        else None
    )
    base_ber = _byte_ber(encoded.base.raw_bytes, outcome.base_bytes)
    detail_ber = (
        None
        if encoded.layout.detail_bits == 0
        else _byte_ber(encoded.detail.raw_bytes, outcome.detail_bytes)
    )
    complete_metrics = _image_metrics(secret, outcome.recovered_secret)
    base_metrics = _image_metrics(secret, outcome.base_reconstruction)
    cover_stego_metrics = _image_metrics(cover, stego)
    diagnostics_object_id = sha256_json(severity)
    failures = [asdict(item) for item in outcome.failures]
    realized_config_sha256 = sha256_json(config.to_dict())

    images = destination / "images"
    save_uint8_grayscale(images / "attacked.png", attacked)
    if outcome.recovered_secret is not None:
        save_uint8_grayscale(images / "recovered.png", outcome.recovered_secret)
    if outcome.base_reconstruction is not None:
        save_uint8_grayscale(
            images / "base_reconstruction.png",
            outcome.base_reconstruction,
        )
    atomic_write_json(destination / "codeword_diagnostics.json", severity)
    record = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": str(_context_value(context, "run_id")),
        "object_id": str(task["evaluation_id"]),
        "embedding_object_id": embedding_id,
        "component": task["component"],
        "pair_id": task["pair_id"],
        "method": task["method"],
        "channel": {
            "instance_id": task["channel_instance_id"],
            "family": task["family"],
            "parameter": {
                "clean": None,
                "jpeg": "quality",
                "gaussian": "variance",
                "salt_pepper": "density",
            }[str(task["family"])],
            "severity": task["severity"],
            "realization": task["realization"],
            "pair_seed": task["pair_seed"],
        },
        "status": "complete" if outcome.success else "scientific_failure",
        "validity_state": outcome.validity_state,
        "failure_stage": severity["failure_stage"],
        "integrity": {
            "header_valid": bool(outcome.header_valid),
            "payload_crc_valid": bool(outcome.payload_crc_valid),
            "base_crc_valid": outcome.base_crc_valid,
            "detail_crc_valid": outcome.detail_crc_valid,
        },
        "recovery": {
            "complete_recovery": bool(outcome.success),
            "valid_base_only_recovery": bool(outcome.base_only_success),
            "raw_ber": _finite(extraction.raw_ber),
            "payload_correct_fraction": severity["recovery"][
                "payload_correct_fraction"
            ],
            "raw_secret_correct_fraction": _bit_correct_fraction(secret, candidate),
            "base_correct_fraction": severity["recovery"][
                "base_correct_fraction"
            ],
            "detail_correct_fraction": severity["recovery"][
                "detail_correct_fraction"
            ],
            "base_ber": base_ber,
            "detail_ber": detail_ber,
            "unknown_bit_fraction": severity["recovery"][
                "unknown_bit_fraction"
            ],
        },
        "codewords": {
            "base": _codeword_summary(severity["base"]),
            "detail": _codeword_summary(severity["detail"]),
            "diagnostics_object_id": diagnostics_object_id,
        },
        "metrics": {
            "cover_stego": cover_stego_metrics,
            "complete_secret": complete_metrics,
            "base_only_secret": base_metrics,
        },
        "timing": {
            "attack_seconds": attack_seconds,
            "extraction_seconds": extraction_seconds,
            "total_seconds": total_seconds,
            "peak_rss_bytes": _peak_rss_bytes(),
        },
        "failures": failures,
        "provenance": {
            "source_fingerprint": source_fingerprint,
            "config_sha256": realized_config_sha256,
            "decoder_fingerprint": decoder_fingerprint(),
            "metric_fingerprint": metric_fingerprint(),
            "attacked_sha256": sha256_array(attacked),
        },
        "backup_state": "local_only",
    }
    atomic_write_json(destination / "evaluation.json", record)
    return record


def execute_internal_task(
    task: Mapping[str, Any],
    *,
    kind: str,
    context: Mapping[str, Any],
    cache_dir: str | Path,
) -> dict[str, Any]:
    """Execute or reuse one immutable internal embedding/evaluation task."""

    if kind not in {"embedding", "evaluation"}:
        raise Worker5JError("kind must be embedding or evaluation")
    id_field = "embedding_id" if kind == "embedding" else "evaluation_id"
    object_id = str(task.get(id_field, ""))
    store = ContentStore(cache_dir)
    existing = store.verify(object_id, deep=True)
    if existing.valid:
        return {
            "status": "cached",
            "kind": kind,
            "object_id": object_id,
            "path": str(existing.path),
            "byte_count": existing.byte_count,
        }
    attempt = store.begin_attempt(object_id)
    try:
        atomic_write_json(attempt / "task.json", dict(task))
        atomic_write_json(
            attempt / "execution_context.json",
            {
                "protocol_id": PROTOCOL_ID,
                "run_id": context.get("run_id"),
                "source_fingerprint": context.get("source_fingerprint"),
                "base_config_sha256": context.get("base_config_sha256"),
                "stability_sha256": context.get("stability_sha256"),
            },
        )
        if kind == "embedding":
            record = _embedding_object(task, attempt, context)
        else:
            record = _evaluation_object(task, attempt, context, store)
        atomic_write_json(attempt / "producer_result.json", record)
        verification = store.commit_attempt(
            object_id,
            attempt,
            task_material_sha256=sha256_json(dict(task)),
        )
        return {
            "status": "completed",
            "kind": kind,
            "object_id": object_id,
            "scientific_status": record["status"],
            "path": str(verification.path),
            "byte_count": verification.byte_count,
        }
    except BaseException as error:
        store.record_failure(
            attempt,
            object_id=object_id,
            error=error,
            traceback_text=traceback.format_exc(),
        )
        return {
            "status": "failed",
            "kind": kind,
            "object_id": object_id,
            "attempt_path": str(attempt),
            "error_type": type(error).__name__,
            "error": str(error),
        }
