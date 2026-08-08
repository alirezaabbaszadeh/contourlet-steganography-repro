"""Audited transform adapter used only by the digital research path."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Mapping, Protocol

import numpy as np
from scipy.io import loadmat, savemat

from ctsteg.transform import DirectionalLaplacianPyramid, PyramidCoefficients

from .config import DigitalADConfig, OCTAVE_PDFB_PROFILE
from .types import FloatImage


_PDFB_PFILTER = "9-7"
_PDFB_DFILTER = "pkva"
_PDFB_NLEVELS = (2, 2, 2, 2)
_PDFB_ELIGIBLE_LEVELS_FROM_COARSE = (3, 4)
_PDFB_RANGE_SCHEME = (
    "pdfb_9_7_pkva_multiscale_range_coordinates_p3_p4_v2"
)
_PDFB_RANGE_EVIDENCE_PROFILE = "octave_pdfb_range_coordinates_v2"
_PDFB_STAGE0_SOURCE_SHA256 = (
    "5e6569a12407d321cd6ad2e12f43cda63dc6e58b64501e7fe2f3de28497efc4c"
)
_PDFB_TOOLBOX_TREE_SHA256 = (
    "29cb403a6e41d3ad8e6e9b7956098d2fdaa872749162f75187c9285aef5ad0c9"
)
_PDFB_COORDINATE_BANDS = (
    ("V:P4:LH", 0, 0, (256, 256)),
    ("V:P4:HL", 0, 1, (256, 256)),
    ("V:P4:HH", 0, 2, (256, 256)),
    ("V:P3:LH", 1, 0, (128, 128)),
    ("V:P3:HL", 1, 1, (128, 128)),
    ("V:P3:HH", 1, 2, (128, 128)),
)
_PDFB_INTERNAL_BAND_COUNTS = (3, 3, 4, 4)
_PDFB_REQUIRED_SLOTS = 222_360
_PDFB_RECONSTRUCTION_MAX_ABS = 1e-8
_PDFB_SELF_GAIN_MIN = 0.99
_PDFB_CROSS_TALK_MAX = 0.01
_PDFB_OFF_TARGET_L2_MAX = 0.05
_PDFB_MIN_PROBES_PER_BAND = 3
_OCTAVE_BRIDGE_SOURCE = r"""
toolbox_path = getenv('CTSTEG_BRIDGE_TOOLBOX');
input_path = getenv('CTSTEG_BRIDGE_INPUT');
output_path = getenv('CTSTEG_BRIDGE_OUTPUT');
operation = getenv('CTSTEG_BRIDGE_OPERATION');
assert(!isempty(toolbox_path), 'CTSteg:MissingToolbox');
assert(!isempty(input_path), 'CTSteg:MissingInput');
assert(!isempty(output_path), 'CTSteg:MissingOutput');
addpath(genpath(toolbox_path), '-begin');
toolbox_canonical = canonicalize_file_name(toolbox_path);
toolbox_prefix = [toolbox_canonical filesep];
required_functions = { ...
  'pdfbdec', 'pdfbrec', 'pfilters', 'wfb2dec', 'wfb2rec', ...
  'dfbdec_l', 'dfbrec_l', 'resampc'};
for required_index = 1:numel(required_functions)
  resolved_path = canonicalize_file_name( ...
    which(required_functions{required_index}));
  assert(!isempty(resolved_path), 'CTSteg:MissingToolboxFunction');
  assert(strncmp(resolved_path, toolbox_prefix, length(toolbox_prefix)), ...
    'CTSteg:ToolboxFunctionShadowed');
end
load(input_path);
if strcmp(operation, 'analyze')
  assert(exist('image', 'var') == 1, 'CTSteg:MissingImage');
  coefficients = pdfbdec(double(image), '9-7', 'pkva', [2 2 2 2]);
  assert(iscell(coefficients) && numel(coefficients) == 5, ...
    'CTSteg:CoefficientLevels');
  [pyramid_h, pyramid_g] = pfilters('9-7');
  lowpass = double(coefficients{1});
  lowpass_values = lowpass(:);
  lowpass_shape = double(size(lowpass));
  detail_values = zeros(0, 1);
  detail_counts = [4; 4; 3; 3];
  detail_shapes = zeros(14, 2);
  detail_offsets = zeros(15, 1);
  slot = 1;
  for level = 1:4
    raw_bands = coefficients{level + 1};
    assert(iscell(raw_bands) && numel(raw_bands) == 4, ...
      'CTSteg:DirectionalBands');
    if level >= 3
      detail_image = dfbrec_l(raw_bands, 'pkva');
      [range_leakage, coord_lh, coord_hl, coord_hh] = ...
        wfb2dec(detail_image, pyramid_h, pyramid_g);
      assert(max(abs(range_leakage(:))) <= 1e-8, ...
        'CTSteg:RangeLeakage');
      level_bands = {coord_lh, coord_hl, coord_hh};
    else
      level_bands = raw_bands;
    end
    for direction = 1:numel(level_bands)
      band = double(level_bands{direction});
      assert(ismatrix(band) && all(isfinite(band(:))), ...
        'CTSteg:BandValues');
      detail_shapes(slot, :) = double(size(band));
      detail_values = [detail_values; band(:)];
      detail_offsets(slot + 1) = numel(detail_values);
      slot = slot + 1;
    end
  end
  save('-mat7-binary', output_path, 'lowpass_values', 'lowpass_shape', ...
    'detail_values', 'detail_counts', 'detail_shapes', 'detail_offsets');
