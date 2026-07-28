"""Audited transform adapter used only by the digital research path."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Protocol

import numpy as np

from ctsteg.transform import DirectionalLaplacianPyramid, PyramidCoefficients

from .config import DigitalADConfig
from .types import FloatImage


@dataclass(frozen=True)
class BandDescriptor:
    index: int
    band_id: str
    level: int
    direction: int
    shape: tuple[int, int]
    coefficient_count: int


class ProxyTransformAdapter:
    """Versioned adapter around the existing transparent proxy backend."""

    backend_name = "directional_laplacian_proxy"
    profile_name = "proxy_directional_lp_v1"
    backend_version = "1"

    def __init__(self, config: DigitalADConfig) -> None:
        self.config = config.validate()
        self.transform = DirectionalLaplacianPyramid(
            levels=self.config.levels,
            directions=self.config.directions,
            angular_concentration=self.config.angular_concentration,
            gaussian_sigma=self.config.gaussian_sigma,
        )

    def analyze(self, image: np.ndarray) -> PyramidCoefficients:
        values = np.asarray(image, dtype=np.float64)
        expected = (self.config.cover_size, self.config.cover_size)
        if values.shape != expected:
            raise ValueError(f"transform input must have shape {expected}")
        return self.transform.analyze(values)

    def synthesize(self, coefficients: PyramidCoefficients) -> FloatImage:
        return self.transform.synthesize(coefficients)

    def descriptors(
        self,
        coefficients: PyramidCoefficients,
        *,
        eligible_only: bool = False,
    ) -> tuple[BandDescriptor, ...]:
        descriptors: list[BandDescriptor] = []
        index = 0
        for level, bands in enumerate(coefficients.details):
            for direction, band in enumerate(bands):
                if not eligible_only or level == self.config.eligible_level:
                    descriptors.append(
                        BandDescriptor(
                            index=index if eligible_only else len(descriptors),
                            band_id=f"L{level}:D{direction}",
                            level=level,
                            direction=direction,
                            shape=tuple(int(value) for value in band.shape),
                            coefficient_count=int(band.size),
                        )
                    )
                    index += 1
        return tuple(descriptors)

    def eligible_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> tuple[np.ndarray, ...]:
        return tuple(coefficients.details[self.config.eligible_level])

    def fingerprint(self) -> str:
        payload = {
            "backend": self.backend_name,
            "profile": self.profile_name,
            "version": self.backend_version,
            "levels": self.config.levels,
            "directions": self.config.directions,
            "angular_concentration": self.config.angular_concentration,
            "gaussian_sigma": self.config.gaussian_sigma,
            "eligible_level": self.config.eligible_level,
            "pyramid_filter": "scipy.ndimage.gaussian_filter",
            "boundary_mode": "reflect",
            "downsample": "stride_2",
            "prediction": "bilinear_zoom",
            "directional_filter": "soft_fourier_angular_partition",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def iter_all_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> Iterable[tuple[str, np.ndarray]]:
        for level, bands in enumerate(coefficients.details):
            for direction, band in enumerate(bands):
                yield f"L{level}:D{direction}", band
        yield "LOWPASS", coefficients.lowpass


class HaarOrthogonalControlAdapter:
    """Exact four-channel 2-D Haar control, explicitly not a Contourlet."""

    backend_name = "haar_orthogonal_control"
    profile_name = "haar_orthogonal_control_v1"
    backend_version = "1"

    def __init__(self, config: DigitalADConfig) -> None:
        self.config = config.validate()
        if self.config.cover_size % 2:
            raise ValueError("Haar control requires an even cover size")
        if self.config.eligible_level != 0:
            raise ValueError("Haar control exposes only eligible_level=0")

    def analyze(self, image: np.ndarray) -> PyramidCoefficients:
        values = np.asarray(image, dtype=np.float64)
        expected = (self.config.cover_size, self.config.cover_size)
        if values.shape != expected:
            raise ValueError(f"transform input must have shape {expected}")
        top_left = values[0::2, 0::2]
        top_right = values[0::2, 1::2]
        bottom_left = values[1::2, 0::2]
        bottom_right = values[1::2, 1::2]
        bands = [
            (top_left + top_right + bottom_left + bottom_right) / 2.0,
            (top_left - top_right + bottom_left - bottom_right) / 2.0,
            (top_left + top_right - bottom_left - bottom_right) / 2.0,
            (top_left - top_right - bottom_left + bottom_right) / 2.0,
        ]
        return PyramidCoefficients(
            lowpass=np.empty((0, 0), dtype=np.float64),
            details=[[np.asarray(band, dtype=np.float64) for band in bands]],
        )

    def synthesize(self, coefficients: PyramidCoefficients) -> FloatImage:
        if len(coefficients.details) != 1 or len(coefficients.details[0]) != 4:
            raise ValueError("Haar control requires exactly four subbands")
        ll, horizontal, vertical, diagonal = coefficients.details[0]
        if not (
            ll.shape == horizontal.shape == vertical.shape == diagonal.shape
        ):
            raise ValueError("Haar control subband shapes differ")
        output = np.empty(
            (ll.shape[0] * 2, ll.shape[1] * 2),
            dtype=np.float64,
        )
        output[0::2, 0::2] = (
            ll + horizontal + vertical + diagonal
        ) / 2.0
        output[0::2, 1::2] = (
            ll - horizontal + vertical - diagonal
        ) / 2.0
        output[1::2, 0::2] = (
            ll + horizontal - vertical - diagonal
        ) / 2.0
        output[1::2, 1::2] = (
            ll - horizontal - vertical + diagonal
        ) / 2.0
        return output

    def descriptors(
        self,
        coefficients: PyramidCoefficients,
        *,
        eligible_only: bool = False,
    ) -> tuple[BandDescriptor, ...]:
        del eligible_only
        names = ("LL", "HORIZONTAL", "VERTICAL", "DIAGONAL")
        return tuple(
            BandDescriptor(
                index=index,
                band_id=f"H0:{name}",
                level=0,
                direction=index,
                shape=tuple(int(value) for value in band.shape),
                coefficient_count=int(band.size),
            )
            for index, (name, band) in enumerate(
                zip(names, coefficients.details[0], strict=True)
            )
        )

    def eligible_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> tuple[np.ndarray, ...]:
        return tuple(coefficients.details[0])

    def fingerprint(self) -> str:
        payload = {
            "backend": self.backend_name,
            "profile": self.profile_name,
            "version": self.backend_version,
            "normalization": "orthonormal_scale_1_over_2",
            "channels": ["LL", "horizontal", "vertical", "diagonal"],
            "boundary": "exact_even_2x2_blocks",
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def iter_all_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> Iterable[tuple[str, np.ndarray]]:
        for descriptor, band in zip(
            self.descriptors(coefficients),
            coefficients.details[0],
            strict=True,
        ):
            yield descriptor.band_id, band


class DigitalTransformAdapter(Protocol):
    backend_name: str
    profile_name: str
    backend_version: str
    config: DigitalADConfig

    def analyze(self, image: np.ndarray) -> PyramidCoefficients: ...

    def synthesize(self, coefficients: PyramidCoefficients) -> FloatImage: ...

    def descriptors(
        self,
        coefficients: PyramidCoefficients,
        *,
        eligible_only: bool = False,
    ) -> tuple[BandDescriptor, ...]: ...

    def eligible_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> tuple[np.ndarray, ...]: ...

    def fingerprint(self) -> str: ...

    def iter_all_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> Iterable[tuple[str, np.ndarray]]: ...


def make_transform_adapter(config: DigitalADConfig) -> DigitalTransformAdapter:
    cfg = config.validate()
    if cfg.transform_profile == ProxyTransformAdapter.profile_name:
        return ProxyTransformAdapter(cfg)
    if cfg.transform_profile == HaarOrthogonalControlAdapter.profile_name:
        return HaarOrthogonalControlAdapter(cfg)
    raise ValueError(f"no adapter for transform profile {cfg.transform_profile!r}")
