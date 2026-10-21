-- One row per station seen in valid trips, as a start or an end. Stations get renamed, so use
-- the most recently used name; coordinates are the median of reported positions.
with valid as (
    select * from {{ ref('int_trips__classified') }}
    where exclusion_reason is null
),

points as (
    select start_station_id as station_id, start_station_name as station_name,
           start_lat as lat, start_lng as lng, started_at as seen_at
    from valid
    union all
    select end_station_id, end_station_name, end_lat, end_lng, ended_at
    from valid
    where end_station_id is not null
),

names as (
    select
        station_id,
        station_name,
        row_number() over (partition by station_id order by max(seen_at) desc, station_name) as rn
    from points
    group by station_id, station_name
),

stats as (
    select
        station_id,
        median(lat)              as latitude,
        median(lng)              as longitude,
        cast(min(seen_at) as date) as first_seen_date,
        cast(max(seen_at) as date) as last_seen_date
    from points
    group by station_id
),

departures as (
    select start_station_id as station_id, count(*) as trips_started
    from valid group by 1
),

arrivals as (
    select end_station_id as station_id, count(*) as trips_ended
    from valid where end_station_id is not null group by 1
)

select
    s.station_id,
    n.station_name,
    {{ station_area('s.station_id') }}           as area,
    round(s.latitude, 6)                         as latitude,
    round(s.longitude, 6)                        as longitude,
    s.first_seen_date,
    s.last_seen_date,
    coalesce(d.trips_started, 0)                 as trips_started,
    coalesce(a.trips_ended, 0)                   as trips_ended
from stats s
join names n on n.station_id = s.station_id and n.rn = 1
left join departures d on d.station_id = s.station_id
left join arrivals a on a.station_id = s.station_id
