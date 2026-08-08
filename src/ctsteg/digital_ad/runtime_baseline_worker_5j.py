"""Content-addressed runtime worker for FINAL-5J B1/B2 baselines."""

from __future__ import annotations

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
except ImportError:  # pragma: no cover
    resource = None

import ctsteg.metrics as metrics_module
from ctsteg.metrics import metric_bundle
from ctsteg.provenance import sha256_array, sha256_file, sha256_json
from ctsteg.runtime import (
    ContentStore,
    atomic_write_bytes,
    atomic_write_json,
)

from .attacks import gaussian, jpeg, salt_and_pepper
from .baselines_5j import (
    embed_baseline,
    extract_baseline,
    raw_payload_bits,
)
from .preprocessing import load_uint8_grayscale, save_uint8_grayscale


PROTOCOL_ID = "FINAL-5J-v1"
BASELINE_METHODS = {"B1", "B2"}


class BaselineWorker5JError(RuntimeError):
    """Fail-closed operational error in a baseline task."""


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


def _not_applicable_codewords() -> dict[str, Any]:
    return {
        "applicability": "not_applicable",
        "total": None,
        "successful": None,
        "failed": None,
        "corrected_symbols": None,
        "fraction_at_or_below_radius": None,
        "overload_mean": None,
        "overload_median": None,
        "overload_max": None,
    }


