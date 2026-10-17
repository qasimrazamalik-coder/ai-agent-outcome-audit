import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit.stats import risk_difference, stratified_risk_difference, wilson  # noqa: E402


def test_wilson_matches_reference_values():
    # Reference: 81 successes out of 263 -> 0.308, 95% Wilson CI (0.255, 0.366).
    ci = wilson(81, 263)
    assert ci.estimate == pytest.approx(0.30798, abs=1e-4)
    assert ci.low == pytest.approx(0.2553, abs=1e-3)
    assert ci.high == pytest.approx(0.3662, abs=1e-3)


def test_wilson_stays_inside_zero_one():
    assert wilson(0, 10).low == 0.0
    assert wilson(10, 10).high == 1.0
    assert math.isnan(wilson(0, 0).estimate)


def test_wilson_rejects_impossible_counts():
    with pytest.raises(ValueError):
        wilson(11, 10)


def test_risk_difference_sign_and_width():
    d = risk_difference(30, 100, 10, 100)
    assert d.estimate == pytest.approx(0.20)
    assert d.low < 0.20 < d.high


def test_stratified_difference_removes_confounding_by_mix():
    # Within each stratum the exposed group churns 5 points more, but the exposed group
    # is concentrated in the high-churn stratum. The crude difference overstates it;
    # the stratified estimate recovers 5 points.
    strata = [(120, 400, 25, 100),  # high-churn driver: 30% vs 25%
              (6, 100, 4, 400)]     # low-churn driver: 6% vs 1%
    crude = risk_difference(126, 500, 29, 500)
    adjusted = stratified_risk_difference(strata)
    assert crude.estimate > 0.15
    assert adjusted.estimate == pytest.approx(0.05, abs=1e-9)
