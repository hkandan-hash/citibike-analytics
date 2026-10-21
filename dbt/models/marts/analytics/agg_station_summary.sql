-- One row per Jersey City / Hoboken station over the whole window: demand, imbalance and how
-- often it needed rebalancing. Built for a Tableau map and a "where to send the van" ranking.
with flow as (
    select * from {{ ref('agg_station_daily_flow') }}
),

riders as (
    select
        start_station_id as station_id,
        avg(case when rider_type = 'member' then 1.0 else 0.0 end) as member_share,
        avg(case when rideable_type = 'electric_bike' then 1.0 else 0.0 end) as ebike_share
    from {{ ref('fct_trips') }}
    group by 1
)

select
    s.station_id,
    s.station_name,
    s.area,
    s.latitude,
    s.longitude,
    sum(f.departures)                                                  as departures,
    sum(f.arrivals)                                                    as arrivals,
    sum(f.net_flow)                                                    as net_flow,
    count(*)                                                           as active_days,
    round(avg(f.departures + f.arrivals), 1)                           as avg_daily_activity,
    round(avg(f.net_flow), 2)                                          as avg_daily_net_flow,
    sum(case when f.net_flow <= -5 then 1 else 0 end)                  as days_draining_5plus,
    sum(case when f.net_flow >= 5 then 1 else 0 end)                   as days_filling_5plus,
    round(r.member_share, 3)                                           as member_share,
    round(r.ebike_share, 3)                                            as ebike_share
from flow f
join {{ ref('dim_stations') }} s on s.station_id = f.station_id
left join riders r on r.station_id = f.station_id
group by s.station_id, s.station_name, s.area, s.latitude, s.longitude, r.member_share, r.ebike_share
