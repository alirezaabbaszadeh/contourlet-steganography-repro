"""Machine-readable Stage-0 transform inventory and capacity audit."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import numpy as np

from .bitstream import TOTAL_BITS
from .config import DigitalADConfig
from .transform_adapter import make_transform_adapter


def deterministic_audit_image(size: int) -> np.ndarray:
    rows, columns = np.indices((size, size), dtype=np.uint32)
    return ((rows * 37 + columns * 19 + (rows * columns) % 251) % 256).astype(
        np.float64
    )


def _filter_inventory(config: DigitalADConfig, profile: str) -> dict[str, Any]:
    if profile == "haar_orthogonal_control_v1":
        return {
            "family": "separable_2d_haar",
            "analysis": "orthonormal 2x2 sum/difference",
            "synthesis": "exact inverse 2x2 sum/difference",
            "normalization": "1/2 in both analysis and synthesis",
            "boundary_mode": "exact non-overlapping even 2x2 blocks",
        }
    return {
        "family": "directional_laplacian_proxy",
        "pyramid": "Gaussian sigma followed by stride-2 subsampling",
        "gaussian_sigma": config.gaussian_sigma,
        "boundary_mode": "reflect",
        "prediction": "bilinear scipy.ndimage.zoom",
        "directional": "soft Fourier angular masks",
        "angular_concentration": config.angular_concentration,
    }


def audit_transform(config: DigitalADConfig) -> dict[str, Any]:
    cfg = config.validate()
    adapter = make_transform_adapter(cfg)
    image = deterministic_audit_image(cfg.cover_size)
    coefficients = adapter.analyze(image)
    reconstructed = adapter.synthesize(coefficients)
    difference = reconstructed - image
    all_bands = [
        {
            "band_id": band_id,
            "shape": [int(value) for value in band.shape],
            "coefficient_count": int(band.size),
        }
        for band_id, band in adapter.iter_all_bands(coefficients)
    ]
    eligible = adapter.descriptors(coefficients, eligible_only=True)
    candidate_count = sum(item.coefficient_count for item in eligible)
    total_coefficients = int(coefficients.coefficient_count)
    report: dict[str, Any] = {
        "schema": 1,
        "backend": adapter.backend_name,
        "profile": adapter.profile_name,
        "backend_version": adapter.backend_version,
        "transform_fingerprint": adapter.fingerprint(),
        "filters": _filter_inventory(cfg, adapter.profile_name),
        "levels": (
            1
            if adapter.profile_name == "haar_orthogonal_control_v1"
            else cfg.levels
        ),
        "directions_per_level": (
            [4]
            if adapter.profile_name == "haar_orthogonal_control_v1"
            else [cfg.directions] * cfg.levels
        ),
        "bands": all_bands,
        "eligible_level": cfg.eligible_level,
        "eligible_bands": [
            {
                "band_id": item.band_id,
                "shape": list(item.shape),
                "coefficient_count": item.coefficient_count,
            }
            for item in eligible
        ],
        "total_coefficients": total_coefficients,
        "candidate_coefficients": candidate_count,
        "required_slots": TOTAL_BITS,
        "capacity_sufficient": candidate_count >= TOTAL_BITS,
        "unused_candidate_slots": candidate_count - TOTAL_BITS,
        "candidate_utilization": TOTAL_BITS / candidate_count,
        "perfect_reconstruction": {
            "max_abs_error": float(np.max(np.abs(difference))),
            "mse": float(np.mean(np.square(difference))),
            "rmse": float(np.sqrt(np.mean(np.square(difference)))),
        },
        "input_coefficients": int(image.size),
        "redundancy_ratio": total_coefficients / image.size,
        "sampling": (
            "critically_sampled"
            if adapter.profile_name == "haar_orthogonal_control_v1"
            else "redundant"
        ),
        "paper_difference": (
            "This is an orthonormal engineering control, not a Contourlet or "
            "the authors' PDFB."
            if adapter.profile_name == "haar_orthogonal_control_v1"
            else "This is the documented Python contourlet-style proxy, not "
            "the authors' undisclosed LPDFB/PDFB configuration."
        ),
        "human_gate_required_for_transform_change": True,
    }
    if not report["capacity_sufficient"]:
        raise ValueError(
            f"candidate pool has {candidate_count} coefficients but "
            f"{TOTAL_BITS} are required"
        )
    return report


def write_transform_audit(
    output: str | Path,
    config: DigitalADConfig,
) -> dict[str, Any]:
    destination = Path(output)
    if destination.exists() and destination.stat().st_size:
        raise FileExistsError(f"refusing to replace non-empty audit: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = audit_transform(config)
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return report
