"""AP/GP/HP pixel mapping reconstructed from Algorithms 1 and 4.

This mapping is deterministic and keyless.  It is retained only to reproduce
the paper; it must not be described or deployed as modern cryptography.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


FloatImage = NDArray[np.float64]


def _validate_grayscale(image: ArrayLike) -> FloatImage:
    array = np.asarray(image, dtype=np.float64)
    if array.ndim != 2:
        raise ValueError("expected a two-dimensional grayscale image")
    if not np.isfinite(array).all():
        raise ValueError("image contains NaN or infinity")
    if array.min() < 0 or array.max() > 255:
        raise ValueError("pixel values must be within [0, 255]")
    return array


def _masks(image: FloatImage) -> tuple[NDArray[np.bool_], NDArray[np.bool_]]:
    rows, cols = np.indices(image.shape)
    even_position = (rows + cols) % 2 == 0
    # L1 = 1, 4, 7, ... .  Pixel membership is defined on integer intensities.
    integer_pixels = np.rint(image).astype(np.int16)
    in_l1 = (integer_pixels >= 1) & ((integer_pixels - 1) % 3 == 0)
    return even_position, in_l1


def encrypt_secret(image: ArrayLike, *, mode: str = "interpreted") -> FloatImage:
    """Apply the article's AP/GP/HP mapping without premature quantization.

    ``interpreted`` resolves the incomplete HP branch by applying the stated
    formula to every odd-parity pixel.  ``strict`` follows Algorithm 1's
    written L3 condition and raises when an odd-parity pixel is greater than
    32, because the paper specifies no output for that case.
    """

    source = _validate_grayscale(image)
    if mode not in {"interpreted", "strict"}:
        raise ValueError("mode must be 'interpreted' or 'strict'")

    even_position, in_l1 = _masks(source)
    odd_position = ~even_position
    if mode == "strict" and np.any(odd_position & (source > 32)):
        count = int(np.count_nonzero(odd_position & (source > 32)))
        raise ValueError(
            "Algorithm 1 leaves CODE_HP undefined for "
            f"{count} odd-parity pixels above 32"
        )

    encrypted = np.empty_like(source)

    gp = even_position & in_l1
    ap = even_position & ~in_l1
    encrypted[gp] = source[gp] / 8.0

    # Within [0, 255], L1 and L2 contain the same residue class modulo 3.
    # Consequently, the N/4 + 193 AP branch is unreachable after the outer
    # "not in L1" condition.  The reachable AP formula is retained here.
    encrypted[ap] = source[ap] / 10.0 + 50.0

    hp = odd_position
    encrypted[hp] = (2.0 * source[hp]) / (1.0 + source[hp])
    return encrypted


def decrypt_secret(
    encrypted: ArrayLike,
    *,
    stabilize_hp: bool = True,
    clip_output: bool = True,
) -> FloatImage:
    """Invert the interpreted AP/GP/HP mapping.

    Noise can push HP values to or beyond its singular point at 2.  The paper
    gives no handling rule.  ``stabilize_hp=True`` clips that branch just below
    2 and records a defensible, deterministic robustness convention.
    """

    values = np.asarray(encrypted, dtype=np.float64)
    if values.ndim != 2:
        raise ValueError("expected a two-dimensional encrypted image")
    if not np.isfinite(values).all():
        raise ValueError("encrypted image contains NaN or infinity")

    rows, cols = np.indices(values.shape)
    even_position = (rows + cols) % 2 == 0
    odd_position = ~even_position

    recovered = np.empty_like(values)
    gp = even_position & (values >= 0.0) & (values <= 32.0)
    ap_high = even_position & (values >= 193.0)
    ap_low = even_position & ~gp & ~ap_high

    recovered[gp] = values[gp] * 8.0
    recovered[ap_high] = 4.0 * (values[ap_high] - 193.0)
    recovered[ap_low] = 10.0 * (values[ap_low] - 50.0)

    hp_values = values[odd_position]
    if stabilize_hp:
        hp_values = np.clip(hp_values, 0.0, 2.0 - 1e-6)
    denominator = 2.0 - hp_values
    if np.any(np.abs(denominator) < 1e-12):
        raise ValueError("inverse HP mapping is singular at encrypted value 2")
    recovered[odd_position] = hp_values / denominator

    if clip_output:
        recovered = np.clip(recovered, 0.0, 255.0)
    return recovered


def pseudocode_reachability() -> dict[str, object]:
    """Return machine-checkable facts about Algorithm 1's pixel-domain lists."""

    l1 = {value for value in range(1, 513, 3) if value <= 255}
    l2 = {value for value in range(511, -1, -3) if value <= 255}
    return {
        "l1_pixel_values": sorted(l1),
        "l2_pixel_values": sorted(l2),
        "l1_equals_l2_on_uint8_domain": l1 == l2,
        "ap_high_branch_reachable_after_not_in_l1": bool(l2 - l1),
    }

