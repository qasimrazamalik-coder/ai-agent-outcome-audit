"""Turn the audit tables into rates with confidence intervals, a cost model per driver,
charts, a one-page report and results.json (read by the Streamlit app)."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from .charts import containment_vs_resolution_chart, value_by_driver_chart
from .cost_model import DriverEconomics, evaluate
from .stats import risk_difference, stratified_risk_difference, wilson


def _load(db: Path) -> dict[str, pd.DataFrame]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return {
            name: con.execute(f"select * from results.{name}").fetchdf()
            for name in ["driver_outcomes", "churn_by_outcome", "proxy_validation", "customer_value"]
        }
    finally:
        con.close()


def churn_effect(churn: pd.DataFrame, confidence: float) -> dict:
    strata = []
    totals = {"falsely contained": [0, 0], "truly resolved": [0, 0]}
    for intent, grp in churn.groupby("intent_code"):
        rows = {r.outcome: (int(r.churned_30d), int(r.sessions)) for r in grp.itertuples()}
        if "falsely contained" in rows and "truly resolved" in rows:
            (x1, n1), (x2, n2) = rows["falsely contained"], rows["truly resolved"]
            strata.append((x1, n1, x2, n2))
        for k, (x, n) in rows.items():
            totals[k][0] += x
            totals[k][1] += n
    fx, fn = totals["falsely contained"]
    tx, tn = totals["truly resolved"]
    crude = risk_difference(fx, fn, tx, tn, confidence)
    adjusted = stratified_risk_difference(strata, confidence)
    return {
        "falsely_contained_churn": fx / fn if fn else None,
        "truly_resolved_churn": tx / tn if tn else None,
        "falsely_contained_sessions": fn,
        "truly_resolved_sessions": tn,
        "crude_difference": asdict(crude),
        "within_driver_difference": asdict(adjusted),
        "strata": len(strata),
    }


def driver_table(outcomes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    conf = cfg["confidence_level"]
    annualise = 12 / cfg["months_of_data"]
    # Fallback for drivers with too few agent-direct contacts: pooled agent figures.
    pooled_fcr = outcomes["agent_resolved"].sum() / outcomes["agent_observable"].sum()
    pooled_cost = (outcomes["agent_cost_per_contact_usd"] * outcomes["agent_contacts"]).sum() / outcomes["agent_contacts"].sum()
    rows = []
    for r in outcomes.itertuples():
        tr = wilson(int(r.bot_true_resolved), int(r.bot_observable), conf)
        uses_pooled = r.agent_observable < 30 or pd.isna(r.agent_cost_per_contact_usd)
        fcr = pooled_fcr if uses_pooled else r.agent_resolved / r.agent_observable
        cost = (pooled_cost if uses_pooled else r.agent_cost_per_contact_usd) / cfg["agent_occupancy"]
        rows.append({
            "intent_code": r.intent_code,
            "driver": r.driver_path if isinstance(r.driver_path, str) else r.intent_code,
            "driver_l1": r.driver_l1,
            "upstream_owner": r.upstream_owner,
            "is_avoidable": bool(r.is_avoidable) if pd.notna(r.is_avoidable) else False,
            "bot_sessions": int(r.bot_sessions),
            "bot_sessions_per_year": r.bot_sessions * annualise,
            "containment": r.bot_contained / r.bot_sessions,
            "true_resolution": tr.estimate,
            "true_resolution_low": tr.low,
            "true_resolution_high": tr.high,
            "false_containment_rate": r.bot_false_contained / r.bot_observable if r.bot_observable else 0.0,
            "false_contained_per_year": r.bot_false_contained / max(r.bot_observable, 1) * r.bot_sessions * annualise,
            "agent_fcr": fcr,
            "agent_cost_per_contact": cost,
            "agent_figures_pooled": uses_pooled,
        })
    df = pd.DataFrame(rows)
    df["containment_gap"] = df["containment"] - df["true_resolution"]
    return df.sort_values("false_contained_per_year", ascending=False).reset_index(drop=True)


def apply_cost_model(df: pd.DataFrame, cfg: dict, uplift: float, customer_value: float,
                     c_bot: float | None = None) -> pd.DataFrame:
    c_bot = cfg["bot_cost_per_session_usd"] if c_bot is None else c_bot
    out = []
    for r in df.itertuples():
        econ = DriverEconomics(r.intent_code, r.bot_sessions_per_year, r.true_resolution,
                               r.false_containment_rate, r.agent_cost_per_contact, r.agent_fcr)
        res = evaluate(econ, c_bot, uplift, customer_value)
        rec = res.recommendation
        if r.bot_sessions < cfg["min_sessions_per_driver"]:
            rec = "insufficient volume"
        elif r.intent_code == "UNCLASSIFIED":
            rec = "improve intent recognition"
        out.append({
            "intent_code": r.intent_code,
            "cost_bot_first": res.cost_bot_first,
            "cost_agent_direct": res.cost_agent_direct,
            "churn_cost_per_bot_session": res.churn_cost_per_bot_session,
            "churn_cost_per_agent_journey": res.churn_cost_per_agent_journey,
            "total_bot_first": res.total_bot_first,
            "total_agent_direct": res.total_agent_direct,
            "annual_value_of_switching": res.annual_value_of_switching,
            "recommendation": rec,
        })
    return df.merge(pd.DataFrame(out), on="intent_code")


def run_analysis(db: Path, assumptions: Path, out_dir: Path) -> dict:
    cfg = yaml.safe_load(assumptions.read_text(encoding="utf-8"))
    t = _load(db)
    conf = cfg["confidence_level"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "charts").mkdir(exist_ok=True)

    outcomes = t["driver_outcomes"]
    mrr = float(t["customer_value"]["avg_mrr_usd"].iloc[0])
    customer_value = mrr * cfg["remaining_customer_lifetime_months"]
    churn = churn_effect(t["churn_by_outcome"], conf)
    uplift = churn["within_driver_difference"]

    drivers = driver_table(outcomes, cfg)
    churn_significant = uplift["low"] > 0
    basis_uplift = uplift["estimate"] if churn_significant else 0.0
    main = apply_cost_model(drivers, cfg, basis_uplift, customer_value)
    lower = apply_cost_model(drivers, cfg, max(uplift["low"], 0.0), customer_value)
    cost_only = apply_cost_model(drivers, cfg, 0.0, customer_value)
    main["robust_at_low_churn_bound"] = main["recommendation"].values == lower["recommendation"].values
    main["recommendation_cost_only"] = cost_only["recommendation"].values

    total = wilson(int(outcomes["bot_true_resolved"].sum()), int(outcomes["bot_observable"].sum()), conf)
    containment = outcomes["bot_contained"].sum() / outcomes["bot_sessions"].sum()
    annualise = 12 / cfg["months_of_data"]
    switch = main[main["recommendation"] == "route to agent"]
    firm = switch[switch["robust_at_low_churn_bound"]]
    test_first = switch[~switch["robust_at_low_churn_bound"]]
    fix = main[main["recommendation"] == "keep on bot, fix the flow"]

    pv = t["proxy_validation"]
    proxy = {
        "measured_resolution_rate": float((pv["measured_resolution_rate"] * pv["contained_sessions"]).sum() / pv["contained_sessions"].sum()),
        "true_resolution_rate": float((pv["true_resolution_rate"] * pv["contained_sessions"]).sum() / pv["contained_sessions"].sum()),
        "proxy_accuracy": float((pv["proxy_accuracy"] * pv["contained_sessions"]).sum() / pv["contained_sessions"].sum()),
        "silent_failures": int(pv["silent_failures"].sum()),
        "contained_sessions": int(pv["contained_sessions"].sum()),
    }

    sensitivity = []
    for c_bot in cfg["sensitivity"]["bot_cost_per_session_usd"]:
        for months in cfg["sensitivity"]["remaining_customer_lifetime_months"]:
            s = apply_cost_model(drivers, cfg, basis_uplift, mrr * months, c_bot=c_bot)
            chosen = s[s["recommendation"] == "route to agent"]
            sensitivity.append({
                "bot_cost_per_session_usd": c_bot, "remaining_lifetime_months": months,
                "drivers_to_route_to_agent": int(len(chosen)),
                "annual_value_usd": float(chosen["annual_value_of_switching"].sum()),
            })

    headline = {
        "bot_sessions_per_year": float(outcomes["bot_sessions"].sum() * annualise),
        "vendor_containment": float(containment),
        "true_resolution": float(total.estimate),
        "true_resolution_ci": [float(total.low), float(total.high)],
        "false_contained_per_year": float(main["false_contained_per_year"].sum()),
        "churn_uplift_within_driver": uplift,
        "churn_effect_significant": churn_significant,
        "recommendation_basis": "cost + churn" if churn_significant else "cost only",
        "drivers_to_route_to_agent": firm["intent_code"].tolist(),
        "annual_value_of_routing_change_usd": float(firm["annual_value_of_switching"].sum()),
        "drivers_to_test_first": test_first["intent_code"].tolist(),
        "annual_value_to_test_usd": float(test_first["annual_value_of_switching"].sum()),
        "drivers_to_fix": fix["intent_code"].tolist(),
        "avg_mrr_usd": mrr,
        "customer_value_usd": customer_value,
    }
    results = {
        "generated": date.today().isoformat(),
        "assumptions": cfg,
        "headline": headline,
        "churn": churn,
        "proxy_validation": proxy,
        "proxy_by_driver": pv.to_dict(orient="records"),
        "drivers": main.to_dict(orient="records"),
        "sensitivity": sensitivity,
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    containment_vs_resolution_chart(main, out_dir / "charts" / "containment_vs_true_resolution.png")
    value_by_driver_chart(main, out_dir / "charts" / "value_by_driver.png")
    from .report import write_report
    write_report(results, main, out_dir / "bot_outcome_audit.md")
    return results