elseif strcmp(operation, 'synthesize')
  assert(exist('lowpass_values', 'var') == 1, 'CTSteg:MissingLowpass');
  assert(exist('detail_values', 'var') == 1, 'CTSteg:MissingDetails');
  assert(isequal(double(detail_counts(:)), [4; 4; 3; 3]), ...
    'CTSteg:DetailCounts');
  assert(all(size(detail_shapes) == [14 2]), 'CTSteg:DetailShapes');
  assert(numel(detail_offsets) == 15, 'CTSteg:DetailOffsets');
  [pyramid_h, pyramid_g] = pfilters('9-7');
  coefficients = cell(1, 5);
  coefficients{1} = reshape(double(lowpass_values), double(lowpass_shape));
  slot = 1;
  for level = 1:4
    level_bands = cell(1, double(detail_counts(level)));
    for direction = 1:double(detail_counts(level))
      first = double(detail_offsets(slot)) + 1;
      last = double(detail_offsets(slot + 1));
      assert(last >= first && last <= numel(detail_values), ...
        'CTSteg:DetailRange');
      level_bands{direction} = reshape( ...
        double(detail_values(first:last)), double(detail_shapes(slot, :)));
      slot = slot + 1;
    end
    if level >= 3
      zero_lowpass = zeros(size(level_bands{1}));
      detail_image = wfb2rec( ...
        zero_lowpass, level_bands{1}, level_bands{2}, level_bands{3}, ...
        pyramid_h, pyramid_g);
      coefficients{level + 1} = dfbdec_l(detail_image, 'pkva', 2);
    else
      coefficients{level + 1} = level_bands;
    end
  end
  image = double(pdfbrec(coefficients, '9-7', 'pkva'));
  assert(ismatrix(image) && all(isfinite(image(:))), ...
    'CTSteg:ReconstructionValues');
  save('-mat7-binary', output_path, 'image');
else
  error('CTSteg:UnknownOperation', 'Unknown bridge operation');
