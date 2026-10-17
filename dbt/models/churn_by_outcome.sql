-- Grain: one row per driver x bot outcome (truly resolved vs falsely contained), for
-- contained bot sessions at least 30 days old. Comparing churn within the same driver
-- controls for the fact that some drivers (cancellations, disputes) churn more anyway.
select
    intent_code,
    case when is_resolved then 'truly resolved' else 'falsely contained' end   as outcome,
    count(*)                                                                    as sessions,
    count(*) filter (where cancelled_within_30d)                                as churned_30d
from {{ ref('bot_sessions') }}
where is_bot_contained and is_churn_observable and is_observable
group by 1, 2
