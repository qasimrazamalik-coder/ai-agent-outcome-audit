"""Small, dependency-free statistics used by the audit (tested in tests/test_stats.py)."""

from __future__ import annotations

import math
from dataclasses import dataclass

Z = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


@dataclass(frozen=True)
class Interval:
    estimate: float
    low: float
    high: float


def wilson(successes: int, n: int, confidence: float = 0.95) -> Interval:
    """Wilson score interval for a proportion. Well behaved near 0 and 1 and for small n."""
    if n <= 0:
        return Interval(float("nan"), float("nan"), float("nan"))
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    z = Z[confidence]
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def risk_difference(x1: int, n1: int, x2: int, n2: int, confidence: float = 0.95) -> Interval:
    """Difference of two proportions (p1 - p2) with a normal-approximation interval."""
    if n1 <= 0 or n2 <= 0:
        return Interval(float("nan"), float("nan"), float("nan"))
    p1, p2 = x1 / n1, x2 / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    z = Z[confidence]
    d = p1 - p2
    return Interval(d, d - z * se, d + z * se)


def stratified_risk_difference(strata: list[tuple[int, int, int, int]], confidence: float = 0.95) -> Interval:
    """Mantel-Haenszel risk difference across strata.

    Each stratum is (x1, n1, x2, n2): events and totals in the exposed and comparison
    groups. Comparing within strata (here: within the same contact driver) removes the
    bias from groups having different mixes of strata.
    """
    num = 0.0
    weight_total = 0.0
    var_num = 0.0
    for x1, n1, x2, n2 in strata:
        if n1 == 0 or n2 == 0:
            continue
        n = n1 + n2
        w = n1 * n2 / n
        p1, p2 = x1 / n1, x2 / n2
        num += w * (p1 - p2)
        weight_total += w
        # Sato's variance contribution, simplified form for the MH risk difference.
        var_num += (w ** 2) * (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    if weight_total == 0:
        return Interval(float("nan"), float("nan"), float("nan"))
    d = num / weight_total
    se = math.sqrt(var_num) / weight_total
    z = Z[confidence]
    return Interval(d, d - z * se, d + z * se)
