-- One row per ride_id, typed and renamed. A ride can appear in two monthly files (late-filed
-- trips), so keep the copy from the most recently loaded file.
with source as (
    select * from {{ source('raw', 'citibike_trips') }}
),

deduplicated as (
    select
        *,
        row_number() over (partition by ride_id order by _loaded_at desc, _source_file desc) as _row_num
    from source
)

select
    ride_id,
    rideable_type,
    member_casual                                                    as rider_type,
    {{ dbt.safe_cast('started_at', api.Column.translate_type('timestamp')) }} as started_at,
    {{ dbt.safe_cast('ended_at', api.Column.translate_type('timestamp')) }}   as ended_at,
    nullif(trim(start_station_id), '')                               as start_station_id,
    nullif(trim(start_station_name), '')                             as start_station_name,
    nullif(trim(end_station_id), '')                                 as end_station_id,
    nullif(trim(end_station_name), '')                               as end_station_name,
    {{ dbt.safe_cast('start_lat', dbt.type_float()) }}               as start_lat,
    {{ dbt.safe_cast('start_lng', dbt.type_float()) }}               as start_lng,
    {{ dbt.safe_cast('end_lat', dbt.type_float()) }}                 as end_lat,
    {{ dbt.safe_cast('end_lng', dbt.type_float()) }}                 as end_lng,
    _source_file                                                     as source_file,
    _loaded_at                                                       as loaded_at
from deduplicated
where _row_num = 1
