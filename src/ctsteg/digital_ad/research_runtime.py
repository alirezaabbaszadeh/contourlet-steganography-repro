"""Lean 64/88 research runner with parallel, resumable artifact execution."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import csv
from dataclasses import asdict, dataclass
import hashlib
import inspect
import io
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import tarfile
import time
import traceback
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

try:
    import resource
except ImportError:  # pragma: no cover - Ubuntu is the research target
    resource = None

from ctsteg.manifest import ImagePair, read_manifest
from ctsteg.metrics import metric_bundle
from ctsteg.provenance import (
    environment_snapshot,
    git_state,
    sha256_array,
    sha256_file,
    sha256_json,
)
from ctsteg.runtime import (
    ContentStore,
    DurableTask,
    DurableTaskRunner,
    RunLock,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    content_object_id,
    read_json,
    resolve_worker_count,
    task_material_sha256,
    utc_now,
)
from ctsteg.runtime_gate_contract import validate_runtime_gate_report

from .attacks import gaussian, jpeg, salt_and_pepper
from .bitplanes import nibbles_to_bytes, split_secret
from .bitstream import encode_bitstream
from .calibration import load_stability_profile
from .config import DigitalADConfig, OCTAVE_PDFB_PROFILE
from .experiment import _decode_metrics, _safe_number, run_digital_experiment
from .pipeline import extract
from .preprocessing import load_uint8_grayscale, save_uint8_grayscale
from .transform_adapter import make_transform_adapter
from .types import MethodId


PROTOCOL_VERSION = "DIGITAL_A_D-research-v2-lean"
RUNTIME_IMPLEMENTATION = "durable-runtime-v1"
EMBEDDING_OBJECT_SCHEMA = 1
EVALUATION_OBJECT_SCHEMA = 1
MANDATORY_ROWS = 64
MANDATORY_EMBEDDINGS = 16
MAX_CONDITIONAL_ROWS = 24
ABSOLUTE_MAX_ROWS = 88
CORE_PAIR_COUNT = 4
CORE_METHODS = (
    MethodId.C0_FIXED,
    MethodId.C1_A,
    MethodId.C2_D,
    MethodId.C3_A_D,
)
REQUIRED_MANIFEST_METADATA = (
    "cover_source_id",
    "secret_source_id",
    "cover_rights",
    "secret_rights",
    "cover_sha256",
    "secret_sha256",
    "cover_array_sha256",
    "secret_array_sha256",
)
EVALUATION_FIELDS = (
    "protocol_version",
    "run_id",
    "pair_id",
    "split",
    "method",
    "channel_id",
    "family",
    "parameter",
    "attack_value",
    "severity",
    "realization_id",
    "status",
    "decode_success",
    "header_valid",
    "payload_crc_valid",
    "raw_ber",
    "base_ber",
    "detail_ber",
    "effective_unrecovered_bit_rate",
    "secret_mse",
    "secret_psnr",
    "secret_ssim",
    "cover_stego_mse",
    "cover_stego_psnr",
    "cover_stego_ssim",
    "protected_payload_bits",
    "selected_lambda",
    "embedding_seconds",
    "attack_seconds",
    "extraction_seconds",
    "worker_peak_rss_mb",
    "embedding_object_id",
    "evaluation_object_id",
    "attacked_sha256",
    "failure_count",
)


@dataclass(frozen=True)
class ChannelSpec:
    channel_id: str
    family: str
    parameter: str
    value: float | int | None
    severity: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


CLEAN = ChannelSpec("clean", "clean", "", None, "clean")
CORE_CHANNELS = (
    ChannelSpec("jpeg-q70", "jpeg", "quality", 70, "medium"),
    ChannelSpec("gaussian-v10", "gaussian", "variance", 10.0, "medium"),
    ChannelSpec(
        "salt-and-pepper-d003",
        "salt_and_pepper",
        "density",
        0.03,
        "medium",
    ),
)
HARD_CHANNELS = {
    "jpeg": ChannelSpec("jpeg-q50", "jpeg", "quality", 50, "hard"),
    "gaussian": ChannelSpec(
        "gaussian-v15",
        "gaussian",
        "variance",
        15.0,
        "hard",
    ),
    "salt_and_pepper": ChannelSpec(
        "salt-and-pepper-d005",
        "salt_and_pepper",
        "density",
        0.05,
        "hard",
    ),
}


def numerical_source_fingerprint() -> str:
    """Hash numerical source while excluding orchestration-only modules."""

    package = Path(__file__).resolve().parents[1]
    excluded = {
        "__init__.py",
        "cli.py",
        "runtime.py",
        "runtime_gate_contract.py",
        "digital_ad/research_runtime.py",
        "digital_ad/runtime_gate.py",
        "digital_ad/runtime_probe.py",
    }
    records = [
        {
            "path": path.relative_to(package).as_posix(),
            "sha256": sha256_file(path),
        }
        for path in sorted(package.rglob("*.py"))
        if path.relative_to(package).as_posix() not in excluded
    ]
    return sha256_json({"schema": 1, "files": records})


def _task_implementation_fingerprints(
    numerical_fingerprint: str,
) -> tuple[str, str]:
    embedding = sha256_json(
        {
            "schema": EMBEDDING_OBJECT_SCHEMA,
            "numerical_source_fingerprint": numerical_fingerprint,
            "producer_source": inspect.getsource(_produce_embedding),
            "config_loader_source": inspect.getsource(_load_config),
        }
    )
    evaluation = sha256_json(
        {
            "schema": EVALUATION_OBJECT_SCHEMA,
            "numerical_source_fingerprint": numerical_fingerprint,
            "producer_source": inspect.getsource(_produce_evaluation),
            "config_loader_source": inspect.getsource(_load_config),
            "stability_loader_source": inspect.getsource(_load_stability),
            "channel_source": inspect.getsource(_apply_channel),
            "realization_source": inspect.getsource(channel_realization),
        }
    )
    return embedding, evaluation


def channel_realization(pair_id: str, channel: ChannelSpec) -> tuple[str, int]:
    """Derive one method-independent realization for a pair and channel."""

    material = (
        PROTOCOL_VERSION.encode("ascii")
        + b"\0"
        + pair_id.encode("utf-8")
        + b"\0"
        + channel.channel_id.encode("ascii")
    )
    digest = hashlib.sha256(material).digest()
    return digest.hex()[:24], int.from_bytes(digest[:16], "big")


def _apply_channel(
    image: np.ndarray,
    channel: ChannelSpec,
    *,
    realization_seed: int,
) -> np.ndarray:
    if channel.family == "clean":
        return image.copy()
    if channel.family == "jpeg":
        return jpeg(image, quality=int(channel.value))
    if channel.family == "gaussian":
        return gaussian(
            image,
            variance=float(channel.value),
            seed=realization_seed,
        )
    if channel.family == "salt_and_pepper":
        return salt_and_pepper(
            image,
            density=float(channel.value),
            seed=realization_seed,
        )
    raise ValueError(f"unsupported research channel family: {channel.family}")


def _load_config(payload: Mapping[str, Any]) -> DigitalADConfig:
    return DigitalADConfig(**dict(payload)).validate()


def _load_stability(
    path: str | None,
    *,
    config: DigitalADConfig,
) -> Mapping[str, float] | None:
    if path is None:
        return None
    return load_stability_profile(path, config=config).values


def _pair_record(pair: ImagePair, config: DigitalADConfig) -> dict[str, object]:
    if pair.seed is not None:
        raise ValueError(
            f"core pair {pair.pair_id!r} declares a seed; seed sweeps are forbidden"
        )
    if pair.split != "traceability_core":
        raise ValueError(
            f"core pair {pair.pair_id!r} must use split='traceability_core'"
        )
    missing = [
        key for key in REQUIRED_MANIFEST_METADATA if not pair.metadata.get(key, "").strip()
    ]
    if missing:
        raise ValueError(
            f"core pair {pair.pair_id!r} is missing traceability fields: {missing}"
        )
    cover_file_hash = sha256_file(pair.cover)
    secret_file_hash = sha256_file(pair.secret)
    if cover_file_hash != pair.metadata["cover_sha256"].lower():
        raise ValueError(f"cover hash mismatch for pair {pair.pair_id!r}")
    if secret_file_hash != pair.metadata["secret_sha256"].lower():
        raise ValueError(f"secret hash mismatch for pair {pair.pair_id!r}")
    cover = load_uint8_grayscale(pair.cover, size=config.cover_size)
    secret = load_uint8_grayscale(pair.secret, size=config.secret_size)
    cover_array_hash = sha256_array(cover)
    secret_array_hash = sha256_array(secret)
    if cover_array_hash != pair.metadata["cover_array_sha256"].lower():
        raise ValueError(f"decoded cover hash mismatch for pair {pair.pair_id!r}")
    if secret_array_hash != pair.metadata["secret_array_sha256"].lower():
        raise ValueError(f"decoded secret hash mismatch for pair {pair.pair_id!r}")
    return {
        "pair_id": pair.pair_id,
        "split": pair.split,
        "cover": str(pair.cover),
        "secret": str(pair.secret),
        "cover_source_id": pair.metadata["cover_source_id"],
        "secret_source_id": pair.metadata["secret_source_id"],
        "cover_rights": pair.metadata["cover_rights"],
        "secret_rights": pair.metadata["secret_rights"],
        "cover_file_sha256": cover_file_hash,
        "secret_file_sha256": secret_file_hash,
        "cover_array_sha256": cover_array_hash,
        "secret_array_sha256": secret_array_hash,
    }


def _ensure_transform_boundary(
    config: DigitalADConfig,
    *,
    engineering_control: bool,
) -> str:
    if config.transform_profile == "haar_orthogonal_control_v1":
        if not engineering_control:
            raise ValueError(
                "Haar is an engineering control; pass --engineering-control "
                "only for infrastructure validation, never final PDFB evidence"
            )
        return "engineering_control_haar"
    if config.transform_profile == "proxy_directional_lp_v1":
        if not engineering_control:
            raise ValueError(
                "the directional proxy is not approved PDFB evidence; "
                "--engineering-control is required"
            )
        return "engineering_control_directional_proxy"
    if config.transform_profile == OCTAVE_PDFB_PROFILE:
        if engineering_control:
            raise ValueError(
                "the explicit Octave PDFB profile is a final research "
                "interpretation; do not label it as an engineering control"
            )
        return (
            "final_pdfb_range_multiscale_coordinates_not_author_equivalent"
        )
    raise ValueError(
        "the configured transform is not supported by the current adapter"
    )


def prepare_research_plan(
    manifest_path: str | Path,
    config: DigitalADConfig,
    *,
    stability_path: str | Path,
    engineering_control: bool = False,
) -> dict[str, Any]:
    """Validate the four-pair lock and construct the immutable 64/88 plan."""

    cfg = config.validate()
    scientific_status = _ensure_transform_boundary(
        cfg,
        engineering_control=engineering_control,
    )
    manifest = Path(manifest_path).resolve()
    stability = Path(stability_path).resolve()
    if not stability.is_file():
        raise FileNotFoundError(f"stability profile not found: {stability}")
    load_stability_profile(stability, config=cfg)
    pairs = read_manifest(manifest)
    if len(pairs) != CORE_PAIR_COUNT:
        raise ValueError(
            f"lean core manifest must contain exactly {CORE_PAIR_COUNT} pairs"
        )
    if len({pair.pair_id for pair in pairs}) != CORE_PAIR_COUNT:
        raise ValueError("lean core manifest contains duplicate pair_id values")
    pair_records = [_pair_record(pair, cfg) for pair in pairs]
    if len({item["cover_array_sha256"] for item in pair_records}) != CORE_PAIR_COUNT:
        raise ValueError("lean core manifest reuses a decoded cover image")
    if len({item["secret_array_sha256"] for item in pair_records}) != CORE_PAIR_COUNT:
        raise ValueError("lean core manifest reuses a decoded secret image")
    code_fingerprint = numerical_source_fingerprint()
    (
        embedding_implementation_fingerprint,
        evaluation_implementation_fingerprint,
    ) = _task_implementation_fingerprints(code_fingerprint)
    config_payload = cfg.to_dict()
    config_hash = sha256_json(config_payload)
    stability_hash = sha256_file(stability)
    transform_fingerprint = make_transform_adapter(cfg).fingerprint()
    plan_material = {
        "schema": 1,
        "protocol_version": PROTOCOL_VERSION,
        "runtime_implementation": RUNTIME_IMPLEMENTATION,
        "scientific_status": scientific_status,
        "manifest_sha256": sha256_file(manifest),
        "pairs": pair_records,
        "config_sha256": config_hash,
        "stability_sha256": stability_hash,
        "source_fingerprint": code_fingerprint,
        "embedding_implementation_fingerprint": (
            embedding_implementation_fingerprint
        ),
        "evaluation_implementation_fingerprint": (
            evaluation_implementation_fingerprint
        ),
        "transform_fingerprint": transform_fingerprint,
        "methods": [method.name for method in CORE_METHODS],
        "core_channels": [CLEAN.to_dict(), *[item.to_dict() for item in CORE_CHANNELS]],
        "conditional_channels": [
            HARD_CHANNELS[key].to_dict() for key in sorted(HARD_CHANNELS)
        ],
        "budget": {
            "embeddings": MANDATORY_EMBEDDINGS,
            "mandatory_rows": MANDATORY_ROWS,
            "max_conditional_rows": MAX_CONDITIONAL_ROWS,
            "absolute_max_rows": ABSOLUTE_MAX_ROWS,
        },
    }
    run_id = sha256_json(plan_material)[:20]
    embeddings: list[dict[str, Any]] = []
    core_evaluations: list[dict[str, Any]] = []
    conditional_evaluations: list[dict[str, Any]] = []
    for pair in pair_records:
        for method in CORE_METHODS:
            embedding_material = {
                "schema": 1,
                "object_schema": EMBEDDING_OBJECT_SCHEMA,
                "kind": "digital_embedding",
                "protocol_version": PROTOCOL_VERSION,
                "source_fingerprint": code_fingerprint,
                "implementation_fingerprint": (
                    embedding_implementation_fingerprint
                ),
                "config_sha256": config_hash,
                "stability_sha256": stability_hash,
                "transform_fingerprint": transform_fingerprint,
                "pair_id": pair["pair_id"],
                "cover_array_sha256": pair["cover_array_sha256"],
                "secret_array_sha256": pair["secret_array_sha256"],
                "method": method.name,
            }
            embedding_id = content_object_id(
                "digital_embedding",
                embedding_material,
            )
            embedding_payload = {
                "pair": pair,
                "method": method.name,
                "config": config_payload,
                "stability_path": str(stability),
                "stability_sha256": stability_hash,
                "source_fingerprint": code_fingerprint,
                "implementation_fingerprint": (
                    embedding_implementation_fingerprint
                ),
                "transform_fingerprint": transform_fingerprint,
                "run_id": run_id,
            }
            embeddings.append(
                {
                    "object_id": embedding_id,
                    "kind": "digital_embedding",
                    "label": f"{pair['pair_id']}:{method.name}:embed+clean",
                    "payload": embedding_payload,
                }
            )
            for channel in CORE_CHANNELS:
                realization_id, realization_seed = channel_realization(
                    str(pair["pair_id"]),
                    channel,
                )
                evaluation_material = {
                    "schema": 1,
                    "object_schema": EVALUATION_OBJECT_SCHEMA,
                    "kind": "digital_channel_evaluation",
                    "protocol_version": PROTOCOL_VERSION,
                    "source_fingerprint": code_fingerprint,
                    "implementation_fingerprint": (
                        evaluation_implementation_fingerprint
                    ),
                    "embedding_object_id": embedding_id,
                    "channel": channel.to_dict(),
                    "realization_id": realization_id,
                }
                evaluation_id = content_object_id(
                    "digital_channel_evaluation",
                    evaluation_material,
                )
                core_evaluations.append(
                    {
                        "object_id": evaluation_id,
                        "kind": "digital_channel_evaluation",
                        "label": (
                            f"{pair['pair_id']}:{method.name}:{channel.channel_id}"
                        ),
                        "payload": {
                            "pair": pair,
                            "method": method.name,
                            "config": config_payload,
                            "stability_path": str(stability),
                            "stability_sha256": stability_hash,
                            "source_fingerprint": code_fingerprint,
                            "implementation_fingerprint": (
                                evaluation_implementation_fingerprint
                            ),
                            "transform_fingerprint": transform_fingerprint,
                            "embedding_object_id": embedding_id,
                            "channel": channel.to_dict(),
                            "realization_id": realization_id,
                            "realization_seed": realization_seed,
                            "run_id": run_id,
                        },
                    }
                )
            if method not in {MethodId.C0_FIXED, MethodId.C3_A_D}:
                continue
            for family in sorted(HARD_CHANNELS):
                channel = HARD_CHANNELS[family]
                realization_id, realization_seed = channel_realization(
                    str(pair["pair_id"]),
                    channel,
                )
                evaluation_material = {
                    "schema": 1,
                    "object_schema": EVALUATION_OBJECT_SCHEMA,
                    "kind": "digital_channel_evaluation",
                    "protocol_version": PROTOCOL_VERSION,
                    "source_fingerprint": code_fingerprint,
                    "implementation_fingerprint": (
                        evaluation_implementation_fingerprint
                    ),
                    "embedding_object_id": embedding_id,
                    "channel": channel.to_dict(),
                    "realization_id": realization_id,
                }
                evaluation_id = content_object_id(
                    "digital_channel_evaluation",
                    evaluation_material,
                )
                conditional_evaluations.append(
                    {
                        "object_id": evaluation_id,
                        "kind": "digital_channel_evaluation",
                        "label": (
                            f"{pair['pair_id']}:{method.name}:{channel.channel_id}"
                        ),
                        "payload": {
                            "pair": pair,
                            "method": method.name,
                            "config": config_payload,
                            "stability_path": str(stability),
                            "stability_sha256": stability_hash,
                            "source_fingerprint": code_fingerprint,
                            "implementation_fingerprint": (
                                evaluation_implementation_fingerprint
                            ),
                            "transform_fingerprint": transform_fingerprint,
                            "embedding_object_id": embedding_id,
                            "channel": channel.to_dict(),
                            "realization_id": realization_id,
                            "realization_seed": realization_seed,
                            "run_id": run_id,
                        },
                    }
                )
    if len(embeddings) != MANDATORY_EMBEDDINGS:
        raise AssertionError("research plan did not create exactly 16 embeddings")
    mandatory_rows = len(embeddings) + len(core_evaluations)
    if mandatory_rows != MANDATORY_ROWS:
        raise AssertionError("research plan did not create exactly 64 core rows")
    if len(conditional_evaluations) != MAX_CONDITIONAL_ROWS:
        raise AssertionError("research plan did not create exactly 24 hard rows")
    if mandatory_rows + len(conditional_evaluations) != ABSOLUTE_MAX_ROWS:
        raise AssertionError("research plan exceeds or misses the 88-row cap")
    return {
        "schema": 1,
        "run_id": run_id,
        "created_at": utc_now(),
        "material": plan_material,
        "manifest_path": str(manifest),
        "stability_path": str(stability),
        "embeddings": embeddings,
        "core_evaluations": core_evaluations,
        "conditional_evaluations": conditional_evaluations,
    }


def _task_from_dict(payload: Mapping[str, Any]) -> DurableTask:
    return DurableTask(
        object_id=str(payload["object_id"]),
        kind=str(payload["kind"]),
        label=str(payload["label"]),
        payload=dict(payload["payload"]),
    )


def _produce_embedding(task: Mapping[str, Any], destination: Path) -> dict[str, Any]:
    payload = dict(task["payload"])
    pair = dict(payload["pair"])
    config = _load_config(payload["config"])
    actual_transform_fingerprint = make_transform_adapter(config).fingerprint()
    if actual_transform_fingerprint != payload["transform_fingerprint"]:
        raise RuntimeError(
            "runtime transform fingerprint differs from the locked research plan"
        )
    stability = (
        None
        if payload.get("stability_path") is None
        else load_stability_profile(
            payload["stability_path"],
            config=config,
        )
    )
    cover = load_uint8_grayscale(pair["cover"], size=config.cover_size)
    secret = load_uint8_grayscale(pair["secret"], size=config.secret_size)
    result = run_digital_experiment(
        cover,
        secret,
        pair_id=str(pair["pair_id"]),
        method=str(payload["method"]),
        config=config,
        output_dir=destination / "payload",
        stability_profile=stability,
        attack_profile="none",
    )
    report = {
        "schema": 1,
        "kind": "digital_embedding",
        "run_id": payload["run_id"],
        "pair_id": pair["pair_id"],
        "method": payload["method"],
        "success": result["success"],
        "failure_reason": result["failure_reason"],
        "embedding_object_id": task["object_id"],
        "source_fingerprint": payload["source_fingerprint"],
        "implementation_fingerprint": payload["implementation_fingerprint"],
        "transform_fingerprint": payload["transform_fingerprint"],
    }
    atomic_write_json(destination / "result.json", report)
    return report


def _produce_evaluation(task: Mapping[str, Any], destination: Path) -> dict[str, Any]:
    payload = dict(task["payload"])
    pair = dict(payload["pair"])
    config = _load_config(payload["config"])
    actual_transform_fingerprint = make_transform_adapter(config).fingerprint()
    if actual_transform_fingerprint != payload["transform_fingerprint"]:
        raise RuntimeError(
            "runtime transform fingerprint differs from the locked research plan"
        )
    method = MethodId.parse(str(payload["method"]))
    channel = ChannelSpec(**dict(payload["channel"]))
    store = ContentStore(payload["_cache_dir"])
    embedding_id = str(payload["embedding_object_id"])
    verification = store.verify(embedding_id, deep=True)
    if not verification.valid:
        raise RuntimeError(
            f"embedding object {embedding_id} is invalid: {verification.reason}"
        )
    embedding_payload = verification.path / "payload"
    cover = load_uint8_grayscale(
        embedding_payload / "images" / "cover.png",
        size=config.cover_size,
    )
    secret = load_uint8_grayscale(
        embedding_payload / "images" / "secret.png",
        size=config.secret_size,
    )
    stego = load_uint8_grayscale(
        embedding_payload / "images" / "stego.png",
        size=config.cover_size,
    )
    stability = _load_stability(payload.get("stability_path"), config=config)
    attack_started = time.perf_counter()
    attacked = _apply_channel(
        stego,
        channel,
        realization_seed=int(payload["realization_seed"]),
    )
    attack_seconds = time.perf_counter() - attack_started
    encoded = encode_bitstream(
        secret,
        pair_id=str(pair["pair_id"]),
        method=method,
        config=config,
    )
    extraction_started = time.perf_counter()
    extraction = extract(
        attacked,
        cover,
        pair_id=str(pair["pair_id"]),
        method=method,
        config=config,
        stability_profile=stability,
        expected_bits=encoded.bits,
    )
    extraction_seconds = time.perf_counter() - extraction_started
    base_original, detail_original = split_secret(secret)
    base_reference = nibbles_to_bytes(base_original)
    detail_reference = nibbles_to_bytes(detail_original)
    metrics = _decode_metrics(
        extraction,
        base_reference=base_reference,
        detail_reference=detail_reference,
    )
    if extraction.decode.recovered_secret is not None:
        metrics.update(
            {
                f"secret_{name}": value
                for name, value in metric_bundle(
                    secret,
                    extraction.decode.recovered_secret,
                ).items()
            }
        )
    failures = [asdict(item) for item in extraction.decode.failures]
    images = destination / "images"
    save_uint8_grayscale(images / "attacked.png", attacked)
    if extraction.decode.recovered_secret is not None:
        save_uint8_grayscale(
            images / "recovered.png",
            extraction.decode.recovered_secret,
        )
    packed = np.packbits(extraction.extracted_bits).tobytes()
    atomic_write_bytes(destination / "extracted_bits.bin", packed)
    extracted_manifest = {
        "schema": 1,
        "bit_count": int(extraction.extracted_bits.size),
        "byte_count": len(packed),
        "sha256": hashlib.sha256(packed).hexdigest(),
    }
    atomic_write_json(
        destination / "extracted_bits_manifest.json",
        extracted_manifest,
    )
    attacked_hash = sha256_array(attacked)
    record = {
        "schema": 1,
        "kind": "digital_channel_evaluation",
        "run_id": payload["run_id"],
        "protocol_version": PROTOCOL_VERSION,
        "pair_id": pair["pair_id"],
        "split": pair["split"],
        "method": method.name,
        "channel": channel.to_dict(),
        "realization_id": payload["realization_id"],
        "embedding_object_id": embedding_id,
        "evaluation_object_id": task["object_id"],
        "decode_success": extraction.decode.success,
        "header_valid": extraction.decode.header_valid,
        "payload_crc_valid": extraction.decode.payload_crc_valid,
        "metrics": {key: _safe_number(value) for key, value in metrics.items()},
        "failures": failures,
        "attack_seconds": attack_seconds,
        "extraction_seconds": extraction_seconds,
        "extraction_breakdown": dict(extraction.timings),
        "attacked_sha256": attacked_hash,
        "stego_sha256": sha256_array(stego),
        "cover_sha256": sha256_array(cover),
        "secret_sha256": sha256_array(secret),
        "source_fingerprint": payload["source_fingerprint"],
        "implementation_fingerprint": payload["implementation_fingerprint"],
        "transform_fingerprint": payload["transform_fingerprint"],
        "environment": environment_snapshot(),
        "git": git_state(),
    }
    atomic_write_json(destination / "evaluation.json", record)
    atomic_write_json(destination / "failures.json", failures)
    return {
        "pair_id": pair["pair_id"],
        "method": method.name,
        "channel_id": channel.channel_id,
        "decode_success": extraction.decode.success,
        "evaluation_object_id": task["object_id"],
    }


def _peak_rss_mb() -> float | None:
    if resource is None:
        return None
    try:
        value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (AttributeError, ValueError):
        return None
    if os.uname().sysname == "Darwin":
        return value / 1024**2
    return value / 1024


def worker_execute_task(
    task: Mapping[str, Any],
    cache_dir: str,
) -> Mapping[str, Any]:
    """Spawn-safe worker entrypoint used by both research and gate probes."""

    store = ContentStore(cache_dir)
    object_id = str(task["object_id"])
    existing = store.verify(object_id, deep=True)
    if existing.valid:
        return {
            "status": "cached",
            "object_id": object_id,
            "path": str(existing.path),
            "byte_count": existing.byte_count,
        }
    attempt = store.begin_attempt(object_id)
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        payload = dict(task["payload"])
        payload["_cache_dir"] = cache_dir
        executable_task = {**dict(task), "payload": payload}
        with (attempt / "stdout.log").open(
            "w",
            encoding="utf-8",
        ) as stdout_stream, (attempt / "stderr.log").open(
            "w",
            encoding="utf-8",
        ) as stderr_stream, redirect_stdout(stdout_stream), redirect_stderr(
            stderr_stream
        ):
            if task["kind"] == "digital_embedding":
                result = _produce_embedding(executable_task, attempt)
            elif task["kind"] == "digital_channel_evaluation":
                result = _produce_evaluation(executable_task, attempt)
            elif task["kind"] == "runtime_probe":
                delay = float(payload.get("delay_seconds", 0.1))
                time.sleep(delay)
                result = {
                    "schema": 1,
                    "probe_index": int(payload["probe_index"]),
                    "probe_value": str(payload["probe_value"]),
                }
                atomic_write_json(attempt / "probe.json", result)
            else:
                raise ValueError(f"unknown durable task kind: {task['kind']}")
        resource_record = {
            "schema": 1,
            "wall_seconds": time.perf_counter() - started_wall,
            "cpu_seconds": time.process_time() - started_cpu,
            "worker_peak_rss_mb": _peak_rss_mb(),
            "pid": os.getpid(),
            "thread_limits": {
                name: os.environ.get(name)
                for name in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                )
            },
        }
        atomic_write_json(attempt / "resource.json", resource_record)
        atomic_write_json(attempt / "task.json", task)
        atomic_write_json(attempt / "producer_result.json", result)
        verification = store.commit_attempt(
            object_id,
            attempt,
            task_material_sha256=task_material_sha256(task),
        )
        return {
            "status": "completed",
            "object_id": object_id,
            "path": str(verification.path),
            "byte_count": verification.byte_count,
            "resource": resource_record,
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
            "object_id": object_id,
            "attempt_path": str(attempt),
            "error_type": type(error).__name__,
            "error": str(error),
        }


def _number(payload: Mapping[str, Any], key: str) -> float | str:
    value = payload.get(key, "")
    if isinstance(value, (int, float)):
        return value
    return ""


def _embedding_evaluation(
    *,
    plan: Mapping[str, Any],
    task: Mapping[str, Any],
    store: ContentStore,
) -> dict[str, Any]:
    object_id = str(task["object_id"])
    verification = store.verify(object_id, deep=True)
    if not verification.valid:
        raise RuntimeError(
            f"missing embedding result {object_id}: {verification.reason}"
        )
    root = verification.path
    payload = root / "payload"
    metrics = read_json(payload / "metrics.json")
    runtime = read_json(payload / "runtime.json")
    capacity = read_json(payload / "capacity_report.json")
    status = read_json(payload / "run_status.json")
    resource_record = read_json(root / "resource.json")
    task_payload = dict(task["payload"])
    pair = dict(task_payload["pair"])
    clean_metrics = dict(metrics["clean_decode"])
    cover_metrics = dict(metrics["cover_stego"])
    secret_metrics = dict(metrics.get("secret_recovery", {}))
    lambda_trials = runtime.get("lambda_trials")
    config = read_json(payload / "config.json")
    lambda_value = runtime.get("selected_lambda", "")
    result = read_json(root / "result.json")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": plan["run_id"],
        "pair_id": pair["pair_id"],
        "split": pair["split"],
        "method": task_payload["method"],
        "channel_id": CLEAN.channel_id,
        "family": CLEAN.family,
        "parameter": "",
        "attack_value": "",
        "severity": CLEAN.severity,
        "realization_id": "",
        "status": status["status"],
        "decode_success": clean_metrics.get("decode_success", 0),
        "header_valid": clean_metrics.get("header_valid", 0),
        "payload_crc_valid": clean_metrics.get("payload_crc_valid", 0),
        "raw_ber": _number(clean_metrics, "raw_ber"),
        "base_ber": _number(clean_metrics, "base_ber"),
        "detail_ber": _number(clean_metrics, "detail_ber"),
        "effective_unrecovered_bit_rate": _number(
            clean_metrics,
            "effective_unrecovered_bit_rate",
        ),
        "secret_mse": _number(secret_metrics, "mse"),
        "secret_psnr": _number(secret_metrics, "psnr"),
        "secret_ssim": _number(secret_metrics, "ssim"),
        "cover_stego_mse": _number(cover_metrics, "mse"),
        "cover_stego_psnr": _number(cover_metrics, "psnr"),
        "cover_stego_ssim": _number(cover_metrics, "ssim"),
        "protected_payload_bits": capacity["required_slots"],
        "selected_lambda": lambda_value,
        "embedding_seconds": runtime["clean_pipeline_seconds"],
        "attack_seconds": 0.0,
        "extraction_seconds": runtime["clean_extraction_breakdown"].get(
            "extraction_total_seconds",
            "",
        ),
        "worker_peak_rss_mb": resource_record.get("worker_peak_rss_mb", ""),
        "embedding_object_id": object_id,
        "evaluation_object_id": object_id,
        "attacked_sha256": read_json(payload / "provenance.json")[
            "stego_array_sha256"
        ],
        "failure_count": len(read_json(payload / "failures.json")["clean"]),
        "_result_success": result["success"],
        "_config_master_seed": config["master_seed"],
        "_lambda_trials": lambda_trials,
    }


def _attack_evaluation(
    *,
    plan: Mapping[str, Any],
    task: Mapping[str, Any],
    store: ContentStore,
) -> dict[str, Any]:
    object_id = str(task["object_id"])
    verification = store.verify(object_id, deep=True)
    if not verification.valid:
        raise RuntimeError(
            f"missing evaluation result {object_id}: {verification.reason}"
        )
    record = read_json(verification.path / "evaluation.json")
    resource_record = read_json(verification.path / "resource.json")
    metrics = dict(record["metrics"])
    channel = dict(record["channel"])
    embedding_verification = store.verify(
        str(record["embedding_object_id"]),
        deep=True,
    )
    if not embedding_verification.valid:
        raise RuntimeError("evaluation references an invalid embedding object")
    embedding_payload = embedding_verification.path / "payload"
    cover_metrics = read_json(embedding_payload / "metrics.json")["cover_stego"]
    capacity = read_json(embedding_payload / "capacity_report.json")
    embedding_runtime = read_json(embedding_payload / "runtime.json")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": plan["run_id"],
        "pair_id": record["pair_id"],
        "split": record["split"],
        "method": record["method"],
        "channel_id": channel["channel_id"],
        "family": channel["family"],
        "parameter": channel["parameter"],
        "attack_value": channel["value"],
        "severity": channel["severity"],
        "realization_id": record["realization_id"],
        "status": "ok" if record["decode_success"] else "decode_failure",
        "decode_success": record["decode_success"],
        "header_valid": record["header_valid"],
        "payload_crc_valid": record["payload_crc_valid"],
        "raw_ber": _number(metrics, "raw_ber"),
        "base_ber": _number(metrics, "base_ber"),
        "detail_ber": _number(metrics, "detail_ber"),
        "effective_unrecovered_bit_rate": _number(
            metrics,
            "effective_unrecovered_bit_rate",
        ),
        "secret_mse": _number(metrics, "secret_mse"),
        "secret_psnr": _number(metrics, "secret_psnr"),
        "secret_ssim": _number(metrics, "secret_ssim"),
        "cover_stego_mse": _number(cover_metrics, "mse"),
        "cover_stego_psnr": _number(cover_metrics, "psnr"),
        "cover_stego_ssim": _number(cover_metrics, "ssim"),
        "protected_payload_bits": capacity["required_slots"],
        "selected_lambda": "",
        "embedding_seconds": embedding_runtime["clean_pipeline_seconds"],
        "attack_seconds": record["attack_seconds"],
        "extraction_seconds": record["extraction_seconds"],
        "worker_peak_rss_mb": resource_record.get("worker_peak_rss_mb", ""),
        "embedding_object_id": record["embedding_object_id"],
        "evaluation_object_id": object_id,
        "attacked_sha256": record["attacked_sha256"],
        "failure_count": len(record["failures"]),
    }


def _public_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record.get(key, "") for key in EVALUATION_FIELDS}


def collect_evaluations(
    plan: Mapping[str, Any],
    *,
    cache_dir: str | Path,
    conditional_families: Iterable[str] = (),
) -> list[dict[str, Any]]:
    store = ContentStore(cache_dir)
    rows = [
        _embedding_evaluation(plan=plan, task=task, store=store)
        for task in plan["embeddings"]
    ]
    rows.extend(
        _attack_evaluation(plan=plan, task=task, store=store)
        for task in plan["core_evaluations"]
    )
    selected = set(conditional_families)
    rows.extend(
        _attack_evaluation(plan=plan, task=task, store=store)
        for task in plan["conditional_evaluations"]
        if task["payload"]["channel"]["family"] in selected
    )
    return rows


def decide_hard_checks(core_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply the predeclared, conservative hard-point trigger."""

    clean = [row for row in core_rows if row["channel_id"] == "clean"]
    clean_passed = len(clean) == 16 and all(
        bool(row["decode_success"]) for row in clean
    )
    decisions: dict[str, Any] = {}
    for family in sorted(HARD_CHANNELS):
        relevant = [
            row
            for row in core_rows
            if row["family"] == family
            and row["method"] in {"C0_FIXED", "C3_A_D"}
        ]
        by_pair: dict[str, dict[str, float]] = {}
        for row in relevant:
            value = row["effective_unrecovered_bit_rate"]
            if not isinstance(value, (int, float)):
                continue
            by_pair.setdefault(str(row["pair_id"]), {})[
                str(row["method"])
            ] = float(value)
        complete = len(by_pair) == 4 and all(
            set(methods) == {"C0_FIXED", "C3_A_D"}
            for methods in by_pair.values()
        )
        values = [
            value for methods in by_pair.values() for value in methods.values()
        ]
        saturated_zero = complete and all(abs(value) <= 1e-12 for value in values)
        saturated_one = complete and all(
            abs(value - 1.0) <= 1e-12 for value in values
        )
        improvements = {
            pair_id: methods["C0_FIXED"] - methods["C3_A_D"]
            for pair_id, methods in by_pair.items()
            if set(methods) == {"C0_FIXED", "C3_A_D"}
        }
        improvement_count = sum(
            value >= 0.01 for value in improvements.values()
        )
        triggered = bool(
            clean_passed
            and complete
            and (saturated_zero or saturated_one or improvement_count >= 3)
        )
        if not clean_passed:
            status = "blocked_by_clean_gate"
        elif not complete:
            status = "blocked_by_incomplete_core"
        else:
            status = "triggered" if triggered else "not_triggered"
        decisions[family] = {
            "status": status,
            "triggered": triggered,
            "hard_channel": HARD_CHANNELS[family].to_dict(),
            "criteria": {
                "strict_saturation_at_zero": saturated_zero,
                "strict_saturation_at_one": saturated_one,
                "c0_minus_c3_at_least_0_01_count": improvement_count,
            },
            "pair_improvements": improvements,
        }
    return {
        "schema": 1,
        "protocol_version": PROTOCOL_VERSION,
        "clean_gate_passed": clean_passed,
        "families": decisions,
        "triggered_families": [
            family
            for family, decision in decisions.items()
            if decision["triggered"]
        ],
    }


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _summary_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        value = row["effective_unrecovered_bit_rate"]
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            groups.setdefault(
                (str(row["channel_id"]), str(row["method"])),
                [],
            ).append(float(value))
    summaries: list[dict[str, Any]] = []
    for (channel, method), values in sorted(groups.items()):
        summaries.append(
            {
                "channel_id": channel,
                "method": method,
                "count": len(values),
                "mean_eur": statistics.fmean(values),
                "median_eur": statistics.median(values),
                "minimum_eur": min(values),
                "maximum_eur": max(values),
            }
        )
    return summaries


