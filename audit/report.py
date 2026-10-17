"""One-page Markdown report from results.json and the driver table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def usd(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def write_report(results: dict, drivers: pd.DataFrame, path: Path) -> None:
    h = results["headline"]
    ch = results["churn"]
    px = results["proxy_validation"]
    cfg = results["assumptions"]
    up = ch["within_driver_difference"]
    acted = drivers[drivers["recommendation"].isin(["route to agent", "keep on bot, fix the flow"])]

    lines = [
        "# Bot outcome audit",
        "",
        f"Generated {results['generated']}. Data: the fictional Northwind Connect operation simulated by "
        "[cx-journey-warehouse](https://github.com/qasimrazamalik-coder/cx-journey-warehouse), Jan to Jun 2025. "
        "All figures are reproducible with `python scripts/run_audit.py --bootstrap`.",
        "",
        "## Answer",
        "",
        f"The bot vendor reports **{pct(h['vendor_containment'])} containment**. Judged by what customers did next, "
        f"the bot truly resolves **{pct(h['true_resolution'])}** of sessions "
        f"(95% CI {pct(h['true_resolution_ci'][0])} to {pct(h['true_resolution_ci'][1])}). "
        f"That is about **{h['false_contained_per_year']:,.0f} sessions a year** counted as success where the customer "
        "was not helped.",
        "",
    ]
    if up["low"] > 0:
        lines += [
            f"Falsely contained customers cancel more: within the same driver, 30-day churn is "
            f"**{up['estimate'] * 100:+.1f} points** higher (95% CI {up['low'] * 100:+.1f} to {up['high'] * 100:+.1f}) "
            "than for customers the bot really helped.",
            "",
        ]
    else:
        lines += [
            f"Churn after a false containment is {up['estimate'] * 100:+.1f} points versus a real resolution "
            f"(95% CI {up['low'] * 100:+.1f} to {up['high'] * 100:+.1f}): **not distinguishable from zero** in this "
            "data, so the cost-only view below is the one to act on.",
            "",
        ]
    names_of = lambda codes: ", ".join(  # noqa: E731
        drivers.set_index("intent_code").loc[codes, "driver"].str.split(" > ").str[-1])
    if h["drivers_to_route_to_agent"]:
        lines += [
            f"**Recommendation:** route {len(h['drivers_to_route_to_agent'])} drivers straight to an agent "
            f"({names_of(h['drivers_to_route_to_agent'])}): **{usd(h['annual_value_of_routing_change_usd'])} a year** "
            f"(basis: {h['recommendation_basis']}). These hold even at the low end of the churn estimate.",
            "",
        ]
    if h["drivers_to_test_first"]:
        lines += [
            f"Test before switching: {names_of(h['drivers_to_test_first'])} "
            f"({usd(h['annual_value_to_test_usd'])} a year at the point estimate). Their case depends on the size of "
            "the churn effect, so route half their traffic to agents for a month and measure.",
            "",
        ]
    lines += ["Keep the bot on the drivers it does solve: password reset, status checks, card updates.", ""]
    lines += [
        "![Containment vs true resolution](charts/containment_vs_true_resolution.png)",
        "",
        "## By driver",
        "",
        "Sorted by falsely contained sessions per year. Totals are the expected cost to resolve one issue, "
        "including the churn risk of leaving it unresolved on each path.",
        "",
        "| Driver | Bot sessions / yr | Containment | True resolution (95% CI) | Falsely contained / yr | Total: bot first | Total: agent direct | Recommendation | Annual value |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in drivers.itertuples():
        name = r.driver.split(" > ")[-1]
        flag = "" if r.robust_at_low_churn_bound else " *"
        lines.append(
            f"| {name} | {r.bot_sessions_per_year:,.0f} | {pct(r.containment)} | {pct(r.true_resolution)} "
            f"({pct(r.true_resolution_low)}-{pct(r.true_resolution_high)}) | {r.false_contained_per_year:,.0f} | "
            f"{usd(r.total_bot_first)} | {usd(r.total_agent_direct)} | "
            f"{r.recommendation}{flag} | {usd(r.annual_value_of_switching) if r.recommendation == 'route to agent' else '-'} |"
        )
    lines += [
        "",
        "\\* Recommendation changes if churn uplift is at the low end of its confidence interval.",
        "",
        "![Annual value by driver](charts/value_by_driver.png)",
        "",
        "## What to do",
        "",
    ]
    n = 1
    for r in acted.sort_values("annual_value_of_switching", ascending=False).itertuples():
        name = r.driver.split(" > ")[-1]
        if r.recommendation == "route to agent" and not r.robust_at_low_churn_bound:
            lines.append(f"{n}. **{name}: test routing to agents on half the traffic.** True resolution "
                         f"{pct(r.true_resolution)}; worth {usd(r.annual_value_of_switching)} a year only if the churn "
                         "effect holds. Owner: CX operations.")
        elif r.recommendation == "route to agent":
            lines.append(f"{n}. **{name}: skip the bot.** True resolution {pct(r.true_resolution)}; "
                         f"{r.false_contained_per_year:,.0f} customers a year leave thinking they were helped. "
                         f"Value {usd(r.annual_value_of_switching)} a year. Owner: CX operations (routing rules).")
        else:
            lines.append(f"{n}. **{name}: fix the flow.** {pct(r.false_containment_rate)} of sessions end contained "
                         "but unsolved. Add a \"did this solve it?\" check that hands off to an agent on \"no\". "
                         f"Upstream owner: {r.upstream_owner}.")
        n += 1
    lines += [
        f"{n}. **Change the vendor scorecard** from containment to true resolution (no repeat contact or ticket on "
        "the same driver within 7 days), reported by driver.",
        "",
        "## How good is the measurement?",
        "",
        "Because the data is simulated, the true outcome of every issue is known, so the repeat-contact proxy can be "
        "checked against it:",
        "",
        f"- Measured resolution of contained sessions: **{pct(px['measured_resolution_rate'], 1)}**; "
        f"true: **{pct(px['true_resolution_rate'], 1)}**.",
        f"- The proxy classifies {pct(px['proxy_accuracy'], 1)} of contained sessions correctly. Its errors run one way: "
        f"{px['silent_failures']:,} customers gave up without contacting again, so they look resolved.",
        "- So the true resolution gap is **larger** than reported here; every recommendation above is conservative.",
        "",
        "## Assumptions",
        "",
        "| Assumption | Value | Source |",
        "|---|---|---|",
        f"| Bot cost per session | {usd(cfg['bot_cost_per_session_usd'])} | Vendor contract (config/assumptions.yml) |",
        f"| Agent cost per contact | measured per driver | Handle time x loaded hourly rate (warehouse) / {cfg['agent_occupancy']:.0%} occupancy |",
        f"| Value of a lost customer | {usd(h['customer_value_usd'])} | Avg MRR {usd(h['avg_mrr_usd'])} x {cfg['remaining_customer_lifetime_months']} months |",
        f"| Churn uplift from false containment | {up['estimate'] * 100:+.2f} pts (used: {'yes' if h['churn_effect_significant'] else 'no, not significant'}) | Measured within driver (Mantel-Haenszel), {ch['strata']} drivers |",
        f"| Annualisation | x{12 / cfg['months_of_data']:.0f} | {cfg['months_of_data']} months of data |",
        "",
        "Sensitivity of the routing recommendation:",
        "",
        "| Bot cost per session | Customer lifetime (months) | Drivers to route to agent | Annual value |",
        "|---|---|---|---|",
    ]
    for s in results["sensitivity"]:
        lines.append(f"| {usd(s['bot_cost_per_session_usd'])} | {s['remaining_lifetime_months']} | "
                     f"{s['drivers_to_route_to_agent']} | {usd(s['annual_value_usd'])} |")
    lines += [
        "",
        "## Limits",
        "",
        "- Churn comparison is observational. Comparing within the same driver removes the obvious confounder "
        "(some drivers churn more), not every one. A routing change should be rolled out to half the traffic first "
        "and measured.",
        "- Agent-direct figures come from customers who chose to call. If they differ from chat users, the agent "
        "cost and resolution for the bot's traffic may differ.",
        "- Sessions whose driver the bot could not classify are reported separately; any next contact within 7 days "
        "counts as a repeat for them.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
