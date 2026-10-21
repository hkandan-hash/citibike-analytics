-- Average trips per hour of day, for workdays vs weekends/holidays, by rider type.
-- Averaged over the number of days of that type, so the two day types are comparable.
with day_counts as (
    select day_type, count(*) as day_count
    from {{ ref('dim_date') }}
    group by day_type
),

hourly as (
    select d.day_type, f.start_hour, f.rider_type, count(*) as trips
    from {{ ref('fct_trips') }} f
    join {{ ref('dim_date') }} d on d.date_day = f.trip_date
    group by d.day_type, f.start_hour, f.rider_type
)

select
    h.day_type,
    h.start_hour,
    h.rider_type,
    h.trips,
    c.day_count,
    round(h.trips * 1.0 / c.day_count, 2) as avg_trips_per_day
from hourly h
join day_counts c on c.day_type = h.day_type
