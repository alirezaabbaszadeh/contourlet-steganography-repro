"""Configuration models for deterministic paper-reconstruction experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import tomllib
from typing import Any


@dataclass(frozen=True)
class ExperimentConfig:
    """All choices that materially affect one baseline run.

    The article fixes ``alpha=0.15`` and four decomposition levels, but leaves
    several other choices unspecified.  They are explicit here so a result can
    be reproduced and compared fairly.
    """

    alpha: float = 0.15
    levels: int = 4
    directions: int = 4
    angular_concentration: float = 8.0
    band_policy: str = "finest"
    embed_lowpass: bool = False
    quantize_stego: bool = True
    encryption_mode: str = "interpreted"
    stabilize_inverse_hp: bool = True
    image_size: int = 512
    random_seed: int = 2026

    def validate(self) -> "ExperimentConfig":
        if not 0 < self.alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        if self.levels < 1:
            raise ValueError("levels must be positive")
        if self.directions < 2:
            raise ValueError("directions must be at least 2")
        if self.angular_concentration <= 0:
            raise ValueError("angular_concentration must be positive")
        if self.band_policy not in {"finest", "all_details"}:
            raise ValueError("band_policy must be 'finest' or 'all_details'")
        if self.encryption_mode not in {"interpreted", "strict"}:
            raise ValueError("encryption_mode must be 'interpreted' or 'strict'")
        if self.image_size < 2**self.levels:
            raise ValueError("image_size is too small for the requested levels")
        if self.image_size % (2**self.levels):
            raise ValueError("image_size must be divisible by 2**levels")
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_toml(cls, path: str | Path) -> "ExperimentConfig":
        with Path(path).open("rb") as stream:
            payload = tomllib.load(stream)
        values = payload.get("experiment", payload)
        unknown = set(values) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
        return cls(**values).validate()

