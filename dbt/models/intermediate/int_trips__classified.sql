-- Every deduplicated trip, with derived fields and an exclusion_reason. Valid trips have a
-- null exclusion_reason. Nothing is dropped here, so data-quality reporting can count what
-- the marts leave out and why.
with trips as (
    select * from {{ ref('stg_citibike__trips') }}
),

derived as (
    select
        *,
        {{ dbt.datediff('started_at', 'ended_at', 'second') }} / 60.0         as duration_min,
        cast(started_at as date)                                              as trip_date,
        {{ station_area('start_station_id') }}                                as start_area,
        {{ station_area('end_station_id') }}                                  as end_area,
        case
            when end_lat is null or end_lng is null or start_lat is null or start_lng is null then null
            else {{ haversine_km('start_lat', 'start_lng', 'end_lat', 'end_lng') }}
        end                                                                   as distance_km
    from trips
)

select
    *,
    case
        when trip_date < cast('{{ var("analysis_start") }}' as date)
          or trip_date > cast('{{ var("analysis_end") }}' as date) then 'outside_analysis_window'
        when start_station_id is null then 'missing_start_station'
        when duration_min <= 0 then 'non_positive_duration'
        when duration_min > {{ var('max_trip_minutes') }} then 'over_max_duration'
    end as exclusion_reason
from derived
