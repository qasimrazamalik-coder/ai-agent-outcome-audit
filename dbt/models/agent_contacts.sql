-- Grain: one row per contact that went straight to an agent (voice, no bot).
-- This is the comparison path: what the same drivers cost and resolve without the bot.
select
    c.session_id,
    c.intent_code,
    c.is_resolved,
    c.is_resolution_eligible and c.is_outcome_observable          as is_observable,
    c.agent_cost_usd,
    c.agent_handle_seconds,
    c.is_churn_observable,
    c.cancelled_within_30d
from {{ source('cx', 'fct_contacts') }} as c
where c.handling_path = 'agent'
