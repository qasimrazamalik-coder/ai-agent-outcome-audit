"""Interactive view of the bot outcome audit.

    pip install -r requirements-app.txt
    streamlit run app/streamlit_app.py

Reads reports/results.json (written by scripts/run_audit.py). The sliders re-run the
cost model live, so you can see how the routing recommendation moves with each assumption.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audit.cost_model import DriverEconomics, evaluate  # noqa: E402

st.set_page_config(page_title="Bot outcome audit", layout="wide")
results = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
h = results["headline"]
drivers = pd.DataFrame(results["drivers"])

st.title("Bot outcome audit")
st.caption("Simulated data (fictional Northwind Connect, Jan to Jun 2025). "
           "Containment = the vendor's number. True resolution = no repeat contact or ticket on the same driver within 7 days.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Vendor containment", f"{h['vendor_containment']:.0%}")
c2.metric("True resolution", f"{h['true_resolution']:.0%}",
          delta=f"{(h['true_resolution'] - h['vendor_containment']) * 100:.0f} pts vs containment", delta_color="inverse")
c3.metric("Falsely contained / year", f"{h['false_contained_per_year']:,.0f}")
up = h["churn_uplift_within_driver"]
c4.metric("30-day churn uplift", f"{up['estimate'] * 100:+.1f} pts", help=f"95% CI {up['low'] * 100:+.1f} to {up['high'] * 100:+.1f}")

st.subheader("Try the assumptions")
s1, s2, s3 = st.columns(3)
bot_cost = s1.slider("Bot cost per session (USD)", 0.25, 2.0, float(results["assumptions"]["bot_cost_per_session_usd"]), 0.05)
lifetime = s2.slider("Remaining customer lifetime (months)", 6, 48, int(results["assumptions"]["remaining_customer_lifetime_months"]))
uplift = s3.slider("Churn uplift from false containment (pts)", 0.0, 5.0, max(up["estimate"] * 100, 0.0), 0.1) / 100

rows = []
for r in drivers.itertuples():
    econ = DriverEconomics(r.intent_code, r.bot_sessions_per_year, r.true_resolution, r.false_containment_rate,
                           r.agent_cost_per_contact, r.agent_fcr)
    res = evaluate(econ, bot_cost, uplift, h["avg_mrr_usd"] * lifetime)
    rec = res.recommendation
    if r.bot_sessions < results["assumptions"]["min_sessions_per_driver"]:
        rec = "insufficient volume"
    elif r.intent_code == "UNCLASSIFIED":
        rec = "improve intent recognition"
    rows.append({
        "Driver": r.driver.split(" > ")[-1],
        "Bot sessions / yr": round(r.bot_sessions_per_year),
        "Containment": r.containment,
        "True resolution": r.true_resolution,
        "Falsely contained / yr": round(r.false_contained_per_year),
        "Cost: bot first": res.cost_bot_first,
        "Cost: agent direct": res.cost_agent_direct,
        "Total: bot first": res.total_bot_first,
        "Total: agent direct": res.total_agent_direct,
        "Recommendation": rec,
        "Annual value of switching": res.annual_value_of_switching if rec == "route to agent" else 0.0,
    })
table = pd.DataFrame(rows).sort_values("Falsely contained / yr", ascending=False)
switch = table[table["Recommendation"] == "route to agent"]
st.metric("Annual value of routing changes (point estimate)", f"${switch['Annual value of switching'].sum():,.0f}",
          help=f"{len(switch)} drivers where routing straight to an agent pays at these settings")
st.dataframe(
    table.style.format({
        "Containment": "{:.0%}", "True resolution": "{:.0%}", "Cost: bot first": "${:,.2f}",
        "Cost: agent direct": "${:,.2f}", "Total: bot first": "${:,.2f}", "Total: agent direct": "${:,.2f}",
        "Annual value of switching": "${:,.0f}",
        "Bot sessions / yr": "{:,}", "Falsely contained / yr": "{:,}",
    }),
    width="stretch", hide_index=True,
)

st.subheader("Charts")
st.image(str(ROOT / "reports" / "charts" / "containment_vs_true_resolution.png"))
st.image(str(ROOT / "reports" / "charts" / "value_by_driver.png"))
