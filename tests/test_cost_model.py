import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit.cost_model import DriverEconomics, agent_direct_cost, bot_first_cost, evaluate  # noqa: E402


def test_agent_direct_cost_is_cost_over_fcr():
    assert agent_direct_cost(4.0, 0.8) == pytest.approx(5.0)


def test_bot_first_cost():
    # $0.85 bot, resolves 60%, otherwise an agent journey costing $5.
    assert bot_first_cost(0.85, 0.6, 5.0) == pytest.approx(0.85 + 0.4 * 5.0)


def test_high_resolution_driver_stays_on_bot():
    d = DriverEconomics("ACC_PWD_RESET", 1000, 0.9, 0.05, 4.0, 0.9)
    r = evaluate(d, 0.85, churn_uplift=0.01, customer_value=1200)
    assert r.recommendation == "keep on bot"
    assert r.annual_value_of_switching < 0


def test_low_resolution_driver_with_churn_goes_to_agent():
    d = DriverEconomics("BIL_DISPUTE", 1000, 0.35, 0.5, 5.0, 0.75)
    r = evaluate(d, 0.85, churn_uplift=0.02, customer_value=1200)
    assert r.recommendation == "route to agent"
    assert r.annual_value_of_switching > 0


def test_negative_churn_uplift_is_ignored():
    d = DriverEconomics("X", 100, 0.5, 0.4, 5.0, 0.8)
    r = evaluate(d, 0.85, -0.05, 1000)
    assert r.churn_cost_per_bot_session == 0 and r.churn_cost_per_agent_journey == 0


def test_churn_is_charged_to_both_paths():
    # Bot leaves 10% falsely contained, agents leave 15% unresolved: churn favours the bot.
    d = DriverEconomics("ORD_DELIVERY", 1000, 0.85, 0.10, 3.0, 0.85)
    r = evaluate(d, 0.85, churn_uplift=0.03, customer_value=1200)
    assert r.churn_cost_per_bot_session == pytest.approx(0.10 * 0.03 * 1200)
    assert r.churn_cost_per_agent_journey == pytest.approx(0.15 * 0.03 * 1200)
    assert r.recommendation == "keep on bot"


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        agent_direct_cost(4.0, 0)
    with pytest.raises(ValueError):
        bot_first_cost(0.85, 1.5, 5.0)
