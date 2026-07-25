"""Validated cover/secret pairing manifests."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Mapping


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REQUIRED_COLUMNS = {"pair_id", "cover", "secret"}
_KNOWN_COLUMNS = _REQUIRED_COLUMNS | {"split", "seed"}


@dataclass(frozen=True)
class ImagePair:
    """One cover/secret pair and its declared experimental unit."""

    pair_id: str
    cover: Path
    secret: Path
    split: str = "test"
    seed: int | None = None
    declared_cover: str = ""
    declared_secret: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def unit_id(self) -> str:
        seed = "config" if self.seed is None else str(self.seed)
        return f"{self.pair_id}@{seed}"


def _resolve_input(base: Path, declared: str, *, field_name: str) -> Path:
    if not declared.strip():
        raise ValueError(f"{field_name} path must not be empty")
    candidate = Path(declared).expanduser()
    resolved = (
        (base / candidate).resolve()
        if not candidate.is_absolute()
        else candidate.resolve()
    )
    if not resolved.is_file():
        raise FileNotFoundError(f"{field_name} image not found: {resolved}")
    return resolved


def read_manifest(path: str | Path) -> list[ImagePair]:
    """Read and validate a UTF-8 CSV manifest.

    Required columns are ``pair_id``, ``cover``, and ``secret``.  Relative
    paths are resolved against the manifest's directory.  Optional ``split``
    and ``seed`` columns support locked test splits and repeated stochastic
    runs.  Additional columns are preserved as metadata.
    """

    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    with manifest_path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = _REQUIRED_COLUMNS - columns
        if missing:
            raise ValueError(
                f"manifest is missing required columns: {sorted(missing)}"
            )

        pairs: list[ImagePair] = []
        observed_units: set[tuple[str, int | None]] = set()
        for line_number, row in enumerate(reader, start=2):
            pair_id = (row.get("pair_id") or "").strip()
            if not _SAFE_ID.fullmatch(pair_id):
                raise ValueError(
                    f"line {line_number}: pair_id must match "
                    "[A-Za-z0-9][A-Za-z0-9._-]*"
                )
            split = (row.get("split") or "test").strip()
            if not _SAFE_ID.fullmatch(split):
                raise ValueError(
                    f"line {line_number}: split must be a filesystem-safe label"
                )

            raw_seed = (row.get("seed") or "").strip()
            try:
                seed = None if not raw_seed else int(raw_seed)
            except ValueError as error:
                raise ValueError(
                    f"line {line_number}: seed must be an integer"
                ) from error
            if seed is not None and seed < 0:
                raise ValueError(f"line {line_number}: seed must be non-negative")

            unit = (pair_id, seed)
            if unit in observed_units:
                raise ValueError(
                    f"line {line_number}: duplicate experimental unit "
                    f"{pair_id!r} with seed {seed!r}"
                )
            observed_units.add(unit)

            declared_cover = (row.get("cover") or "").strip()
            declared_secret = (row.get("secret") or "").strip()
            metadata = {
                key: value
                for key, value in row.items()
                if key not in _KNOWN_COLUMNS and value not in (None, "")
            }
            pairs.append(
                ImagePair(
                    pair_id=pair_id,
                    cover=_resolve_input(
                        manifest_path.parent,
                        declared_cover,
                        field_name="cover",
                    ),
                    secret=_resolve_input(
                        manifest_path.parent,
                        declared_secret,
                        field_name="secret",
                    ),
                    split=split,
                    seed=seed,
                    declared_cover=declared_cover,
                    declared_secret=declared_secret,
                    metadata=metadata,
                )
            )

    if not pairs:
        raise ValueError("manifest contains no image pairs")
    return pairs
