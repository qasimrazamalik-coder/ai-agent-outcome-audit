# AI Agent Outcome Audit

Support bots report **containment**: the customer never reached a human. That says
nothing about whether the problem was solved. This project measures what the bot
actually resolves, driver by driver, what false "success" costs in repeat contacts and
churn, and which drivers should skip the bot.

[![ci](https://github.com/qasimrazamalik-coder/ai-agent-outcome-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/qasimrazamalik-coder/ai-agent-outcome-audit/actions/workflows/ci.yml)

> **The data is simulated.** It comes from the fictional Northwind Connect operation
> built by [cx-journey-warehouse](https://github.com/qasimrazamalik-coder/cx-journey-warehouse)
> (Jan to Jun 2025, about 21,000 bot sessions a year). The effects are planted, including
> a churn penalty for false containment; the point is the method that finds and prices them.

## Answer

| | |
|---|---|
| Vendor-reported containment | **85%** |
| True resolution (no repeat contact or ticket on the same driver within 7 days) | **60%** (95% CI 59% to 61%) |
| Sessions a year counted as success where the customer was not helped | **about 5,150** |
| Extra 30-day churn after a false containment, within the same driver | **+2.4 pts** (95% CI +0.7 to +4.1) |

**Recommendation:** route *Proration after plan change* and *Refund status* straight to
agents (**about $18,900 a year**). Test five more drivers on half their traffic before
switching, because their case depends on the size of the churn effect. Keep the bot on
password resets, status checks and card updates, where it really works. Change the
vendor's scorecard from containment to true resolution.

Full one-page memo: [reports/bot_outcome_audit.md](reports/bot_outcome_audit.md)

![Containment vs true resolution by driver](reports/charts/containment_vs_true_resolution.png)

## How it works

```
cx-journey-warehouse (attached read-only)      this repo
  marts.fct_contacts      ─┐                   dbt models          bot_sessions, agent_contacts,
  marts.dim_contact_driver ├─► dbt (DuckDB) ─►                     driver_outcomes, churn_by_outcome,
  marts.dim_customer      ─┘                                       proxy_validation, customer_value
                                               audit/ (Python)     Wilson intervals, Mantel-Haenszel
                                                                   churn difference, cost model
                                               reports/            memo, charts, results.json
                                               app/                Streamlit what-if view
```

**1. Outcome, not activity.** A bot session is truly resolved only if the bot contained
it and the customer did not come back about the same driver, or open a ticket, within
7 days. The definition lives in the upstream warehouse's governed layer, so this audit
and every dashboard use the same one.

**2. Uncertainty on every rate.** Each driver's true resolution carries a 95% Wilson
interval, so small drivers don't drive decisions on noise.

**3. Churn measured within driver.** Some drivers (cancellations, disputes) churn more
whatever the bot does. Comparing falsely contained and truly resolved customers inside
each driver (Mantel-Haenszel risk difference) removes that mix effect. The crude,
unstratified number would overstate it.

**4. A cost model you can trace.** For each driver, the expected cost to resolve one issue:

- bot first = bot session cost + (1 − bot true resolution) × agent journey cost
- agent direct = agent cost per contact ÷ agent FCR
- each path also pays for its churn risk: unresolved share × churn uplift × customer value

Churn only counts if its effect is statistically different from zero. A recommendation
that flips at the low end of the churn interval is marked "test first", not "switch".
Every assumption is in [`config/assumptions.yml`](config/assumptions.yml), and the memo
shows a sensitivity table across bot price and customer lifetime.

**5. The measurement is validated.** Because the data is simulated, each issue's true
outcome is known. The repeat-contact proxy classifies 87.8% of contained sessions
correctly, and its errors run one way: 1,006 customers gave up without contacting again
and look resolved. Measured resolution of contained sessions is 70.9% against a true
59.4%, so the real gap is **larger** than reported and the recommendations are
conservative.

![Annual value by driver](reports/charts/value_by_driver.png)

## Run it

Needs Python 3.11+ and git.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_audit.py --bootstrap          # clones and builds the warehouse, then runs the audit
python scripts/run_audit.py --bootstrap --scale 0.25   # faster, smaller data
pytest -q                                        # statistics and cost-model tests
```

Interactive view (sliders re-run the cost model live):

```bash
pip install -r requirements-app.txt
streamlit run app/streamlit_app.py
```

Already have the warehouse checked out? `python scripts/bootstrap_warehouse.py --repo ../cx-journey-warehouse`.

## Tests

- `pytest`: Wilson interval against reference values, the stratified difference recovers
  a known effect that the crude difference overstates, cost-model formulas and routing rules.
- `dbt build`: keys unique, per-driver counts reconcile to the session total, true
  resolution never exceeds containment, proxy accuracy within [0, 1].
- CI builds the upstream warehouse from scratch and runs everything on every push.

## Limits

- The churn comparison is observational. Stratifying by driver removes the obvious
  confounder, not every one, which is why borderline drivers get an A/B test, not a switch.
- Agent-direct figures come from customers who chose to call; chat users may differ.
- Silent failures (customers who give up) look resolved to any repeat-based measure; the
  30-day churn signal is how they still show up.

## Stack

Python (pandas, matplotlib) · dbt-core 1.11 · DuckDB · Streamlit · GitHub Actions

## Related projects

- [cx-journey-warehouse](https://github.com/qasimrazamalik-coder/cx-journey-warehouse): the governed warehouse this audit runs on.
- [governed-ai-analyst-benchmark](https://github.com/qasimrazamalik-coder/governed-ai-analyst-benchmark): an LLM writing raw SQL vs an LLM limited to governed metrics.
