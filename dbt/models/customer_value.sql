-- Grain: one row. Average monthly revenue of active customers, used to value churn.
select
    count(*)                    as active_customers,
    avg(current_mrr_usd)        as avg_mrr_usd
from {{ source('cx', 'dim_customer') }}
where is_active