def _contrast_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, float]] = {}
    for row in rows:
        value = row["effective_unrecovered_bit_rate"]
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            continue
        grouped.setdefault(
            (str(row["pair_id"]), str(row["channel_id"])),
            {},
        )[str(row["method"])] = float(value)
    output: list[dict[str, Any]] = []
    required = {"C0_FIXED", "C1_A", "C2_D", "C3_A_D"}
    for (pair_id, channel_id), values in sorted(grouped.items()):
        if set(values) != required:
            continue
        c0 = values["C0_FIXED"]
        c1 = values["C1_A"]
        c2 = values["C2_D"]
        c3 = values["C3_A_D"]
        output.append(
            {
                "pair_id": pair_id,
                "channel_id": channel_id,
                "a_main_effect": ((c0 - c1) + (c2 - c3)) / 2.0,
                "d_main_effect": ((c0 - c2) + (c1 - c3)) / 2.0,
                "a_by_d_interaction": c1 + c2 - c0 - c3,
                "c0_minus_c3": c0 - c3,
                "c3_favored": c3 < c0,
            }
        )
    return output


def _write_figure(
    figure: Any,
    destination: Path,
    *,
    format_name: str,
    dpi: int | None = None,
) -> None:
    temporary = destination.with_name(
        f".{destination.stem}.tmp-{os.getpid()}.{format_name}"
    )
    metadata = (
        {
            "Creator": "ctsteg durable runtime",
            "CreationDate": None,
            "ModDate": None,
        }
        if format_name == "pdf"
        else {"Software": "ctsteg durable runtime"}
    )
    figure.savefig(
        temporary,
        format=format_name,
        dpi=dpi,
        bbox_inches="tight",
        metadata=metadata,
    )
    os.replace(temporary, destination)


