"""Encoding and semi-blind decoding for the reconstructed baseline."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .config import ExperimentConfig
from .encryption import decrypt_secret, encrypt_secret
from .transform import DirectionalLaplacianPyramid, PyramidCoefficients


FloatImage = NDArray[np.float64]


@dataclass(frozen=True)
class StegoResult:
    cover: FloatImage
    secret: FloatImage
    encrypted_secret: FloatImage
    stego: FloatImage
    config: ExperimentConfig
    transform_redundancy: float


@dataclass(frozen=True)
class ExtractionResult:
    extracted_encrypted: FloatImage
    recovered_secret: FloatImage


def _as_image(image: ArrayLike, *, name: str) -> FloatImage:
    array = np.asarray(image, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError(f"{name} must be a two-dimensional grayscale image")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains NaN or infinity")
    return array


def _make_transform(config: ExperimentConfig) -> DirectionalLaplacianPyramid:
    return DirectionalLaplacianPyramid(
        levels=config.levels,
        directions=config.directions,
        angular_concentration=config.angular_concentration,
    )


def _selected_levels(config: ExperimentConfig) -> range:
    if config.band_policy == "finest":
        return range(1)
    return range(config.levels)


def _embed_coefficients(
    cover: PyramidCoefficients,
    secret: PyramidCoefficients,
    config: ExperimentConfig,
) -> PyramidCoefficients:
    modified = cover.copy()
    for level_index in _selected_levels(config):
        for direction_index in range(config.directions):
            modified.details[level_index][direction_index] += (
                config.alpha * secret.details[level_index][direction_index]
            )
    if config.embed_lowpass:
        modified.lowpass += config.alpha * secret.lowpass
    return modified


def _extract_coefficients(
    stego: PyramidCoefficients,
    cover: PyramidCoefficients,
    config: ExperimentConfig,
) -> PyramidCoefficients:
    details = [
        [np.zeros_like(band) for band in level] for level in cover.details
    ]
    extracted = PyramidCoefficients(
        lowpass=np.zeros_like(cover.lowpass),
        details=details,
    )
    for level_index in _selected_levels(config):
        for direction_index in range(config.directions):
            extracted.details[level_index][direction_index] = (
                stego.details[level_index][direction_index]
                - cover.details[level_index][direction_index]
            ) / config.alpha
    if config.embed_lowpass:
        extracted.lowpass = (stego.lowpass - cover.lowpass) / config.alpha
    return extracted


def embed_secret(
    cover: ArrayLike,
    secret: ArrayLike,
    config: ExperimentConfig | None = None,
) -> StegoResult:
    """Encrypt and embed a secret image.

    The transform is applied to both images, matching Algorithm 2's written
    sequence.  The exact selected-band policy is configuration-controlled.
    """

    cfg = (config or ExperimentConfig()).validate()
    cover_image = _as_image(cover, name="cover")
    secret_image = _as_image(secret, name="secret")
    if cover_image.shape != secret_image.shape:
        raise ValueError("cover and secret must have the same shape")
    if cover_image.shape != (cfg.image_size, cfg.image_size):
        raise ValueError(
            f"images must be {cfg.image_size}x{cfg.image_size} for this run"
        )
    if cover_image.min() < 0 or cover_image.max() > 255:
        raise ValueError("cover values must be within [0, 255]")

    encrypted = encrypt_secret(secret_image, mode=cfg.encryption_mode)
    transform = _make_transform(cfg)
    cover_coeffs = transform.analyze(cover_image)
    secret_coeffs = transform.analyze(encrypted)
    modified_coeffs = _embed_coefficients(cover_coeffs, secret_coeffs, cfg)
    stego = transform.synthesize(modified_coeffs)
    if cfg.quantize_stego:
        stego = np.rint(np.clip(stego, 0.0, 255.0))

    return StegoResult(
        cover=cover_image.copy(),
        secret=secret_image.copy(),
        encrypted_secret=encrypted,
        stego=stego,
        config=cfg,
        transform_redundancy=transform.redundancy_ratio(cover_image.shape),
    )


def extract_secret(
    stego: ArrayLike,
    original_cover: ArrayLike,
    config: ExperimentConfig | None = None,
) -> ExtractionResult:
    """Extract using the original cover, as required by the semi-blind paper."""

    cfg = (config or ExperimentConfig()).validate()
    stego_image = _as_image(stego, name="stego")
    cover_image = _as_image(original_cover, name="original_cover")
    if stego_image.shape != cover_image.shape:
        raise ValueError("stego and original cover must have the same shape")
    if stego_image.shape != (cfg.image_size, cfg.image_size):
        raise ValueError(
            f"images must be {cfg.image_size}x{cfg.image_size} for this run"
        )

    transform = _make_transform(cfg)
    stego_coeffs = transform.analyze(stego_image)
    cover_coeffs = transform.analyze(cover_image)
    extracted_coeffs = _extract_coefficients(stego_coeffs, cover_coeffs, cfg)
    extracted_encrypted = transform.synthesize(extracted_coeffs)
    recovered = decrypt_secret(
        extracted_encrypted,
        stabilize_hp=cfg.stabilize_inverse_hp,
        clip_output=True,
    )
    return ExtractionResult(
        extracted_encrypted=extracted_encrypted,
        recovered_secret=recovered,
    )

