-- Per-driver counts must add up to the bot session total: nothing dropped by the join
-- to the driver taxonomy.
select d.n as driver_total, s.n as session_total
from (select sum(bot_sessions) as n from {{ ref('driver_outcomes') }}) as d
cross join (select count(*) as n from {{ ref('bot_sessions') }}) as s
where d.n <> s.n
