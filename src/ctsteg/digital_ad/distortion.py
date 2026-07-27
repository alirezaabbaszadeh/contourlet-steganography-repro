"""PSNR-constrained binary search after inverse transform and quantization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ctsteg.metrics import psnr

from .config import DigitalADConfig
from .preprocessing import half_up_uint8
from .types import UInt8Image


@dataclass(frozen=True)
class LambdaTrial:
    strength: float
    psnr_db: float
    feasible: bool


@dataclass(frozen=True)
class LambdaSearchResult:
    strength: float
    stego: UInt8Image
    psnr_db: float
    trials: tuple[LambdaTrial, ...]
    lower_bound: float
    upper_bound: float
    iterations: int
    upper_bound_feasible: bool


def search_lambda(
    cover: UInt8Image,
    renderer: Callable[[float], np.ndarray],
    config: DigitalADConfig,
) -> LambdaSearchResult:
    cfg = config.validate()
    cover_values = np.asarray(cover, dtype=np.uint8)
    trials: list[LambdaTrial] = []

    def evaluate(strength: float) -> tuple[UInt8Image, float, bool]:
        stego = half_up_uint8(renderer(strength))
        quality = psnr(cover_values, stego)
        feasible = quality >= cfg.psnr_target_db
        trials.append(LambdaTrial(strength, quality, feasible))
        return stego, quality, feasible

    low = cfg.lambda_low
    high = cfg.lambda_high
    low_stego, low_psnr, low_feasible = evaluate(low)
    if not low_feasible:
        raise RuntimeError(
            "lambda_low violates the requested Cover-Stego PSNR constraint"
        )
    high_stego, high_psnr, high_feasible = evaluate(high)
    if high_feasible:
        return LambdaSearchResult(
            strength=high,
            stego=high_stego,
            psnr_db=high_psnr,
            trials=tuple(trials),
            lower_bound=cfg.lambda_low,
            upper_bound=cfg.lambda_high,
            iterations=0,
            upper_bound_feasible=True,
        )
    best_strength = low
    best_stego = low_stego
    best_psnr = low_psnr
    completed = 0
    for _ in range(cfg.lambda_iterations):
        completed += 1
        midpoint = (low + high) / 2.0
        stego, quality, feasible = evaluate(midpoint)
        if feasible:
            low = midpoint
            best_strength = midpoint
            best_stego = stego
            best_psnr = quality
        else:
            high = midpoint
        if abs(quality - cfg.psnr_target_db) <= cfg.psnr_tolerance_db:
            # Continue searching toward the largest feasible point; quantized
            # plateaus make strength tolerance less meaningful than PSNR.
            continue
    final_stego, final_psnr, final_feasible = evaluate(best_strength)
    if not final_feasible:
        raise AssertionError("final lambda no longer satisfies the PSNR target")
    return LambdaSearchResult(
        strength=best_strength,
        stego=final_stego,
        psnr_db=final_psnr,
        trials=tuple(trials),
        lower_bound=cfg.lambda_low,
        upper_bound=cfg.lambda_high,
        iterations=completed,
        upper_bound_feasible=False,
    )
