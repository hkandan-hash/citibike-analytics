-- Departures and arrivals per Jersey City / Hoboken station per day. A negative net_flow means
-- bikes drained out of the station that day (it needs restocking); positive means it filled up.
-- New York City docks are excluded: this data only shows trips that touch Jersey City or Hoboken.
with departures as (
    select start_station_id as station_id, trip_date, count(*) as departures
    from {{ ref('fct_trips') }}
    group by 1, 2
),

arrivals as (
    select end_station_id as station_id, cast(ended_at as date) as trip_date, count(*) as arrivals
    from {{ ref('fct_trips') }}
    where end_station_id is not null
    group by 1, 2
),

combined as (
    select
        coalesce(d.station_id, a.station_id) as station_id,
        coalesce(d.trip_date, a.trip_date)   as flow_date,
        coalesce(d.departures, 0)            as departures,
        coalesce(a.arrivals, 0)              as arrivals
    from departures d
    full outer join arrivals a
        on a.station_id = d.station_id and a.trip_date = d.trip_date
)

select
    c.station_id,
    s.station_name,
    s.area,
    c.flow_date,
    c.departures,
    c.arrivals,
    c.arrivals - c.departures as net_flow
from combined c
join {{ ref('dim_stations') }} s on s.station_id = c.station_id
where s.area in ('Jersey City', 'Hoboken')
  and c.flow_date between cast('{{ var("analysis_start") }}' as date) and cast('{{ var("analysis_end") }}' as date)
