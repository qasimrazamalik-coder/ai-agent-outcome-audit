-- Grain: one row per driver. How well does the repeat-contact proxy measure true
-- resolution? Ground truth exists only because the data is simulated: the generator
-- records whether each issue was really solved and at which contact.
with truth as (
    select
        se.session_id,
        e.truly_resolved and e.contacts = se.contact_no                as truly_resolved_here
    from {{ source('cx_truth', 'session_episode') }} as se
    inner join {{ source('cx_truth', 'episodes') }} as e on e.episode_id = se.episode_id
)

select
    b.intent_code,
    count(*)                                                            as contained_sessions,
    avg(case when b.is_resolved then 1.0 else 0 end)                    as measured_resolution_rate,
    avg(case when t.truly_resolved_here then 1.0 else 0 end)            as true_resolution_rate,
    avg(case when b.is_resolved = t.truly_resolved_here then 1.0 else 0 end) as proxy_accuracy,
    count(*) filter (where b.is_resolved and not t.truly_resolved_here) as silent_failures
from {{ ref('bot_sessions') }} as b
inner join truth as t on t.session_id = b.session_id
where b.is_bot_contained and b.is_observable
group by 1