def _write_figures(
    rows: Sequence[Mapping[str, Any]],
    contrasts: Sequence[Mapping[str, Any]],
    destination: Path,
) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    figures = destination / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    method_order = [method.name for method in CORE_METHODS]
    observed_channels = {str(row["channel_id"]) for row in rows}
    canonical_channels = [
        CLEAN.channel_id,
        *[channel.channel_id for channel in CORE_CHANNELS],
        *[
            HARD_CHANNELS[family].channel_id
            for family in sorted(HARD_CHANNELS)
        ],
    ]
    channel_order = [
        channel for channel in canonical_channels if channel in observed_channels
    ]
    means: dict[tuple[str, str], float] = {}
    for channel in channel_order:
        for method in method_order:
            values = [
                float(row["effective_unrecovered_bit_rate"])
                for row in rows
                if row["channel_id"] == channel
                and row["method"] == method
                and isinstance(
                    row["effective_unrecovered_bit_rate"],
                    (int, float),
                )
                and math.isfinite(
                    float(row["effective_unrecovered_bit_rate"])
                )
            ]
            means[(channel, method)] = (
                statistics.fmean(values) if values else float("nan")
            )
    positions = np.arange(len(channel_order), dtype=np.float64)
    width = 0.18
    fig, axis = plt.subplots(figsize=(10, 5.5))
    for method_index, method in enumerate(method_order):
        offset = (method_index - 1.5) * width
        axis.bar(
            positions + offset,
            [means[(channel, method)] for channel in channel_order],
            width=width,
            label=method,
        )
    axis.set_xticks(positions)
    axis.set_xticklabels(channel_order, rotation=25, ha="right")
    axis.set_ylabel("Mean effective unrecovered-bit rate (lower is better)")
    axis.set_xlabel("Locked channel condition")
    axis.set_ylim(bottom=0)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(ncol=2, frameon=False)
    axis.set_title("DIGITAL_A_D case-level recovery by method")
    _write_figure(
        fig,
        figures / "mean_eur_by_method.png",
        format_name="png",
        dpi=300,
    )
    _write_figure(
        fig,
        figures / "mean_eur_by_method.pdf",
        format_name="pdf",
    )
    plt.close(fig)

    pair_order = sorted({str(row["pair_id"]) for row in contrasts})
    contrast_channels = [
        channel
        for channel in channel_order
        if any(row["channel_id"] == channel for row in contrasts)
    ]
    matrix = np.full(
        (len(pair_order), len(contrast_channels)),
        np.nan,
        dtype=np.float64,
    )
    lookup = {
        (str(row["pair_id"]), str(row["channel_id"])): float(
            row["c0_minus_c3"]
        )
        for row in contrasts
    }
    for pair_index, pair_id in enumerate(pair_order):
        for channel_index, channel_id in enumerate(contrast_channels):
            if (pair_id, channel_id) in lookup:
                matrix[pair_index, channel_index] = lookup[
                    (pair_id, channel_id)
                ]
    finite = np.abs(matrix[np.isfinite(matrix)])
    limit = max(0.01, float(np.max(finite)) if finite.size else 0.01)
    fig, axis = plt.subplots(
        figsize=(max(7, 1.25 * len(contrast_channels)), 4.8)
    )
    image = axis.imshow(
        matrix,
        cmap="RdBu",
        vmin=-limit,
        vmax=limit,
        aspect="auto",
    )
    axis.set_xticks(np.arange(len(contrast_channels)))
    axis.set_xticklabels(contrast_channels, rotation=25, ha="right")
    axis.set_yticks(np.arange(len(pair_order)))
    axis.set_yticklabels(pair_order)
    axis.set_xlabel("Locked channel condition")
    axis.set_ylabel("Traceability pair")
    axis.set_title("C0 − C3 EUR (positive favors C3)")
    for row_index in range(matrix.shape[0]):
        for column_index in range(matrix.shape[1]):
            value = matrix[row_index, column_index]
            if math.isfinite(float(value)):
                axis.text(
                    column_index,
                    row_index,
                    f"{value:.3f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                )
    fig.colorbar(image, ax=axis, label="C0 − C3 EUR")
    _write_figure(
        fig,
        figures / "c0_minus_c3_heatmap.png",
        format_name="png",
        dpi=300,
    )
    _write_figure(
        fig,
        figures / "c0_minus_c3_heatmap.pdf",
        format_name="pdf",
    )
    plt.close(fig)
    return {
        "mean_eur_png": "reports/figures/mean_eur_by_method.png",
        "mean_eur_pdf": "reports/figures/mean_eur_by_method.pdf",
        "c0_minus_c3_png": "reports/figures/c0_minus_c3_heatmap.png",
        "c0_minus_c3_pdf": "reports/figures/c0_minus_c3_heatmap.pdf",
    }


def _write_parquet(
    rows: Sequence[Mapping[str, Any]],
    destination: Path,
) -> dict[str, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return {
            "status": "not_installed",
            "install": "pip install '.[research]'",
        }
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    table = pa.Table.from_pylist([dict(row) for row in rows])
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, destination)
    return {
        "status": "written",
        "path": destination.name,
        "sha256": sha256_file(destination),
    }


def write_reports(
    run_dir: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    require_parquet: bool,
) -> dict[str, Any]:
    destination = Path(run_dir)
    reports = destination / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    public = [_public_record(row) for row in rows]
    atomic_write_text(
        reports / "evaluations.csv",
        _csv_text(public, EVALUATION_FIELDS),
    )
    atomic_write_text(
        reports / "evaluations.jsonl",
        "".join(
            json.dumps(item, sort_keys=True, allow_nan=False) + "\n"
            for item in public
        ),
    )
    atomic_write_json(reports / "evaluations.json", public)
    summaries = _summary_rows(public)
    summary_fields = (
        "channel_id",
        "method",
        "count",
        "mean_eur",
        "median_eur",
        "minimum_eur",
        "maximum_eur",
    )
    atomic_write_text(
        reports / "summary.csv",
        _csv_text(summaries, summary_fields),
    )
    atomic_write_json(reports / "summary.json", summaries)
    contrasts = _contrast_rows(public)
    contrast_fields = (
        "pair_id",
        "channel_id",
        "a_main_effect",
        "d_main_effect",
        "a_by_d_interaction",
        "c0_minus_c3",
        "c3_favored",
    )
    atomic_write_text(
        reports / "contrasts.csv",
        _csv_text(contrasts, contrast_fields),
    )
    atomic_write_json(reports / "contrasts.json", contrasts)
    figures = _write_figures(public, contrasts, reports)
    parquet = _write_parquet(public, reports / "evaluations.parquet")
    if require_parquet and parquet["status"] != "written":
        raise RuntimeError(
            "Parquet output is required; install the 'research' optional extra"
        )
    report = {
        "schema": 1,
        "evaluation_rows": len(public),
        "files": {
            "csv": "reports/evaluations.csv",
            "json": "reports/evaluations.json",
            "jsonl": "reports/evaluations.jsonl",
            "summary_csv": "reports/summary.csv",
            "summary_json": "reports/summary.json",
            "contrasts_csv": "reports/contrasts.csv",
            "contrasts_json": "reports/contrasts.json",
            **figures,
        },
        "parquet": parquet,
    }
    atomic_write_json(reports / "report_manifest.json", report)
    return report


def _checksum_records(
    run_dir: Path,
    object_paths: Mapping[str, Path],
    attempt_paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or "exports" in path.relative_to(run_dir).parts:
            continue
        if path.name in {"checksums.sha256", "run.lock"}:
            continue
        records.append(
            {
                "archive_path": (
                    Path("experiment") / "run" / path.relative_to(run_dir)
                ).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    for object_id, root in sorted(object_paths.items()):
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            records.append(
                {
                    "archive_path": (
                        Path("experiment")
                        / "objects"
                        / object_id
                        / path.relative_to(root)
                    ).as_posix(),
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    for attempt_id, root in sorted(attempt_paths.items()):
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            records.append(
                {
                    "archive_path": (
                        Path("experiment")
                        / "attempts"
                        / attempt_id
                        / path.relative_to(root)
                    ).as_posix(),
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
            )
    return records


def verify_download_bundle(archive_path: str | Path) -> dict[str, Any]:
    """Verify every member declared by the bundle's checksum manifest."""

    archive = Path(archive_path).resolve()
    checked = 0
    with tarfile.open(archive, "r:gz") as stream:
        checksum_file = stream.extractfile(
            stream.getmember("experiment/run/checksums.sha256")
        )
        if checksum_file is None:
            raise RuntimeError("download bundle checksum file is unreadable")
        for line_number, line in enumerate(
            checksum_file.read().decode("utf-8").splitlines(),
            start=1,
        ):
            try:
                digest, member_name = line.split("  ", 1)
            except ValueError as error:
                raise RuntimeError(
                    f"invalid checksum record at line {line_number}"
                ) from error
            try:
                member = stream.getmember(member_name)
            except KeyError as error:
                raise RuntimeError(
                    f"archive member is missing: {member_name}"
                ) from error
            source = stream.extractfile(member)
            if source is None:
                raise RuntimeError(
                    f"archive member is unreadable: {member_name}"
                )
            actual = hashlib.sha256()
            while chunk := source.read(1024 * 1024):
                actual.update(chunk)
            if actual.hexdigest() != digest:
                raise RuntimeError(
                    f"archive checksum mismatch for {member_name}"
                )
            checked += 1
    return {"checked_files": checked, "status": "passed"}


def create_download_bundle(
    run_dir: str | Path,
    *,
    cache_dir: str | Path,
    object_ids: Iterable[str],
    allow_missing_objects: bool = False,
) -> dict[str, Any]:
    destination = Path(run_dir).resolve()
    store = ContentStore(cache_dir)
    objects: dict[str, Path] = {}
    attempts: dict[str, Path] = {}
    missing: list[str] = []
    requested_ids = sorted(set(object_ids))
    for object_id in requested_ids:
        verification = store.verify(object_id, deep=True)
        if not verification.valid:
            missing.append(object_id)
        else:
            objects[object_id] = verification.path
        attempt_parent = store.attempt_parent(object_id)
        if attempt_parent.is_dir():
            for attempt in sorted(attempt_parent.iterdir()):
                if attempt.is_dir():
                    attempts[f"{object_id}/{attempt.name}"] = attempt
    if missing and not allow_missing_objects:
        raise RuntimeError(
            "cannot package invalid or missing objects: " + ", ".join(missing)
        )
    release_files: dict[str, str] = {}
    for relative in (
        Path("plan.json"),
        Path("runtime_gate.json"),
        Path("trigger_decisions.json"),
    ):
        candidate = destination / relative
        if candidate.is_file():
            release_files[relative.as_posix()] = sha256_file(candidate)
    reports_root = destination / "reports"
    if reports_root.is_dir():
        for candidate in sorted(reports_root.rglob("*")):
            if candidate.is_file():
                release_files[
                    candidate.relative_to(destination).as_posix()
                ] = sha256_file(candidate)
    bundle_material = {
        "schema": 2,
        "bundle_format": "self-verified-tar-gzip-v2",
        "run_id": destination.name,
        "objects": {
            object_id: sha256_file(path / "COMPLETED.json")
            for object_id, path in sorted(objects.items())
        },
        "missing_objects": missing,
        "release_files": release_files,
        "attempts": {
            attempt_id: [
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_file(path),
                    "size": path.stat().st_size,
                }
                for path in sorted(root.rglob("*"))
                if path.is_file()
            ]
            for attempt_id, root in sorted(attempts.items())
        },
    }
    bundle_material_sha256 = sha256_json(bundle_material)
    exports = destination / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    for manifest in sorted(exports.glob("experiment-*.tar.gz.json")):
        try:
            prior = read_json(manifest)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        archive_path = Path(str(prior.get("archive", "")))
        if (
            prior.get("bundle_material_sha256") == bundle_material_sha256
            and archive_path.is_file()
            and sha256_file(archive_path) == prior.get("archive_sha256")
        ):
            try:
                archive_validation = verify_download_bundle(archive_path)
            except (OSError, UnicodeError, tarfile.TarError, RuntimeError):
                continue
            return {
                **prior,
                "archive_validation": archive_validation,
                "reused": True,
            }
    checksums = _checksum_records(destination, objects, attempts)
    checksum_text = "".join(
        f"{record['sha256']}  {record['archive_path']}\n"
        for record in checksums
    )
    atomic_write_text(destination / "checksums.sha256", checksum_text)
    bundle_id = sha256_json(
        {
            "schema": 2,
            "run_id": destination.name,
            "objects": sorted(objects),
            "missing_objects": missing,
            "attempts": sorted(attempts),
            "checksums": checksums,
        }
    )[:16]
    archive = exports / f"experiment-{destination.name}-{bundle_id}.tar.gz"
    temporary = exports / f".{archive.name}.part-{os.getpid()}"
    with tarfile.open(temporary, mode="w:gz", dereference=True) as stream:
        def filter_run(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
            relative = Path(info.name).parts
            if "exports" in relative or relative[-1:] == ("run.lock",):
                return None
            return info

        stream.add(
            destination,
            arcname="experiment/run",
            recursive=True,
            filter=filter_run,
        )
        for object_id, root in sorted(objects.items()):
            stream.add(
                root,
                arcname=f"experiment/objects/{object_id}",
                recursive=True,
            )
        for attempt_id, root in sorted(attempts.items()):
            stream.add(
                root,
                arcname=f"experiment/attempts/{attempt_id}",
                recursive=True,
            )
    archive_validation = verify_download_bundle(temporary)
    os.replace(temporary, archive)
    report = {
        "schema": 2,
        "bundle_format": "self-verified-tar-gzip-v2",
        "bundle_id": bundle_id,
        "bundle_material_sha256": bundle_material_sha256,
        "archive": str(archive),
        "archive_sha256": sha256_file(archive),
        "archive_size": archive.stat().st_size,
        "object_count": len(objects),
        "attempt_count": len(attempts),
        "missing_object_ids": missing,
        "file_count": len(checksums),
        "archive_validation": archive_validation,
        "created_at": utc_now(),
        "reused": False,
    }
    atomic_write_json(exports / f"{archive.name}.json", report)
    return report


def _selected_conditional_tasks(
    plan: Mapping[str, Any],
    families: Iterable[str],
) -> list[DurableTask]:
    selected = set(families)
    unknown = selected - set(HARD_CHANNELS)
    if unknown:
        raise ValueError(f"unknown hard-check families: {sorted(unknown)}")
    return [
        _task_from_dict(task)
        for task in plan["conditional_evaluations"]
        if task["payload"]["channel"]["family"] in selected
    ]


def execute_research_plan(
    plan: Mapping[str, Any],
    *,
    output_root: str | Path,
    cache_dir: str | Path | None = None,
    runtime_gate_report: str | Path,
    workers: int = 0,
    reserve_cpus: int = 4,
    reserve_memory_gib: float = 12.0,
    worker_memory_gib: float = 3.0,
    max_workers: int = 16,
    minimum_free_disk_gib: float = 10.0,
    require_parquet: bool = False,
    package_results: bool = True,
) -> dict[str, Any]:
    """Execute or resume a validated plan and package all referenced objects."""

    if plan["material"]["budget"] != {
        "embeddings": MANDATORY_EMBEDDINGS,
        "mandatory_rows": MANDATORY_ROWS,
        "max_conditional_rows": MAX_CONDITIONAL_ROWS,
        "absolute_max_rows": ABSOLUTE_MAX_ROWS,
    }:
        raise ValueError("research plan budget does not match the locked 64/88 gate")
    transform_profiles = {
        str(task["payload"]["config"]["transform_profile"])
        for task in plan["embeddings"]
    }
    if OCTAVE_PDFB_PROFILE in transform_profiles and workers != 1:
        raise ValueError(
            "the external Octave PDFB backend requires explicit --workers 1"
        )
    runtime_gate = validate_runtime_gate_report(runtime_gate_report)
    root = Path(output_root).resolve()
    cache = (
        (root / "cache").resolve()
        if cache_dir is None
        else Path(cache_dir).resolve()
    )
    if minimum_free_disk_gib < 0:
        raise ValueError("minimum_free_disk_gib must be non-negative")
    root.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    minimum_free_disk_bytes = int(minimum_free_disk_gib * 1024**3)
    storage_filesystems: dict[str, dict[str, int | str | float]] = {}
    for storage_name, storage_path in (
        ("output_root", root),
        ("cache", cache),
    ):
        disk_usage = shutil.disk_usage(storage_path)
        storage_filesystems[storage_name] = {
            "path": str(storage_path),
            "device_id": storage_path.stat().st_dev,
            "total_bytes": disk_usage.total,
            "used_bytes": disk_usage.used,
            "free_bytes": disk_usage.free,
            "minimum_free_disk_gib": minimum_free_disk_gib,
        }
        if disk_usage.free < minimum_free_disk_bytes:
            raise RuntimeError(
                f"{storage_name} filesystem has "
                f"{disk_usage.free / 1024**3:.2f} GiB free; "
                f"{minimum_free_disk_gib:.2f} GiB is required"
            )
    run_dir = root / "runs" / str(plan["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_path = run_dir / "plan.json"
    if plan_path.is_file():
        existing_plan = read_json(plan_path)
        if (
            existing_plan.get("run_id") != plan.get("run_id")
            or existing_plan.get("material") != plan.get("material")
        ):
            raise RuntimeError("existing immutable plan does not match this run")
        plan = existing_plan
    else:
        atomic_write_json(plan_path, plan)
    atomic_write_json(run_dir / "runtime_gate.json", runtime_gate)
    maximum_jobs = max(
        len(plan["embeddings"]),
        len(plan["core_evaluations"]),
        len(plan["conditional_evaluations"]),
    )
    resolved_workers, resource_plan = resolve_worker_count(
        workers,
        job_count=maximum_jobs,
        reserve_cpus=reserve_cpus,
        reserve_memory_gib=reserve_memory_gib,
        worker_memory_gib=worker_memory_gib,
        hard_cap=max_workers,
    )
    resource_plan.update(
        {
            "minimum_free_disk_gib": minimum_free_disk_gib,
            "storage_filesystems": storage_filesystems,
        }
    )
    atomic_write_json(run_dir / "resource_plan.json", resource_plan)
    runtime_context = {
        "schema": 1,
        "run_id": plan["run_id"],
        "output_root": str(root),
        "cache_dir": str(cache),
        "workers": resolved_workers,
    }
    atomic_write_json(run_dir / "runtime_context.json", runtime_context)
    stages: list[dict[str, Any]] = []
    referenced_ids: list[str] = []
    with RunLock(run_dir):
        runner = DurableTaskRunner(
            cache_dir=cache,
            run_dir=run_dir,
            workers=resolved_workers,
        )
        embedding_tasks = [
            _task_from_dict(task) for task in plan["embeddings"]
        ]
        embedding_stage = runner.run(
            embedding_tasks,
            stage="01_embeddings_and_clean",
            worker=worker_execute_task,
        )
        stages.append(embedding_stage)
        referenced_ids.extend(task.object_id for task in embedding_tasks)
        if embedding_stage["failed"]:
            status = "operational_failure_embeddings"
            rows: list[dict[str, Any]] = []
            decisions = {
                "schema": 1,
                "status": "blocked_by_operational_failure",
                "triggered_families": [],
            }
        else:
            clean_rows = collect_evaluations(
                {
                    **dict(plan),
                    "core_evaluations": [],
                    "conditional_evaluations": [],
                },
                cache_dir=cache,
            )
            clean_gate = len(clean_rows) == 16 and all(
                bool(row["decode_success"]) for row in clean_rows
            )
            if not clean_gate:
                status = "blocked_by_clean_gate"
                rows = clean_rows
                decisions = decide_hard_checks(clean_rows)
            else:
                core_tasks = [
                    _task_from_dict(task)
                    for task in plan["core_evaluations"]
                ]
                core_stage = runner.run(
                    core_tasks,
                    stage="02_core_channels",
                    worker=worker_execute_task,
                )
                stages.append(core_stage)
                referenced_ids.extend(task.object_id for task in core_tasks)
                if core_stage["failed"]:
                    status = "operational_failure_core"
                    rows = clean_rows
                    decisions = {
                        "schema": 1,
                        "status": "blocked_by_operational_failure",
                        "triggered_families": [],
                    }
                else:
                    rows = collect_evaluations(plan, cache_dir=cache)
                    if len(rows) != MANDATORY_ROWS:
                        raise RuntimeError(
                            f"core aggregation produced {len(rows)}, expected 64"
                        )
                    decisions = decide_hard_checks(rows)
                    triggered = decisions["triggered_families"]
                    conditional_tasks = _selected_conditional_tasks(
                        plan,
                        triggered,
                    )
                    if conditional_tasks:
                        conditional_stage = runner.run(
                            conditional_tasks,
                            stage="03_conditional_hard_checks",
                            worker=worker_execute_task,
                        )
                        stages.append(conditional_stage)
                        referenced_ids.extend(
                            task.object_id for task in conditional_tasks
                        )
                        if conditional_stage["failed"]:
                            status = "operational_failure_conditional"
                            for family in triggered:
                                decisions["families"][family]["status"] = (
                                    "blocked_by_operational_failure"
                                )
                        else:
                            rows = collect_evaluations(
                                plan,
                                cache_dir=cache,
                                conditional_families=triggered,
                            )
                            for family in triggered:
                                decisions["families"][family]["status"] = (
                                    "triggered_and_run"
                                )
                            status = "complete"
                    else:
                        status = "complete"
        atomic_write_json(run_dir / "trigger_decisions.json", decisions)
        if rows:
            if status == "complete":
                expected = (
                    MANDATORY_ROWS
                    + 8 * len(decisions.get("triggered_families", []))
                )
                if len(rows) != expected:
                    raise RuntimeError(
                        f"result count {len(rows)} does not match planned {expected}"
                    )
            if len(rows) > ABSOLUTE_MAX_ROWS:
                raise RuntimeError("result count exceeds the absolute 88-row cap")
            report = write_reports(
                run_dir,
                rows,
                require_parquet=require_parquet,
            )
        else:
            report = {
                "schema": 1,
                "evaluation_rows": 0,
                "files": {},
                "parquet": {"status": "not_attempted"},
            }
        run_summary = {
            "schema": 1,
            "run_id": plan["run_id"],
            "status": status,
            "scientific_status": plan["material"]["scientific_status"],
            "created_at": plan["created_at"],
            "updated_at": utc_now(),
            "mandatory_rows": MANDATORY_ROWS,
            "conditional_rows": max(0, len(rows) - MANDATORY_ROWS),
            "result_rows": len(rows),
            "absolute_max_rows": ABSOLUTE_MAX_ROWS,
            "triggered_families": decisions.get("triggered_families", []),
            "stages": [
                {
                    key: value
                    for key, value in stage.items()
                    if key != "records"
                }
                for stage in stages
            ],
            "resource_plan": resource_plan,
            "runtime_gate": runtime_gate,
            "report": report,
            "cache_dir": str(cache),
            "run_dir": str(run_dir),
            "git": git_state(),
            "environment": environment_snapshot(),
        }
        atomic_write_json(run_dir / "run_summary.json", run_summary)
        if package_results and referenced_ids:
            run_summary["bundle"] = create_download_bundle(
                run_dir,
                cache_dir=cache,
                object_ids=referenced_ids,
                allow_missing_objects=status != "complete",
            )
            atomic_write_json(run_dir / "run_summary.json", run_summary)
        return run_summary
