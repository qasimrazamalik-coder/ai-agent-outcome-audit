-- Grain: one row per contact that started with the bot.
-- Outcome flags come from the warehouse's outcome-based definitions (no repeat contact
-- or ticket on the same driver within 7 days). Only observable sessions (at least 7
-- days old, customer known) are used for rates.
select
    c.session_id,
    c.customer_key,
    c.contact_date,
    c.intent_code,
    d.driver_l1,
    d.driver_path,
    d.is_avoidable,
    d.upstream_owner,
    c.is_bot_contained,
    c.is_bot_escalated,
    c.is_resolved,
    c.has_repeat_contact,
    c.has_follow_up_ticket,
    c.is_resolution_eligible and c.is_outcome_observable          as is_observable,
    c.is_churn_observable,
    c.cancelled_within_30d,
    c.agent_cost_usd,
    c.bot_cost_usd,
    c.cost_to_serve_usd,
    -- The vendor calls it contained; the customer's next move says it was not solved.
    c.is_bot_contained and not c.is_resolved                     as is_false_containment
from {{ source('cx', 'fct_contacts') }} as c
left join {{ source('cx', 'dim_contact_driver') }} as d on d.intent_code = c.intent_code
where c.started_with_bot
