"""Validated, independent configuration for the digital A+D path."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import tomllib
from typing import Any


OCTAVE_PDFB_PROFILE = (
    "octave_pdfb_9_7_pkva_nlev_2222_p3p4_range_v2"
)
SUPPORTED_FORMAT_VERSIONS = {1, 2}


@dataclass(frozen=True)
class DigitalADConfig:
    """All outcome-determining choices for a versioned digital transport."""

    format_version: int = 1
    cover_size: int = 512
    secret_size: int = 128
    grayscale_policy: str = "pillow_l"
    resize_kernel: str = "bicubic"
    rounding_policy: str = "half_up"
    transform_profile: str = "haar_orthogonal_control_v1"
    levels: int = 1
    directions: int = 4
    angular_concentration: float = 8.0
    gaussian_sigma: float = 1.0
    eligible_level: int = 0
    master_seed: int = 2026
    psnr_target_db: float = 45.0
    psnr_tolerance_db: float = 0.1
    lambda_low: float = 0.0
    lambda_high: float = 16.0
    lambda_iterations: int = 24
    entropy_bins: int = 64
    adaptive_weight_min: float = 0.75
    adaptive_weight_max: float = 1.25
    allocation_epsilon: float = 1e-12
    robust_clip: float = 3.0
    clean_decode_required: bool = True

    def validate(self) -> "DigitalADConfig":
        if self.format_version not in SUPPORTED_FORMAT_VERSIONS:
            raise ValueError(
                f"supported digital A+D format versions are "
                f"{sorted(SUPPORTED_FORMAT_VERSIONS)}"
            )
        if self.cover_size != 512:
            raise ValueError("digital A+D formats require a 512x512 cover")
        if self.secret_size != 128:
            raise ValueError("digital A+D formats require a 128x128 secret")
        if self.grayscale_policy != "pillow_l":
            raise ValueError("digital A+D requires grayscale_policy='pillow_l'")
        if self.resize_kernel != "bicubic":
            raise ValueError("digital A+D requires resize_kernel='bicubic'")
        if self.rounding_policy != "half_up":
            raise ValueError("digital A+D requires half-up rounding")
        if self.transform_profile not in {
            "proxy_directional_lp_v1",
            "haar_orthogonal_control_v1",
            OCTAVE_PDFB_PROFILE,
        }:
            raise ValueError(
                "unknown executable transform profile; PDFB profiles require "
                "an explicit external adapter"
            )
        if self.transform_profile == "haar_orthogonal_control_v1":
            if self.levels != 1 or self.directions != 4:
                raise ValueError(
                    "Haar control profile requires levels=1 and directions=4"
                )
        if self.transform_profile == OCTAVE_PDFB_PROFILE:
            if (
                self.levels != 4
                or self.directions != 4
                or self.eligible_level != 0
            ):
                raise ValueError(
                    "Octave PDFB profile fixes levels=4, directions=4, and "
                    "eligible_level=0 (the P3+P4 range-coordinate pool is "
                    "selected by the adapter)"
                )
        if self.levels < 1:
            raise ValueError("levels must be positive")
        if self.directions < 2:
            raise ValueError("directions must be at least two")
        if not 0 <= self.eligible_level < self.levels:
            raise ValueError("eligible_level must identify an existing level")
        if self.cover_size % (2**self.levels):
            raise ValueError("cover_size must be divisible by 2**levels")
        if self.angular_concentration <= 0 or self.gaussian_sigma <= 0:
            raise ValueError("transform filter parameters must be positive")
        if not 0 <= self.master_seed < 2**128:
            raise ValueError("master_seed must fit in an unsigned 128-bit integer")
        if self.psnr_target_db <= 0 or self.psnr_tolerance_db <= 0:
            raise ValueError("PSNR target and tolerance must be positive")
        if not 0 <= self.lambda_low < self.lambda_high:
            raise ValueError("lambda bounds must satisfy 0 <= low < high")
        if self.lambda_iterations < 1:
            raise ValueError("lambda_iterations must be positive")
        if self.entropy_bins != 64:
            raise ValueError("digital A+D fixes entropy_bins at 64")
        if not 0 < self.adaptive_weight_min <= self.adaptive_weight_max:
            raise ValueError("adaptive weight bounds are invalid")
        if self.allocation_epsilon <= 0 or self.robust_clip <= 0:
            raise ValueError("normalization constants must be positive")
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_toml(cls, path: str | Path) -> "DigitalADConfig":
        with Path(path).open("rb") as stream:
            payload = tomllib.load(stream)
        values = payload.get("digital_ad", payload)
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown digital A+D keys: {sorted(unknown)}")
        return cls(**values).validate()
