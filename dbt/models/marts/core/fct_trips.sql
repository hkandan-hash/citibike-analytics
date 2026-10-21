-- One row per valid trip. Grain: ride_id.
select
    ride_id,
    trip_date,
    started_at,
    ended_at,
    extract(hour from started_at)                         as start_hour,
    {{ day_of_week('started_at') }}                       as day_of_week,
    rideable_type,
    rider_type,
    start_station_id,
    end_station_id,
    start_area,
    end_area,
    round(duration_min, 2)                                as duration_min,
    round(distance_km, 3)                                 as distance_km,
    end_station_id is null                                as is_missing_end_station,
    coalesce(start_station_id = end_station_id, false)    as is_round_trip,
    coalesce(end_area = 'New York City', false)           as is_to_nyc,
    coalesce(start_area <> end_area, false)               as is_cross_area
from {{ ref('int_trips__classified') }}
where exclusion_reason is null
