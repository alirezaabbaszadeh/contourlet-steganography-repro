"""Common method interface used by the benchmark harness.

The audited paper reconstruction is registered as ``paper_baseline``.  A
future proposed method should implement :class:`SteganographyMethod` and be
registered without changing the benchmark or statistical-analysis code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .config import ExperimentConfig
from .pipeline import embed_secret, extract_secret


FloatImage = NDArray[np.float64]
JsonScalar = str | int | float | bool | None


@dataclass(frozen=True)
class MethodEmbedding:
    """Normalized output of one method's embedding phase."""

    cover: FloatImage
    secret: FloatImage
    stego: FloatImage
    metadata: Mapping[str, JsonScalar] = field(default_factory=dict)
    diagnostic_images: Mapping[str, FloatImage] = field(default_factory=dict)
    extraction_context: object | None = field(default=None, repr=False)


@dataclass(frozen=True)
class MethodExtraction:
    """Normalized output of one method's extraction phase."""

    recovered_secret: FloatImage
    metadata: Mapping[str, JsonScalar] = field(default_factory=dict)
    diagnostic_images: Mapping[str, FloatImage] = field(default_factory=dict)


@runtime_checkable
class SteganographyMethod(Protocol):
    """Minimal interface shared by baseline and future proposed methods."""

    name: str
    version: str

    def embed(
        self,
        cover: ArrayLike,
        secret: ArrayLike,
        config: ExperimentConfig,
    ) -> MethodEmbedding:
        """Embed ``secret`` into ``cover`` under the shared experiment config."""

    def extract(
        self,
        stego: ArrayLike,
        original_cover: ArrayLike,
        config: ExperimentConfig,
        *,
        context: object | None = None,
    ) -> MethodExtraction:
        """Recover a secret from a stego image."""


class PaperBaselineMethod:
    """Adapter around the audited Python reconstruction."""

    name = "paper_baseline"
    version = "1"

    def embed(
        self,
        cover: ArrayLike,
        secret: ArrayLike,
        config: ExperimentConfig,
    ) -> MethodEmbedding:
        result = embed_secret(cover, secret, config)
        return MethodEmbedding(
            cover=result.cover,
            secret=result.secret,
            stego=result.stego,
            metadata={
                "transform_backend": "directional_laplacian_proxy",
                "transform_redundancy_ratio": result.transform_redundancy,
                "semi_blind": True,
            },
            diagnostic_images={"encrypted_secret": result.encrypted_secret},
        )

    def extract(
        self,
        stego: ArrayLike,
        original_cover: ArrayLike,
        config: ExperimentConfig,
        *,
        context: object | None = None,
    ) -> MethodExtraction:
        del context
        result = extract_secret(stego, original_cover, config)
        return MethodExtraction(
            recovered_secret=result.recovered_secret,
            diagnostic_images={
                "extracted_encrypted": result.extracted_encrypted,
            },
        )


MethodFactory = Callable[[], SteganographyMethod]
_METHODS: dict[str, MethodFactory] = {
    PaperBaselineMethod.name: PaperBaselineMethod,
}


def register_method(
    name: str,
    factory: MethodFactory,
    *,
    replace: bool = False,
) -> None:
    """Register a method factory for programmatic benchmark extensions."""

    normalized = name.strip()
    if not normalized or any(character.isspace() for character in normalized):
        raise ValueError("method name must be non-empty and contain no whitespace")
    if normalized in _METHODS and not replace:
        raise ValueError(f"method already registered: {normalized}")
    candidate = factory()
    if not isinstance(candidate, SteganographyMethod):
        raise TypeError("factory did not return a SteganographyMethod")
    if candidate.name != normalized:
        raise ValueError(
            f"registered name {normalized!r} does not match method name "
            f"{candidate.name!r}"
        )
    if not isinstance(candidate.version, str) or not candidate.version.strip():
        raise ValueError("method version must be a non-empty string")
    _METHODS[normalized] = factory


def build_method(name: str) -> SteganographyMethod:
    """Instantiate a registered method by its stable identifier."""

    try:
        method = _METHODS[name]()
    except KeyError as error:
        available = ", ".join(sorted(_METHODS))
        raise ValueError(
            f"unknown method {name!r}; available methods: {available}"
        ) from error
    if not isinstance(method, SteganographyMethod):
        raise TypeError(f"registered factory for {name!r} returned an invalid method")
    if method.name != name:
        raise ValueError(
            f"registered factory for {name!r} returned method {method.name!r}"
        )
    if not isinstance(method.version, str) or not method.version.strip():
        raise ValueError(f"method {name!r} has an invalid version")
    return method


def available_methods() -> tuple[str, ...]:
    """Return stable method identifiers in deterministic order."""

    return tuple(sorted(_METHODS))
