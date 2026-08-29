from __future__ import annotations

import math


def delta_e_rgb(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Return the Euclidean distance between two RGB triples scaled to ΔE units.

    RGB values are assumed to be normalised to the 0--1 range.  The result is
    multiplied by 100 so that a just-noticeable colour difference is in the low
    single digits, matching the ΔE < 5 threshold in TRD §3.11 / FR-1101.
    """
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True))) * 100.0
