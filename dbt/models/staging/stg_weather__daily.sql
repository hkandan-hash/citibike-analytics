-- One row per date. Overlapping weather files can cover the same day; keep the latest load.
with source as (
    select
        *,
        row_number() over (partition by weather_date order by _loaded_at desc) as _row_num
    from {{ source('raw', 'weather_daily') }}
)

select
    {{ dbt.safe_cast('weather_date', api.Column.translate_type('date')) }} as weather_date,
    {{ dbt.safe_cast('temperature_2m_max', dbt.type_float()) }}   as temp_max_c,
    {{ dbt.safe_cast('temperature_2m_min', dbt.type_float()) }}   as temp_min_c,
    {{ dbt.safe_cast('temperature_2m_mean', dbt.type_float()) }}  as temp_mean_c,
    {{ dbt.safe_cast('precipitation_sum', dbt.type_float()) }}    as precipitation_mm,
    {{ dbt.safe_cast('snowfall_sum', dbt.type_float()) }}         as snowfall_cm,
    {{ dbt.safe_cast('wind_speed_10m_max', dbt.type_float()) }}   as wind_max_kmh
from source
where _row_num = 1