end
""".strip()


@dataclass(frozen=True)
class BandDescriptor:
    index: int
    band_id: str
    level: int
    direction: int
    shape: tuple[int, int]
    coefficient_count: int


def _add_coordinate_perturbation(
    bands: Iterable[np.ndarray],
    perturbation: tuple[np.ndarray, ...],
    *,
    strength: float,
) -> None:
    if not np.isfinite(strength) or strength < 0:
        raise ValueError("embedding strength must be finite and non-negative")
    targets = tuple(bands)
    if len(targets) != len(perturbation):
        raise ValueError("perturbation band count does not match transform")
    for band, unit in zip(targets, perturbation, strict=True):
        if band.shape != unit.shape:
            raise ValueError("perturbation band shape does not match transform")
        band += strength * np.asarray(unit, dtype=np.float64)


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

    def apply_eligible_perturbation(
        self,
        coefficients: PyramidCoefficients,
        perturbation: tuple[np.ndarray, ...],
        *,
        strength: float,
    ) -> PyramidCoefficients:
        modified = coefficients.copy()
        _add_coordinate_perturbation(
            modified.details[self.config.eligible_level],
            perturbation,
            strength=strength,
        )
        return modified

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

    def apply_eligible_perturbation(
        self,
        coefficients: PyramidCoefficients,
        perturbation: tuple[np.ndarray, ...],
        *,
        strength: float,
    ) -> PyramidCoefficients:
        modified = coefficients.copy()
        _add_coordinate_perturbation(
            modified.details[0],
            perturbation,
            strength=strength,
        )
        return modified

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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_runtime(value: str) -> Path:
    candidate = Path(value).expanduser()
    located = (
        str(candidate)
        if candidate.is_file()
        else shutil.which(value)
    )
    if not located:
        raise FileNotFoundError(
            "Octave PDFB runtime not found; set CTSTEG_PDFB_RUNTIME "
            "to octave-cli"
        )
    return Path(located).resolve()


def _unique_toolbox_file(root: Path, name: str) -> Path:
    matches = sorted(
        path.resolve()
        for path in root.rglob(name)
        if path.is_file()
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {name} below {root}, found {len(matches)}"
        )
    return matches[0]


def _toolbox_inventory(root: Path) -> tuple[dict[str, str], ...]:
    for name in (
        "pdfbdec.m",
        "pdfbrec.m",
        "pfilters.m",
        "wfb2dec.m",
        "wfb2rec.m",
        "dfbdec_l.m",
        "dfbrec_l.m",
    ):
        _unique_toolbox_file(root, name)
    resampc = sorted(
        path.resolve()
        for path in root.rglob("resampc.*")
        if path.is_file()
    )
    if not resampc:
        raise RuntimeError(
            f"no resampc implementation was found below {root}"
        )
    paths = sorted(
        path.resolve()
        for path in root.rglob("*")
        if path.is_file()
    )
    return tuple(
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path),
        }
        for path in paths
    )


def _inventory_tree_sha256(
    inventory: Iterable[Mapping[str, str]],
) -> str:
    digest = hashlib.sha256()
    for item in inventory:
        digest.update(str(item["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(item["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PDFB Stage-0 evidence {label} must be an object")
    return value


def _require_finite_number(
    mapping: Mapping[str, Any],
    key: str,
    label: str,
) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"PDFB Stage-0 evidence {label}.{key} is not numeric")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"PDFB Stage-0 evidence {label}.{key} is not finite")
    return result


def _validate_raw_stage0_evidence(
    payload: Mapping[str, Any],
    *,
    inventory: tuple[dict[str, str], ...],
    runtime_path: Path,
    toolbox_path: Path,
) -> None:
    if payload.get("schema") != 2 or payload.get("runtime_verified") is not True:
        raise ValueError("PDFB Stage-0 evidence is not runtime-verified schema 2")
    if payload.get("profile") != _PDFB_RANGE_EVIDENCE_PROFILE:
        raise ValueError(
            "PDFB Stage-0 evidence profile is not the approved range profile"
        )
    if payload.get("scheme") != _PDFB_RANGE_SCHEME:
        raise ValueError("PDFB Stage-0 coordinate scheme does not match")
    if payload.get("exploratory") is not False or payload.get("passed") is not True:
        raise ValueError("PDFB Stage-0 evidence is not a locked passing artifact")
    if payload.get("author_equivalence_claimed") is not False:
        raise ValueError(
            "PDFB Stage-0 evidence must reject author-equivalence claims"
        )
    source = _require_mapping(payload.get("source"), "source")
    if source.get("script_sha256") != _PDFB_STAGE0_SOURCE_SHA256:
        raise ValueError(
            "PDFB Stage-0 source script hash is not the locked FINAL2 source"
        )
    parameters = _require_mapping(payload.get("parameters"), "parameters")
    expected_parameters = {
        "pfilter": _PDFB_PFILTER,
        "dfilter": _PDFB_DFILTER,
        "nlevels": list(_PDFB_NLEVELS),
        "eligible_pyramid_levels_from_coarse": list(
            _PDFB_ELIGIBLE_LEVELS_FROM_COARSE
        ),
        "cover_size": 512,
        "required_slots": _PDFB_REQUIRED_SLOTS,
        "probe_delta": 1,
        "probe_fractions": [0.25, 0.5, 0.75],
        "coordinate_order": [
            item[0] for item in _PDFB_COORDINATE_BANDS
        ],
    }
    for key, expected in expected_parameters.items():
        if parameters.get(key) != expected:
            raise ValueError(
                f"PDFB Stage-0 evidence parameters.{key} does not match "
                "the executable profile"
            )

    virtual_bands = payload.get("virtual_bands")
    if not isinstance(virtual_bands, list) or len(virtual_bands) != 6:
        raise ValueError("PDFB Stage-0 evidence must expose six virtual bands")
    expected_band_ids = tuple(item[0] for item in _PDFB_COORDINATE_BANDS)
    band_shapes: dict[str, tuple[int, int]] = {}
    candidate_coordinates = 0
    for record, expected in zip(
        virtual_bands,
        _PDFB_COORDINATE_BANDS,
        strict=True,
    ):
        item = _require_mapping(record, "virtual_bands item")
        band_id, _level, _direction, expected_shape = expected
        if item.get("band_id") != band_id:
            raise ValueError("PDFB Stage-0 virtual-band order or ID differs")
        shape_value = item.get("shape")
        if shape_value != list(expected_shape):
            raise ValueError(f"PDFB Stage-0 {band_id} shape differs")
        count = item.get("coordinate_count")
        if count != expected_shape[0] * expected_shape[1]:
            raise ValueError(f"PDFB Stage-0 {band_id} count differs")
        band_shapes[band_id] = expected_shape
        candidate_coordinates += int(count)

    rank = _require_mapping(payload.get("rank_certificate"), "rank_certificate")
    if (
        rank.get("p4_raw_directional_values") != 262_144
        or rank.get("p4_independent_coordinates") != 196_608
        or rank.get("p3_raw_directional_values") != 65_536
        or rank.get("p3_independent_coordinates") != 49_152
        or rank.get("p3_p4_independent_coordinates") != 245_760
        or candidate_coordinates != 245_760
    ):
        raise ValueError("PDFB Stage-0 capacity gate did not pass")
    capacity = _require_mapping(payload.get("capacity"), "capacity")
    expected_utilization = _PDFB_REQUIRED_SLOTS / candidate_coordinates
    if (
        capacity.get("required_slots") != _PDFB_REQUIRED_SLOTS
        or capacity.get("candidate_coefficients") != candidate_coordinates
        or capacity.get("candidate_coordinates") != candidate_coordinates
        or capacity.get("coordinate_basis_rank") != candidate_coordinates
        or capacity.get("capacity_sufficient") is not True
        or capacity.get("unused_candidate_slots")
        != candidate_coordinates - _PDFB_REQUIRED_SLOTS
        or not math.isclose(
            _require_finite_number(
                capacity,
                "candidate_utilization",
                "capacity",
            ),
            expected_utilization,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise ValueError("PDFB Stage-0 capacity record is inconsistent")

    reconstruction = _require_mapping(
        payload.get("perfect_reconstruction"),
        "perfect_reconstruction",
    )
    reconstruction_error = _require_finite_number(
        reconstruction,
        "max_abs_error",
        "perfect_reconstruction",
    )
    if reconstruction_error < 0 or reconstruction_error > _PDFB_RECONSTRUCTION_MAX_ABS:
        raise ValueError("PDFB Stage-0 perfect-reconstruction gate did not pass")
    reconstruction_rmse = _require_finite_number(
        reconstruction,
        "rmse",
        "perfect_reconstruction",
    )
    if reconstruction_rmse < 0 or reconstruction_rmse > reconstruction_error:
        raise ValueError("PDFB Stage-0 reconstruction RMSE is inconsistent")
    leakage = _require_mapping(
        payload.get("valid_range_leakage"),
        "valid_range_leakage",
    )
    leakage_values = [
        _require_finite_number(leakage, key, "valid_range_leakage")
        for key in leakage
        if key.endswith("_max_abs")
    ]
    if (
        not leakage_values
        or min(leakage_values) < 0
        or max(leakage_values) > _PDFB_RECONSTRUCTION_MAX_ABS
        or leakage.get("gate_passed") is not True
        or _require_finite_number(
            leakage,
            "threshold",
            "valid_range_leakage",
        )
        != _PDFB_RECONSTRUCTION_MAX_ABS
        or _require_finite_number(
            leakage,
            "maximum_observed",
            "valid_range_leakage",
        )
        != max(leakage_values)
    ):
        raise ValueError("PDFB Stage-0 valid-range leakage gate did not pass")

    writability = _require_mapping(
        payload.get("independent_writability"),
        "independent_writability",
    )
    probes = writability.get("probes")
    if not isinstance(probes, list):
        raise ValueError("PDFB Stage-0 evidence probes must be an array")
    counts = {band_id: 0 for band_id in expected_band_ids}
    identities: set[tuple[str, int, int]] = set()
    probe_self_gains: list[float] = []
    probe_cross_talk: list[float] = []
    probe_off_target: list[float] = []
    for raw_probe in probes:
        probe = _require_mapping(raw_probe, "probe")
        band_id = probe.get("band_id")
        if band_id not in counts:
            raise ValueError("PDFB Stage-0 probe names an unknown virtual band")
        row = probe.get("row")
        column = probe.get("column")
        if isinstance(row, bool) or not isinstance(row, int):
            raise ValueError("PDFB Stage-0 probe row is not an integer")
        if isinstance(column, bool) or not isinstance(column, int):
            raise ValueError("PDFB Stage-0 probe column is not an integer")
        shape = band_shapes[str(band_id)]
        if not 0 <= row < shape[0] or not 0 <= column < shape[1]:
            raise ValueError("PDFB Stage-0 probe coordinate is out of range")
        fraction = _require_finite_number(probe, "fraction", "probe")
        if fraction not in (0.25, 0.5, 0.75):
            raise ValueError("PDFB Stage-0 probe fraction is not locked")
        expected_row = int(fraction * (shape[0] - 1))
        expected_column = int(fraction * (shape[1] - 1))
        if row != expected_row or column != expected_column:
            raise ValueError(
                "PDFB Stage-0 probe coordinate does not match its fraction"
            )
        identity = (str(band_id), row, column)
        if identity in identities:
            raise ValueError("PDFB Stage-0 probes contain a duplicate coordinate")
        identities.add(identity)
        counts[str(band_id)] += 1
        self_gain = _require_finite_number(probe, "self_gain", "probe")
        cross_talk = _require_finite_number(
            probe,
            "maximum_cross_talk",
            "probe",
        )
        off_target = _require_finite_number(
            probe,
            "off_target_l2_ratio",
            "probe",
        )
        if min(self_gain, cross_talk, off_target) < 0:
            raise ValueError("PDFB Stage-0 probe metrics must be non-negative")
        probe_self_gains.append(self_gain)
        probe_cross_talk.append(cross_talk)
        probe_off_target.append(off_target)
    if (
        len(probes) != len(expected_band_ids) * _PDFB_MIN_PROBES_PER_BAND
        or set(counts.values()) != {_PDFB_MIN_PROBES_PER_BAND}
        or writability.get("probe_count") != len(probes)
        or writability.get("probes_per_band") != _PDFB_MIN_PROBES_PER_BAND
    ):
        raise ValueError("PDFB Stage-0 probe-count gate did not pass")
    minimum_self_gain = _require_finite_number(
        writability,
        "minimum_self_gain",
        "independent_writability",
    )
    maximum_cross_talk = _require_finite_number(
        writability,
        "maximum_cross_talk",
        "independent_writability",
    )
    maximum_off_target = _require_finite_number(
        writability,
        "maximum_off_target_l2_ratio",
        "independent_writability",
    )
    if (
        minimum_self_gain != min(probe_self_gains)
        or maximum_cross_talk != max(probe_cross_talk)
        or maximum_off_target != max(probe_off_target)
    ):
        raise ValueError(
            "PDFB Stage-0 writability aggregates do not match probe records"
        )
    if (
        minimum_self_gain < _PDFB_SELF_GAIN_MIN
        or maximum_cross_talk < 0
        or maximum_cross_talk > _PDFB_CROSS_TALK_MAX
        or maximum_off_target < 0
        or maximum_off_target > _PDFB_OFF_TARGET_L2_MAX
    ):
        raise ValueError("PDFB Stage-0 independent-writability gate did not pass")

    boundary = _require_mapping(
        payload.get("boundary_writability"),
        "boundary_writability",
    )
    boundary_probes = boundary.get("probes")
    if (
        not isinstance(boundary_probes, list)
        or len(boundary_probes) != len(expected_band_ids) * 2
        or boundary.get("probe_count") != len(boundary_probes)
        or boundary.get("positions_per_band") != 2
        or boundary.get("gate_passed") is not True
    ):
        raise ValueError("PDFB Stage-0 boundary-probe coverage did not pass")
    boundary_identities: set[tuple[str, str]] = set()
    boundary_self_gains: list[float] = []
    boundary_cross_talk: list[float] = []
    boundary_off_target: list[float] = []
    for raw_probe in boundary_probes:
        probe = _require_mapping(raw_probe, "boundary probe")
        band_id = str(probe.get("band_id"))
        if band_id not in band_shapes:
            raise ValueError("PDFB Stage-0 boundary probe has an unknown band")
        position = str(probe.get("position"))
        if position not in {"first", "last"}:
            raise ValueError("PDFB Stage-0 boundary probe position is invalid")
        identity = (band_id, position)
        if identity in boundary_identities:
            raise ValueError("PDFB Stage-0 boundary probes contain a duplicate")
        boundary_identities.add(identity)
        shape = band_shapes[band_id]
        expected_coordinate = (
            (0, 0)
            if position == "first"
            else (shape[0] - 1, shape[1] - 1)
        )
        if (probe.get("row"), probe.get("column")) != expected_coordinate:
            raise ValueError("PDFB Stage-0 boundary probe coordinate is invalid")
        boundary_self_gains.append(
            _require_finite_number(probe, "self_gain", "boundary probe")
        )
        boundary_cross_talk.append(
            _require_finite_number(
                probe,
                "maximum_cross_talk",
                "boundary probe",
            )
        )
        boundary_off_target.append(
            _require_finite_number(
                probe,
                "off_target_l2_ratio",
                "boundary probe",
            )
        )
    boundary_minimum_self = _require_finite_number(
        boundary,
        "minimum_self_gain",
        "boundary_writability",
    )
    boundary_maximum_cross = _require_finite_number(
        boundary,
        "maximum_cross_talk",
        "boundary_writability",
    )
    boundary_maximum_off_target = _require_finite_number(
        boundary,
        "maximum_off_target_l2_ratio",
        "boundary_writability",
    )
    if (
        boundary_minimum_self != min(boundary_self_gains)
        or boundary_maximum_cross != max(boundary_cross_talk)
        or boundary_maximum_off_target != max(boundary_off_target)
        or boundary_minimum_self < _PDFB_SELF_GAIN_MIN
        or not 0 <= boundary_maximum_cross <= _PDFB_CROSS_TALK_MAX
        or not 0 <= boundary_maximum_off_target <= _PDFB_OFF_TARGET_L2_MAX
    ):
        raise ValueError("PDFB Stage-0 boundary-writability gate did not pass")

    dense = _require_mapping(
        payload.get("dense_222360_sign_trial"),
        "dense_222360_sign_trial",
    )
    if (
        dense.get("slot_count") != _PDFB_REQUIRED_SLOTS
        or dense.get("selection")
        != "all P4 coordinates plus first 8584 coordinates of each P3 band"
        or dense.get("sign_generator")
        != "park_miller_48271_thresholded_v1"
    ):
        raise ValueError("PDFB Stage-0 dense trial has the wrong slot count")
    if dense.get("sign_errors") != 0:
        raise ValueError("PDFB Stage-0 dense trial contains sign errors")
    dense_max_error = _require_finite_number(
        dense,
        "maximum_absolute_coordinate_error",
        "dense_222360_sign_trial",
    )
    dense_selected_l2 = _require_finite_number(
        dense,
        "selected_l2_error_ratio",
        "dense_222360_sign_trial",
    )
    dense_unselected_l2 = _require_finite_number(
        dense,
        "unselected_l2_ratio",
        "dense_222360_sign_trial",
    )
    if (
        dense_max_error < 0
        or dense_max_error > 1e-8
        or dense_selected_l2 < 0
        or dense_selected_l2 > 1e-10
        or dense_unselected_l2 < 0
        or dense_unselected_l2 > _PDFB_OFF_TARGET_L2_MAX
    ):
        raise ValueError("PDFB Stage-0 dense-trial numeric gate did not pass")

    full_dense = _require_mapping(
        payload.get("dense_245760_full_candidate_trial"),
        "dense_245760_full_candidate_trial",
    )
    if (
        full_dense.get("slot_count") != 245_760
        or full_dense.get("selection")
        != "all independent P3+P4 coordinates"
        or full_dense.get("sign_generator")
        != "park_miller_48271_thresholded_offset_20260730_v1"
        or full_dense.get("sign_errors") != 0
        or full_dense.get("gate_passed") is not True
    ):
        raise ValueError("PDFB Stage-0 full-candidate dense trial did not pass")
    full_dense_max_error = _require_finite_number(
        full_dense,
        "maximum_absolute_coordinate_error",
        "dense_245760_full_candidate_trial",
    )
    full_dense_selected_l2 = _require_finite_number(
        full_dense,
        "selected_l2_error_ratio",
        "dense_245760_full_candidate_trial",
    )
    full_dense_leakage = _require_finite_number(
        full_dense,
        "maximum_valid_range_lowpass_abs",
        "dense_245760_full_candidate_trial",
    )
    if (
        not 0 <= full_dense_max_error <= 1e-8
        or not 0 <= full_dense_selected_l2 <= 1e-10
        or not 0 <= full_dense_leakage <= _PDFB_RECONSTRUCTION_MAX_ABS
    ):
        raise ValueError(
            "PDFB Stage-0 full-candidate dense numeric gate did not pass"
        )

    thresholds = _require_mapping(
        payload.get("locked_thresholds"),
        "locked_thresholds",
    )
    if dict(thresholds) != {
        "reconstruction_max_abs": _PDFB_RECONSTRUCTION_MAX_ABS,
        "minimum_self_gain": _PDFB_SELF_GAIN_MIN,
        "maximum_cross_talk": _PDFB_CROSS_TALK_MAX,
        "maximum_off_target_l2_ratio": _PDFB_OFF_TARGET_L2_MAX,
        "valid_range_lowpass_max_abs": _PDFB_RECONSTRUCTION_MAX_ABS,
        "dense_maximum_absolute_coordinate_error": 1e-8,
        "dense_relative_l2_error": 1e-10,
        "minimum_probes_per_band": _PDFB_MIN_PROBES_PER_BAND,
        "required_slots": _PDFB_REQUIRED_SLOTS,
    }:
        raise ValueError("PDFB Stage-0 locked thresholds differ from FINAL2")
    gate = _require_mapping(payload.get("gate"), "gate")
    expected_gate_names = {
        "reconstruction_passed",
        "capacity_passed",
        "rank_passed",
        "probe_coverage_passed",
        "self_gain_passed",
        "cross_talk_passed",
        "off_target_passed",
        "boundary_probes_passed",
        "valid_range_leakage_passed",
        "dense_sign_trial_passed",
        "full_candidate_dense_trial_passed",
        "passed",
    }
    if set(gate) != expected_gate_names or any(
        gate.get(name) is not True for name in expected_gate_names
    ):
        raise ValueError("PDFB Stage-0 FINAL2 gate flags are incomplete")

    evidence_inventory = payload.get("toolbox_inventory")
    if not isinstance(evidence_inventory, list):
        raise ValueError("PDFB Stage-0 toolbox_inventory must be an array")
    normalized_inventory = tuple(
        {
            "path": str(_require_mapping(item, "toolbox item").get("path")),
            "sha256": str(_require_mapping(item, "toolbox item").get("sha256")),
        }
        for item in evidence_inventory
    )
    if normalized_inventory != inventory:
        raise ValueError(
            "PDFB Stage-0 toolbox inventory differs from the runtime toolbox"
        )
    inventory_tree_sha256 = _inventory_tree_sha256(inventory)
    if (
        payload.get("toolbox_inventory_count") != len(inventory)
        or payload.get("toolbox_tree_sha256") != inventory_tree_sha256
        or inventory_tree_sha256 != _PDFB_TOOLBOX_TREE_SHA256
    ):
        raise ValueError("PDFB Stage-0 toolbox tree identity differs from FINAL2")
    toolbox = _require_mapping(payload.get("toolbox"), "toolbox")
    if Path(str(toolbox.get("root", ""))).resolve() != toolbox_path:
        raise ValueError("PDFB Stage-0 toolbox root differs from runtime")
    if (
        toolbox.get("inventory") != list(inventory)
        or toolbox.get("inventory_policy") != "all_regular_files_recursive_v1"
        or toolbox.get("inventory_count") != len(inventory)
        or toolbox.get("tree_sha256") != inventory_tree_sha256
    ):
        raise ValueError("PDFB Stage-0 nested toolbox inventory is inconsistent")
    inventory_by_path = {
        item["path"]: item["sha256"] for item in inventory
    }
    function_inventory = toolbox.get("function_inventory")
    expected_function_names = (
        "pdfbdec",
        "pdfbrec",
        "pfilters",
        "wfb2dec",
        "wfb2rec",
        "dfbdec_l",
        "dfbrec_l",
    )
    if not isinstance(function_inventory, list) or len(
        function_inventory
    ) != len(expected_function_names):
        raise ValueError("PDFB Stage-0 function inventory is incomplete")
    for raw_function, expected_name in zip(
        function_inventory,
        expected_function_names,
        strict=True,
    ):
        function = _require_mapping(raw_function, "toolbox function")
        relative_path = f"{expected_name}.m"
        if (
            function.get("name") != expected_name
            or Path(str(function.get("path", ""))).resolve()
            != (toolbox_path / relative_path).resolve()
            or function.get("sha256") != inventory_by_path.get(relative_path)
        ):
            raise ValueError(
                "PDFB Stage-0 function inventory differs from runtime"
            )
    resampc_path = (toolbox_path / "resampc.mex").resolve()
    resampc = _require_mapping(toolbox.get("resampc_mex"), "resampc_mex")
    if (
        resampc.get("name") != "resampc.mex"
        or Path(str(resampc.get("path", ""))).resolve() != resampc_path
        or resampc.get("sha256") != inventory_by_path.get("resampc.mex")
        or Path(str(toolbox.get("resampc_resolved_path", ""))).resolve()
        != resampc_path
    ):
        raise ValueError("PDFB Stage-0 resampc identity differs from runtime")
    runtime = _require_mapping(payload.get("runtime"), "runtime")
    runtime_version = runtime.get("version")
    runtime_platform = runtime.get("platform")
    runtime_executable = runtime.get("executable")
    current_runtime_version = _octave_version(str(runtime_path))
    if (
        runtime.get("engine") != "gnu_octave"
        or not isinstance(runtime_version, str)
        or not runtime_version.strip()
        or not isinstance(runtime_platform, str)
        or "linux" not in runtime_platform.lower()
        or not isinstance(runtime_executable, str)
        or Path(runtime_executable).resolve() != runtime_path
        or "GNU Octave" not in current_runtime_version
        or runtime_version not in current_runtime_version
    ):
        raise ValueError("PDFB Stage-0 runtime identity differs from GNU Octave/Linux")


@lru_cache(maxsize=8)
def _octave_version(runtime: str) -> str:
    completed = subprocess.run(
        [runtime, "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode:
        raise RuntimeError(
            f"could not identify Octave runtime {runtime}: "
            f"{completed.stderr.strip()}"
        )
    lines = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    if not lines:
        raise RuntimeError(f"Octave runtime {runtime} returned no version")
    return lines[0]


def _reshape_fortran(values: np.ndarray, shape: np.ndarray) -> np.ndarray:
    dimensions = tuple(int(value) for value in np.asarray(shape).reshape(-1))
    if len(dimensions) != 2 or any(value <= 0 for value in dimensions):
        raise RuntimeError(f"invalid PDFB band shape: {dimensions}")
    flat = np.asarray(values, dtype=np.float64).reshape(-1)
    if flat.size != dimensions[0] * dimensions[1]:
        raise RuntimeError("PDFB band vector length does not match its shape")
    return flat.reshape(dimensions, order="F")


class OctavePdfbTransformAdapter:
    """Real Minh Do PDFB adapter executed by a headless Octave subprocess."""

    backend_name = "minh_do_pdfb_octave"
    profile_name = OCTAVE_PDFB_PROFILE
    backend_version = "1"

    def __init__(self, config: DigitalADConfig) -> None:
        self.config = config.validate()
        toolbox_value = os.environ.get("CTSTEG_PDFB_TOOLBOX_PATH", "")
        if not toolbox_value:
            raise RuntimeError(
                "CTSTEG_PDFB_TOOLBOX_PATH is required for the Octave PDFB profile"
            )
        self.toolbox_path = Path(toolbox_value).expanduser().resolve()
        if not self.toolbox_path.is_dir():
            raise FileNotFoundError(
                f"PDFB toolbox directory not found: {self.toolbox_path}"
            )
        self.runtime_path = _resolve_runtime(
            os.environ.get("CTSTEG_PDFB_RUNTIME", "octave-cli")
        )
        evidence_value = os.environ.get("CTSTEG_PDFB_STAGE0_EVIDENCE", "")
        if not evidence_value:
            raise RuntimeError(
                "CTSTEG_PDFB_STAGE0_EVIDENCE is required for the final "
                "Octave PDFB profile"
            )
        self.evidence_path = Path(evidence_value).expanduser().resolve()
        if not self.evidence_path.is_file():
            raise FileNotFoundError(
                f"PDFB Stage-0 evidence not found: {self.evidence_path}"
            )
        self._inventory = _toolbox_inventory(self.toolbox_path)
        with self.evidence_path.open(encoding="utf-8") as stream:
            evidence = json.load(stream)
        if not isinstance(evidence, Mapping):
            raise ValueError("PDFB Stage-0 evidence root must be an object")
        _validate_raw_stage0_evidence(
            evidence,
            inventory=self._inventory,
            runtime_path=self.runtime_path,
            toolbox_path=self.toolbox_path,
        )
        timeout_value = os.environ.get("CTSTEG_PDFB_TIMEOUT_SECONDS", "300")
        self.timeout_seconds = float(timeout_value)
        if not np.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("CTSTEG_PDFB_TIMEOUT_SECONDS must be positive")

    def _run_bridge(
        self,
        operation: str,
        input_path: Path,
        output_path: Path,
        bridge_path: Path,
    ) -> None:
        environment = os.environ.copy()
        environment.update(
            {
                "CTSTEG_BRIDGE_TOOLBOX": str(self.toolbox_path),
                "CTSTEG_BRIDGE_INPUT": str(input_path),
                "CTSTEG_BRIDGE_OUTPUT": str(output_path),
                "CTSTEG_BRIDGE_OPERATION": operation,
            }
        )
        completed = subprocess.run(
            [
                str(self.runtime_path),
                "--quiet",
                "--no-gui",
                "--no-window-system",
                "--no-history",
                str(bridge_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            env=environment,
        )
        if completed.returncode:
            stderr = completed.stderr.strip()[-4000:]
            stdout = completed.stdout.strip()[-2000:]
            raise RuntimeError(
                f"Octave PDFB {operation} failed with exit code "
                f"{completed.returncode}; stdout={stdout!r}; stderr={stderr!r}"
            )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Octave PDFB {operation} produced no MAT output"
            )

    def analyze(self, image: np.ndarray) -> PyramidCoefficients:
        values = np.asarray(image, dtype=np.float64)
        expected = (self.config.cover_size, self.config.cover_size)
        if values.shape != expected:
            raise ValueError(f"transform input must have shape {expected}")
        if not np.all(np.isfinite(values)):
            raise ValueError("transform input contains non-finite values")
        with tempfile.TemporaryDirectory(prefix="ctsteg-pdfb-") as temporary:
            root = Path(temporary)
            input_path = root / "input.mat"
            output_path = root / "output.mat"
            bridge_path = root / "ctsteg_pdfb_bridge.m"
            savemat(input_path, {"image": values}, format="5")
            bridge_path.write_text(_OCTAVE_BRIDGE_SOURCE + "\n", encoding="utf-8")
            self._run_bridge("analyze", input_path, output_path, bridge_path)
            payload = loadmat(output_path)
        lowpass = _reshape_fortran(
            payload["lowpass_values"],
            payload["lowpass_shape"],
        )
        detail_values = np.asarray(
            payload["detail_values"],
            dtype=np.float64,
        ).reshape(-1)
        detail_shapes = np.asarray(payload["detail_shapes"], dtype=np.int64)
        detail_offsets = np.asarray(
            payload["detail_offsets"],
            dtype=np.int64,
        ).reshape(-1)
        detail_counts = tuple(
            int(value)
            for value in np.asarray(
                payload["detail_counts"],
                dtype=np.int64,
            ).reshape(-1)
        )
        if (
            detail_counts != tuple(reversed(_PDFB_INTERNAL_BAND_COUNTS))
            or detail_shapes.shape != (14, 2)
            or detail_offsets.shape != (15,)
        ):
            raise RuntimeError("Octave PDFB returned an invalid detail inventory")
        if (
            detail_offsets[0] != 0
            or detail_offsets[-1] != detail_values.size
            or np.any(np.diff(detail_offsets) <= 0)
        ):
            raise RuntimeError("Octave PDFB returned invalid detail offsets")
        coarse_to_fine: list[list[np.ndarray]] = []
        slot = 0
        for band_count in detail_counts:
            bands: list[np.ndarray] = []
            for _direction in range(band_count):
                start = int(detail_offsets[slot])
                stop = int(detail_offsets[slot + 1])
                bands.append(
                    _reshape_fortran(
                        detail_values[start:stop],
                        detail_shapes[slot],
                    )
                )
                slot += 1
            coarse_to_fine.append(bands)
        details = list(reversed(coarse_to_fine))
        if tuple(len(level) for level in details) != _PDFB_INTERNAL_BAND_COUNTS:
            raise RuntimeError(
                "Octave PDFB internal band counts differ from P4=3, P3=3, "
                "P2=4, P1=4"
            )
        for _band_id, level, direction, expected_shape in _PDFB_COORDINATE_BANDS:
            if details[level][direction].shape != expected_shape:
                raise RuntimeError(
                    "Octave PDFB range-coordinate shape differs from FINAL2"
                )
        return PyramidCoefficients(
            lowpass=lowpass,
            details=details,
        )

    def synthesize(self, coefficients: PyramidCoefficients) -> FloatImage:
        if len(coefficients.details) != self.config.levels:
            raise ValueError("PDFB coefficient level count does not match profile")
        internal_counts = tuple(len(level) for level in coefficients.details)
        if internal_counts != _PDFB_INTERNAL_BAND_COUNTS:
            raise ValueError(
                "PDFB internal band counts must be P4=3, P3=3, P2=4, P1=4"
            )
        lowpass = np.asarray(coefficients.lowpass, dtype=np.float64)
        if lowpass.ndim != 2 or not np.all(np.isfinite(lowpass)):
            raise ValueError("PDFB lowpass must be a finite matrix")
        raw_bands = [
            np.asarray(band, dtype=np.float64)
            for level in reversed(coefficients.details)
            for band in level
        ]
        coarse_to_fine_counts = tuple(reversed(internal_counts))
        if any(band.ndim != 2 or not np.all(np.isfinite(band)) for band in raw_bands):
            raise ValueError("PDFB detail bands must be finite matrices")
        offsets = [0]
        vectors: list[np.ndarray] = []
        for band in raw_bands:
            vector = band.reshape(-1, order="F")
            vectors.append(vector)
            offsets.append(offsets[-1] + vector.size)
        with tempfile.TemporaryDirectory(prefix="ctsteg-pdfb-") as temporary:
            root = Path(temporary)
            input_path = root / "input.mat"
            output_path = root / "output.mat"
            bridge_path = root / "ctsteg_pdfb_bridge.m"
            savemat(
                input_path,
                {
                    "lowpass_values": lowpass.reshape(-1, order="F"),
                    "lowpass_shape": np.asarray(lowpass.shape, dtype=np.float64),
                    "detail_values": np.concatenate(vectors),
                    "detail_counts": np.asarray(
                        coarse_to_fine_counts,
                        dtype=np.float64,
                    ),
                    "detail_shapes": np.asarray(
                        [band.shape for band in raw_bands],
                        dtype=np.float64,
                    ),
                    "detail_offsets": np.asarray(offsets, dtype=np.float64),
                },
                format="5",
            )
            bridge_path.write_text(_OCTAVE_BRIDGE_SOURCE + "\n", encoding="utf-8")
            self._run_bridge("synthesize", input_path, output_path, bridge_path)
            payload = loadmat(output_path)
        output = np.asarray(payload["image"], dtype=np.float64)
        expected = (self.config.cover_size, self.config.cover_size)
        if output.shape != expected or not np.all(np.isfinite(output)):
            raise RuntimeError(
                f"Octave PDFB reconstruction must be finite with shape {expected}"
            )
        return output

    def descriptors(
        self,
        coefficients: PyramidCoefficients,
        *,
        eligible_only: bool = False,
    ) -> tuple[BandDescriptor, ...]:
        descriptors: list[BandDescriptor] = []
        coordinate_lookup = {
            (level, direction): band_id
            for band_id, level, direction, _shape in _PDFB_COORDINATE_BANDS
        }
        for level, bands in enumerate(coefficients.details):
            if eligible_only and level not in (0, 1):
                continue
            pyramid_level = self.config.levels - level
            for direction, band in enumerate(bands):
                band_id = coordinate_lookup.get(
                    (level, direction),
                    f"P{pyramid_level}:D{direction}",
                )
                descriptors.append(
                    BandDescriptor(
                        index=len(descriptors),
                        band_id=band_id,
                        level=level,
                        direction=direction,
                        shape=tuple(int(value) for value in band.shape),
                        coefficient_count=int(band.size),
                    )
                )
        return tuple(descriptors)

    def eligible_bands(
        self,
        coefficients: PyramidCoefficients,
    ) -> tuple[np.ndarray, ...]:
        return tuple(
            band
            for level in coefficients.details[:2]
            for band in level
        )

    def apply_eligible_perturbation(
        self,
        coefficients: PyramidCoefficients,
        perturbation: tuple[np.ndarray, ...],
        *,
        strength: float,
    ) -> PyramidCoefficients:
        modified = coefficients.copy()
        targets = tuple(
            band
            for level in modified.details[:2]
            for band in level
        )
        _add_coordinate_perturbation(
            targets,
            perturbation,
            strength=strength,
        )
        return modified

    def fingerprint(self) -> str:
        payload = {
            "backend": self.backend_name,
            "profile": self.profile_name,
            "version": self.backend_version,
            "runtime": {
                "path": str(self.runtime_path),
                "sha256": _sha256_file(self.runtime_path),
                "version": _octave_version(str(self.runtime_path)),
            },
            "toolbox_root": str(self.toolbox_path),
            "toolbox_inventory": self._inventory,
            "toolbox_tree_sha256": _inventory_tree_sha256(self._inventory),
            "stage0_evidence": {
                "path": str(self.evidence_path),
                "sha256": _sha256_file(self.evidence_path),
                "source_script_sha256": _PDFB_STAGE0_SOURCE_SHA256,
            },
            "bridge_sha256": hashlib.sha256(
                _OCTAVE_BRIDGE_SOURCE.encode("utf-8")
            ).hexdigest(),
            "pfilter": _PDFB_PFILTER,
            "dfilter": _PDFB_DFILTER,
            "nlevels_coarse_to_fine": list(_PDFB_NLEVELS),
            "internal_level_order": "finest_to_coarsest",
            "coordinate_scheme": _PDFB_RANGE_SCHEME,
            "eligible_pyramid_levels_from_coarse": list(
                _PDFB_ELIGIBLE_LEVELS_FROM_COARSE
            ),
            "eligible_internal_levels": [0, 1],
            "eligible_coordinate_bands": [
                item[0] for item in _PDFB_COORDINATE_BANDS
            ],
            "dense_222360_selection": (
                "all P4 coordinates plus first 8584 coordinates "
                "of each P3 band"
            ),
            "mat_transport": "scipy_mat_v5_numeric_vectors_fortran_order",
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
        yield "P0:LOWPASS", coefficients.lowpass
        for level in reversed(range(len(coefficients.details))):
            pyramid_level = self.config.levels - level
            for direction, band in enumerate(coefficients.details[level]):
                virtual_id = next(
                    (
                        band_id
                        for band_id, item_level, item_direction, _shape
                        in _PDFB_COORDINATE_BANDS
                        if item_level == level and item_direction == direction
                    ),
                    None,
                )
                yield virtual_id or f"P{pyramid_level}:D{direction}", band


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

    def apply_eligible_perturbation(
        self,
        coefficients: PyramidCoefficients,
        perturbation: tuple[np.ndarray, ...],
        *,
        strength: float,
    ) -> PyramidCoefficients: ...

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
    if cfg.transform_profile == OctavePdfbTransformAdapter.profile_name:
        return OctavePdfbTransformAdapter(cfg)
    raise ValueError(f"no adapter for transform profile {cfg.transform_profile!r}")
