"""Exact digital-only attack profiles with explicit uint8 boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ctsteg import attacks as legacy_attacks

from .preprocessing import half_up_uint8
from .types import UInt8Image


@dataclass(frozen=True)
class DigitalAttack:
    name: str
    parameter: str
    value: float | int
    apply: Callable[[UInt8Image], UInt8Image]


def jpeg(image: UInt8Image, *, quality: int) -> UInt8Image:
    return half_up_uint8(legacy_attacks.jpeg_compression(image, quality=quality))


def gaussian(
    image: UInt8Image,
    *,
    variance: float,
    seed: int,
) -> UInt8Image:
    attacked = legacy_attacks.gaussian_noise(
        image,
        variance=variance,
        seed=seed,
    )
    return half_up_uint8(attacked)


def salt_and_pepper(
    image: UInt8Image,
    *,
    density: float,
    seed: int,
) -> UInt8Image:
    attacked = legacy_attacks.salt_and_pepper_noise(
        image,
        density=density,
        seed=seed,
    )
    return half_up_uint8(attacked)


def pilot_attacks(seed: int) -> tuple[DigitalAttack, ...]:
    return (
        DigitalAttack(
            "jpeg",
            "quality",
            70,
            lambda image: jpeg(image, quality=70),
        ),
        DigitalAttack(
            "gaussian",
            "variance",
            10.0,
            lambda image: gaussian(image, variance=10.0, seed=seed),
        ),
    )


def calibration_attacks(seed: int) -> tuple[DigitalAttack, ...]:
    return (
        *pilot_attacks(seed),
        DigitalAttack(
            "salt_and_pepper",
            "density",
            0.03,
            lambda image: salt_and_pepper(image, density=0.03, seed=seed),
        ),
    )


def final_attack_suite(seed: int) -> tuple[DigitalAttack, ...]:
    attacks: list[DigitalAttack] = []
    for quality in (90, 70, 50):
        attacks.append(
            DigitalAttack(
                "jpeg",
                "quality",
                quality,
                lambda image, quality=quality: jpeg(image, quality=quality),
            )
        )
    for variance in (5.0, 10.0, 15.0):
        attacks.append(
            DigitalAttack(
                "gaussian",
                "variance",
                variance,
                lambda image, variance=variance: gaussian(
                    image,
                    variance=variance,
                    seed=seed,
                ),
            )
        )
    for density in (0.01, 0.03, 0.05):
        attacks.append(
            DigitalAttack(
                "salt_and_pepper",
                "density",
                density,
                lambda image, density=density: salt_and_pepper(
                    image,
                    density=density,
                    seed=seed,
                ),
            )
        )
    return tuple(attacks)
