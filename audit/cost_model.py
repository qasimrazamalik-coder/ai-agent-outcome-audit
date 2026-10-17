"""Expected cost to resolve one issue, per contact driver, for two routing options.

Bot first:
    pay for the bot session; if the bot does not truly resolve the issue, the customer
    ends up with an agent anyway.
        C_bot_first = c_bot + (1 - r_bot) * C_agent

Agent direct:
    every agent attempt costs c_agent and resolves with probability fcr, so the expected
    number of agent contacts is 1 / fcr.
        C_agent = c_agent / fcr

Churn (charged to both paths, so neither gets a free pass):
    leaving a customer's issue unresolved raises 30-day churn by `churn_uplift`
    (measured within driver). Each lost customer costs MRR x remaining lifetime.
        bot path:   false_containment_rate * churn_uplift * customer_value
        agent path: (1 - fcr)              * churn_uplift * customer_value

The model is deliberately simple so every number in the recommendation can be traced
back to a measured rate and a stated assumption (config/assumptions.yml).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriverEconomics:
    intent_code: str
    bot_sessions_per_year: float
    bot_true_resolution: float  # r_bot
    false_containment_rate: float  # share of observable bot sessions contained but not resolved
    agent_cost_per_contact: float  # c_agent
    agent_fcr: float  # fcr


@dataclass(frozen=True)
class RoutingResult:
    intent_code: str
    cost_bot_first: float
    cost_agent_direct: float
    churn_cost_per_bot_session: float
    churn_cost_per_agent_journey: float
    total_bot_first: float
    total_agent_direct: float
    annual_value_of_switching: float
    recommendation: str


def agent_direct_cost(c_agent: float, fcr: float) -> float:
    if fcr <= 0:
        raise ValueError("fcr must be positive")
    return c_agent / fcr


def bot_first_cost(c_bot: float, r_bot: float, c_agent_direct: float) -> float:
    if not 0 <= r_bot <= 1:
        raise ValueError("r_bot must be a probability")
    return c_bot + (1 - r_bot) * c_agent_direct


def evaluate(d: DriverEconomics, c_bot: float, churn_uplift: float, customer_value: float) -> RoutingResult:
    c_agent = agent_direct_cost(d.agent_cost_per_contact, d.agent_fcr)
    c_bot_first = bot_first_cost(c_bot, d.bot_true_resolution, c_agent)
    uplift = max(churn_uplift, 0.0)
    churn_bot = uplift * d.false_containment_rate * customer_value
    churn_agent = uplift * (1 - d.agent_fcr) * customer_value
    total_bot = c_bot_first + churn_bot
    total_agent = c_agent + churn_agent
    value = (total_bot - total_agent) * d.bot_sessions_per_year
    if total_bot > total_agent:
        rec = "route to agent"
    elif d.false_containment_rate >= 0.25:
        rec = "keep on bot, fix the flow"
    else:
        rec = "keep on bot"
    return RoutingResult(d.intent_code, c_bot_first, c_agent, churn_bot, churn_agent, total_bot, total_agent, value, rec)
