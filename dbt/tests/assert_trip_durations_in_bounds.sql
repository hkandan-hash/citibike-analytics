-- No trip in the fact table can end before it starts or exceed the configured maximum.
select ride_id, duration_min
from {{ ref('fct_trips') }}
where duration_min <= 0 or duration_min > {{ var('max_trip_minutes') }}