def _pair(
    task: Mapping[str, Any],
    context: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    pairs = context.get("pair_inputs")
    if not isinstance(pairs, Mapping):
        raise BaselineWorker5JError("pair_inputs must be an object")
    pair_id = str(task["pair_id"])
    item = pairs.get(pair_id)
    if not isinstance(item, Mapping):
        raise BaselineWorker5JError(f"unresolved pair: {pair_id}")
    paths = {
        "cover": Path(str(item.get("cover", ""))).resolve(),
        "secret": Path(str(item.get("secret", ""))).resolve(),
    }
    for role, path in paths.items():
        if not path.is_file() or path.is_symlink():
            raise BaselineWorker5JError(
                f"{role} is not a regular file: {path}"
            )
        expected = str(task[f"{role}_sha256"])
        actual = sha256_file(path)
        if actual != expected:
            raise BaselineWorker5JError(
                f"{role} SHA-256 mismatch for {pair_id}: {actual} != {expected}"
            )
    return (
        load_uint8_grayscale(paths["cover"], size=512),
        load_uint8_grayscale(paths["secret"], size=128),
    )


def _verify_method(
    task: Mapping[str, Any],
    context: Mapping[str, Any],
) -> str:
    method = str(task.get("method", ""))
    if method not in BASELINE_METHODS:
        raise BaselineWorker5JError(f"not a baseline method: {method!r}")
    expected_map = context.get("baseline_method_fingerprints")
    if not isinstance(expected_map, Mapping):
        raise BaselineWorker5JError(
            "baseline_method_fingerprints must be an object"
        )
    expected = str(expected_map.get(method, ""))
    if not expected or task.get("method_fingerprint") != expected:
        raise BaselineWorker5JError(
            f"baseline method fingerprint mismatch for {method}"
        )
    return method


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
            raise BaselineWorker5JError("gaussian channel requires a seed")
        return gaussian(image, variance=float(severity), seed=seed)
    if family == "salt_pepper":
        if not isinstance(seed, int):
            raise BaselineWorker5JError("salt-pepper channel requires a seed")
        return salt_and_pepper(image, density=float(severity), seed=seed)
    raise BaselineWorker5JError(f"unsupported channel family: {family}")


def _packed_bits(bits: np.ndarray) -> bytes:
    return np.packbits(
        np.asarray(bits, dtype=np.uint8),
        bitorder="big",
    ).tobytes()


def _embedding_object(
    task: Mapping[str, Any],
    destination: Path,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    method = _verify_method(task, context)
    cover, secret = _pair(task, context)
    started = time.perf_counter()
    embedding = embed_baseline(
        method,
        cover,
        secret,
        payload_fraction=float(task["payload_fraction"]),
        target_psnr_db=float(task["target_psnr_db"]),
    )
    total_seconds = time.perf_counter() - started
    clean = extract_baseline(
        method,
        embedding.stego,
        reference_bits=embedding.payload_bits,
        payload_fraction=float(task["payload_fraction"]),
        parameters=embedding.parameters,
    )
    if not clean.complete_recovery:
        raise BaselineWorker5JError(
            f"{method} clean round trip failed with "
            f"{clean.bit_errors} bit errors"
        )

    images = destination / "images"
    save_uint8_grayscale(images / "stego.png", embedding.stego)
    payload_bytes = _packed_bits(embedding.payload_bits)
    atomic_write_bytes(destination / "raw_payload_bits.bin", payload_bytes)
    atomic_write_json(
        destination / "raw_payload_bits.json",
        {
            "schema_version": 1,
            "bit_count": int(embedding.payload_bits.size),
            "byte_count": len(payload_bytes),
            "sha256": hashlib.sha256(payload_bytes).hexdigest(),
        },
    )
    atomic_write_json(
        destination / "baseline_parameters.json",
        dict(embedding.parameters),
    )
    record = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": str(context["run_id"]),
        "object_id": str(task["embedding_id"]),
        "component": task["component"],
        "pair_id": task["pair_id"],
        "method": method,
        "payload_format_version": 2,
        "payload_fraction": float(task["payload_fraction"]),
        "target_psnr_db": float(task["target_psnr_db"]),
        "protected_payload_bits": int(embedding.payload_bits.size),
        "cover_sha256": task["cover_sha256"],
        "secret_sha256": task["secret_sha256"],
        "config_sha256": str(context["base_config_sha256"]),
        "transform_fingerprint": sha256_json(
            {
                "method": method,
                "parameters": dict(embedding.parameters),
            }
        ),
        "method_fingerprint": task["method_fingerprint"],
        "source_fingerprint": str(context["source_fingerprint"]),
        "stego_sha256": sha256_array(embedding.stego),
        "coefficient_map_sha256": None,
        "realized_cover_stego": {
            "mse": _finite(embedding.cover_stego_metrics["mse"]),
            "psnr": _finite(embedding.cover_stego_metrics["psnr_db"]),
            "ssim": _finite(
                embedding.cover_stego_metrics["ssim_windowed"]
            ),
        },
        "timing": {
            "total_seconds": total_seconds,
            "peak_rss_bytes": _peak_rss_bytes(),
            "breakdown": {
                "baseline_embedding_seconds": total_seconds,
            },
        },
        "status": "complete",
        "failure": None,
        "backup_state": "local_only",
    }
    atomic_write_json(destination / "embedding.json", record)
    return record


def _evaluation_object(
    task: Mapping[str, Any],
    destination: Path,
    context: Mapping[str, Any],
    store: ContentStore,
) -> dict[str, Any]:
    method = _verify_method(task, context)
    cover, secret = _pair(task, context)
    embedding_id = str(task["embedding_id"])
    verification = store.verify(embedding_id, deep=True)
    if not verification.valid:
        raise BaselineWorker5JError(
            f"embedding {embedding_id} is invalid: {verification.reason}"
        )
    embedding_record = json.loads(
        (verification.path / "embedding.json").read_text(encoding="utf-8")
    )
    if embedding_record.get("status") != "complete":
        raise BaselineWorker5JError(
            "baseline evaluation requires a complete embedding"
        )
    stego = load_uint8_grayscale(
        verification.path / "images" / "stego.png",
        size=512,
    )
    parameters = json.loads(
        (verification.path / "baseline_parameters.json").read_text(
            encoding="utf-8"
        )
    )
    reference_bits = raw_payload_bits(
        secret,
        payload_fraction=float(task["payload_fraction"]),
    )

    total_started = time.perf_counter()
    attack_started = time.perf_counter()
    attacked = _apply_channel(stego, task)
    attack_seconds = time.perf_counter() - attack_started
    extraction_started = time.perf_counter()
    extraction = extract_baseline(
        method,
        attacked,
        reference_bits=reference_bits,
        payload_fraction=float(task["payload_fraction"]),
        parameters=parameters,
    )
    extraction_seconds = time.perf_counter() - extraction_started
    total_seconds = time.perf_counter() - total_started

    complete = bool(extraction.complete_recovery)
    validity_state = (
        "complete_valid_recovery"
        if complete
        else "header_valid_no_valid_layer"
    )
    failure_stage = "S0_COMPLETE" if complete else "S2_HEADER_VALID_PARTIAL"
    failures = []
    if not complete:
        failures.append(
            {
                "stage": failure_stage,
                "reason": (
                    f"baseline payload contains "
                    f"{extraction.bit_errors} bit errors"
                ),
                "layer": None,
                "codeword_index": None,
            }
        )

    images = destination / "images"
    save_uint8_grayscale(images / "attacked.png", attacked)
    save_uint8_grayscale(images / "recovered.png", extraction.reconstructed)
    record = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "run_id": str(context["run_id"]),
        "object_id": str(task["evaluation_id"]),
        "embedding_object_id": embedding_id,
        "component": task["component"],
        "pair_id": task["pair_id"],
        "method": method,
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
        "status": "complete" if complete else "scientific_failure",
        "validity_state": validity_state,
        "failure_stage": failure_stage,
        "integrity": {
            "header_valid": True,
            "payload_crc_valid": complete,
            "base_crc_valid": None,
            "detail_crc_valid": None,
        },
        "recovery": {
            "complete_recovery": complete,
            "valid_base_only_recovery": None,
            "raw_ber": float(extraction.ber),
            "payload_correct_fraction": float(1.0 - extraction.ber),
            "raw_secret_correct_fraction": float(1.0 - extraction.ber),
            "base_correct_fraction": None,
            "detail_correct_fraction": None,
            "base_ber": None,
            "detail_ber": None,
            "unknown_bit_fraction": 0.0,
        },
        "codewords": {
            "base": _not_applicable_codewords(),
            "detail": _not_applicable_codewords(),
            "diagnostics_object_id": None,
        },
        "metrics": {
            "cover_stego": _image_metrics(cover, stego),
            "complete_secret": _image_metrics(
                secret,
                extraction.reconstructed,
            ),
            "base_only_secret": _image_metrics(
                secret,
                None,
                missing="not_applicable",
            ),
        },
        "timing": {
            "attack_seconds": attack_seconds,
            "extraction_seconds": extraction_seconds,
            "total_seconds": total_seconds,
            "peak_rss_bytes": _peak_rss_bytes(),
        },
        "failures": failures,
        "provenance": {
            "source_fingerprint": str(context["source_fingerprint"]),
            "config_sha256": str(context["base_config_sha256"]),
            "decoder_fingerprint": sha256_file(
                Path(__file__).resolve().parent / "baselines_5j.py"
            ),
            "metric_fingerprint": sha256_file(
                Path(str(metrics_module.__file__)).resolve()
            ),
            "attacked_sha256": sha256_array(attacked),
        },
        "backup_state": "local_only",
    }
    atomic_write_json(destination / "evaluation.json", record)
    return record


def execute_baseline_task(
    task: Mapping[str, Any],
    *,
    kind: str,
    context: Mapping[str, Any],
    cache_dir: str | Path,
) -> dict[str, Any]:
    """Execute or reuse one immutable B1/B2 embedding or evaluation."""
    if kind not in {"embedding", "evaluation"}:
        raise BaselineWorker5JError("kind must be embedding or evaluation")
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
                "baseline_method_fingerprints": context.get(
                    "baseline_method_fingerprints"
                ),
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
