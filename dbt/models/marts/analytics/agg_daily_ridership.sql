-- One row per day: ridership, mix and weather. Days with no trips still appear (zero trips).
with trips as (
    select
        trip_date,
        count(*)                                                        as trips,
        sum(case when rider_type = 'member' then 1 else 0 end)          as member_trips,
        sum(case when rider_type = 'casual' then 1 else 0 end)          as casual_trips,
        sum(case when rideable_type = 'electric_bike' then 1 else 0 end) as ebike_trips,
        sum(case when is_to_nyc then 1 else 0 end)                      as trips_to_nyc,
        avg(duration_min)                                               as avg_duration_min,
        median(duration_min)                                            as median_duration_min,
        avg(distance_km)                                                as avg_distance_km
    from {{ ref('fct_trips') }}
    group by trip_date
)

select
    d.date_day,
    d.year_month,
    d.month_name,
    d.day_name,
    d.is_weekend,
    d.is_holiday,
    d.day_type,
    coalesce(t.trips, 0)                         as trips,
    coalesce(t.member_trips, 0)                  as member_trips,
    coalesce(t.casual_trips, 0)                  as casual_trips,
    coalesce(t.ebike_trips, 0)                   as ebike_trips,
    coalesce(t.trips_to_nyc, 0)                  as trips_to_nyc,
    round(t.avg_duration_min, 2)                 as avg_duration_min,
    round(t.median_duration_min, 2)              as median_duration_min,
    round(t.avg_distance_km, 3)                  as avg_distance_km,
    w.temp_mean_c,
    w.temp_max_c,
    w.precipitation_mm,
    w.snowfall_cm,
    w.wind_max_kmh,
    coalesce(w.precipitation_mm >= {{ var('rainy_day_mm') }}, false) as is_wet_day
from {{ ref('dim_date') }} d
left join trips t on t.trip_date = d.date_day
left join {{ ref('stg_weather__daily') }} w on w.weather_date = d.date_day
