"""Complete C0--C3 digital embedding and semi-blind extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping

import numpy as np
from numpy.typing import ArrayLike

from .adaptive import BandFeatures, band_features
from .allocation import SlotPlan, build_slot_plan
from .bitstream import EncodedBitstream, decode_bitstream, encode_bitstream
from .config import DigitalADConfig
from .distortion import LambdaSearchResult, search_lambda
from .embedding import (
    apply_perturbation,
    build_unit_perturbation,
    extract_bits,
)
from .preprocessing import require_uint8_grayscale
from .transform_adapter import DigitalTransformAdapter, make_transform_adapter
from .types import BitArray, DecodeOutcome, MethodId, UInt8Image


@dataclass(frozen=True)
class DigitalEmbedding:
    cover: UInt8Image
    secret: UInt8Image
    stego: UInt8Image
    method: MethodId
    pair_id: str
    encoded: EncodedBitstream
    slot_plan: SlotPlan
    features: tuple[BandFeatures, ...]
    lambda_search: LambdaSearchResult
    config: DigitalADConfig
    timings: Mapping[str, float]


@dataclass(frozen=True)
class DigitalExtraction:
    extracted_header_bits: BitArray
    extracted_body_bits: BitArray
    extracted_bits: BitArray
    decode: DecodeOutcome
    raw_ber: float
    timings: Mapping[str, float]


@dataclass(frozen=True)
class DigitalRun:
    embedding: DigitalEmbedding
    extraction: DigitalExtraction
    success: bool
    failure_reason: str | None
    metadata: Mapping[str, Any]


def _plan(
    cover_coefficients: Any,
    *,
    adapter: DigitalTransformAdapter,
    method: MethodId,
    config: DigitalADConfig,
    stability_profile: Mapping[str, float] | None,
) -> tuple[tuple[BandFeatures, ...], SlotPlan]:
    bands = adapter.eligible_bands(cover_coefficients)
    descriptors = adapter.descriptors(cover_coefficients, eligible_only=True)
    band_ids = [item.band_id for item in descriptors]
    features = band_features(
        bands,
        band_ids,
        config=config,
        stability_profile=stability_profile,
    )
    slot_plan = build_slot_plan(
        method=method,
        bands=bands,
        band_ids=band_ids,
        features=features,
        epsilon=config.allocation_epsilon,
    )
    return features, slot_plan


def embed(
    cover: ArrayLike,
    secret: ArrayLike,
    *,
    pair_id: str,
    method: MethodId | str | int,
    config: DigitalADConfig,
    stability_profile: Mapping[str, float] | None = None,
) -> DigitalEmbedding:
    cfg = config.validate()
    selected = MethodId.parse(method)
    cover_image = require_uint8_grayscale(
        cover,
        shape=(cfg.cover_size, cfg.cover_size),
        name="cover",
    )
    secret_image = require_uint8_grayscale(
        secret,
        shape=(cfg.secret_size, cfg.secret_size),
        name="secret",
    )
    total_started = time.perf_counter()
    stage_started = time.perf_counter()
    encoded = encode_bitstream(
        secret_image,
        pair_id=pair_id,
        method=selected,
        config=cfg,
    )
    bitstream_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    adapter = make_transform_adapter(cfg)
    cover_coefficients = adapter.analyze(cover_image)
    transform_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    features, slot_plan = _plan(
        cover_coefficients,
        adapter=adapter,
        method=selected,
        config=cfg,
        stability_profile=stability_profile,
    )
    policy_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    unit = build_unit_perturbation(
        cover_coefficients,
        slot_plan,
        encoded.header_bits,
        encoded.body_bits,
        eligible_level=cfg.eligible_level,
        eligible_bands=adapter.eligible_bands(cover_coefficients),
    )
    perturbation_seconds = time.perf_counter() - stage_started

    def render(strength: float) -> np.ndarray:
        modified = apply_perturbation(
            cover_coefficients,
            unit,
            eligible_level=cfg.eligible_level,
            strength=strength,
            adapter=adapter,
        )
        return adapter.synthesize(modified)

    stage_started = time.perf_counter()
    lambda_search = search_lambda(cover_image, render, cfg)
    lambda_seconds = time.perf_counter() - stage_started
    return DigitalEmbedding(
        cover=cover_image.copy(),
        secret=secret_image.copy(),
        stego=lambda_search.stego,
        method=selected,
        pair_id=pair_id,
        encoded=encoded,
        slot_plan=slot_plan,
        features=features,
        lambda_search=lambda_search,
        config=cfg,
        timings={
            "bitstream_encode_seconds": bitstream_seconds,
            "cover_transform_seconds": transform_seconds,
            "policy_and_allocation_seconds": policy_seconds,
            "unit_perturbation_seconds": perturbation_seconds,
            "lambda_search_seconds": lambda_seconds,
            "embedding_total_seconds": time.perf_counter() - total_started,
        },
    )


def extract(
    stego: ArrayLike,
    original_cover: ArrayLike,
    *,
    pair_id: str,
    method: MethodId | str | int,
    config: DigitalADConfig,
    stability_profile: Mapping[str, float] | None = None,
    expected_bits: ArrayLike | None = None,
) -> DigitalExtraction:
    cfg = config.validate()
    selected = MethodId.parse(method)
    stego_image = require_uint8_grayscale(
        stego,
        shape=(cfg.cover_size, cfg.cover_size),
        name="stego",
    )
    cover_image = require_uint8_grayscale(
        original_cover,
        shape=(cfg.cover_size, cfg.cover_size),
        name="original_cover",
    )
    total_started = time.perf_counter()
    stage_started = time.perf_counter()
    adapter = make_transform_adapter(cfg)
    cover_coefficients = adapter.analyze(cover_image)
    stego_coefficients = adapter.analyze(stego_image)
    transform_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    _, slot_plan = _plan(
        cover_coefficients,
        adapter=adapter,
        method=selected,
        config=cfg,
        stability_profile=stability_profile,
    )
    policy_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    header, body, bits = extract_bits(
        stego_coefficients,
        cover_coefficients,
        slot_plan,
        eligible_level=cfg.eligible_level,
        adapter=adapter,
    )
    bit_extraction_seconds = time.perf_counter() - stage_started
    stage_started = time.perf_counter()
    outcome = decode_bitstream(
        bits,
        pair_id=pair_id,
        expected_method=selected,
        config=cfg,
    )
    decode_seconds = time.perf_counter() - stage_started
    raw_ber = float("nan")
    if expected_bits is not None:
        reference = np.asarray(expected_bits, dtype=np.uint8).reshape(-1)
        if reference.shape != bits.shape:
            raise ValueError("expected bitstream shape does not match extraction")
        raw_ber = float(np.mean(reference != bits))
    return DigitalExtraction(
        extracted_header_bits=header,
        extracted_body_bits=body,
        extracted_bits=bits,
        decode=outcome,
        raw_ber=raw_ber,
        timings={
            "cover_and_stego_transform_seconds": transform_seconds,
            "policy_and_allocation_seconds": policy_seconds,
            "bit_extraction_seconds": bit_extraction_seconds,
            "bitstream_decode_seconds": decode_seconds,
            "extraction_total_seconds": time.perf_counter() - total_started,
        },
    )


def run_clean(
    cover: ArrayLike,
    secret: ArrayLike,
    *,
    pair_id: str,
    method: MethodId | str | int,
    config: DigitalADConfig,
    stability_profile: Mapping[str, float] | None = None,
) -> DigitalRun:
    embedding = embed(
        cover,
        secret,
        pair_id=pair_id,
        method=method,
        config=config,
        stability_profile=stability_profile,
    )
    extraction = extract(
        embedding.stego,
        embedding.cover,
        pair_id=pair_id,
        method=embedding.method,
        config=embedding.config,
        stability_profile=stability_profile,
        expected_bits=embedding.encoded.bits,
    )
    success = extraction.decode.success
    failure_reason = None
    if not success:
        failure_reason = "; ".join(
            failure.reason for failure in extraction.decode.failures
        ) or "clean decode failed"
    return DigitalRun(
        embedding=embedding,
        extraction=extraction,
        success=success,
        failure_reason=failure_reason,
        metadata={
            "clean_decode_required": config.clean_decode_required,
            "transform_profile": config.transform_profile,
            "transform_fingerprint": make_transform_adapter(config).fingerprint(),
        },
    )
