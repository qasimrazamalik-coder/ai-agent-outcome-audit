-- Grain: one row per contact driver. Counts only; rates and confidence intervals are
-- computed in Python (audit/stats.py) so they can be tested in isolation.
with bot as (
    select
        intent_code,
        any_value(driver_path)                                              as driver_path,
        any_value(driver_l1)                                                as driver_l1,
        any_value(is_avoidable)                                             as is_avoidable,
        any_value(upstream_owner)                                           as upstream_owner,
        count(*)                                                            as bot_sessions,
        count(*) filter (where is_bot_contained)                            as bot_contained,
        count(*) filter (where is_observable)                               as bot_observable,
        count(*) filter (where is_observable and is_bot_contained)          as bot_contained_observable,
        count(*) filter (where is_observable and is_bot_contained and is_resolved) as bot_true_resolved,
        count(*) filter (where is_observable and is_false_containment)      as bot_false_contained,
        count(*) filter (where is_observable and is_bot_escalated)          as bot_escalated_observable,
        count(*) filter (where is_observable and is_bot_escalated and is_resolved) as bot_escalated_resolved,
        avg(agent_cost_usd) filter (where is_bot_escalated)                 as escalated_agent_cost_usd
    from {{ ref('bot_sessions') }}
    group by intent_code
),

agent as (
    select
        intent_code,
        count(*)                                                            as agent_contacts,
        count(*) filter (where is_observable)                               as agent_observable,
        count(*) filter (where is_observable and is_resolved)               as agent_resolved,
        avg(agent_cost_usd)                                                 as agent_cost_per_contact_usd,
        avg(agent_handle_seconds)                                           as agent_aht_seconds
    from {{ ref('agent_contacts') }}
    group by intent_code
)

select
    b.*,
    coalesce(a.agent_contacts, 0)                                           as agent_contacts,
    coalesce(a.agent_observable, 0)                                         as agent_observable,
    coalesce(a.agent_resolved, 0)                                           as agent_resolved,
    a.agent_cost_per_contact_usd,
    a.agent_aht_seconds
from bot as b
left join agent as a on a.intent_code = b.intent_code
