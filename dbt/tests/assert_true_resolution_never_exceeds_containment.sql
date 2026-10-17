-- A session can only be truly resolved by the bot if the bot contained it.
select intent_code
from {{ ref('driver_outcomes') }}
where bot_true_resolved > bot_contained_observable
