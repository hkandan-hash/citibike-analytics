-- Per source file: rows received, duplicates removed, rows excluded by reason, and valid trips.
-- Makes every number in the marts traceable back to the raw files.
with raw_counts as (
    select _source_file as source_file, count(*) as raw_rows
    from {{ source('raw', 'citibike_trips') }}
    group by 1
),

classified as (
    select
        source_file,
        count(*)                                                                  as deduplicated_rows,
        sum(case when exclusion_reason is null then 1 else 0 end)                 as valid_trips,
        sum(case when exclusion_reason = 'outside_analysis_window' then 1 else 0 end) as excluded_outside_window,
        sum(case when exclusion_reason = 'missing_start_station' then 1 else 0 end)   as excluded_missing_start_station,
        sum(case when exclusion_reason = 'non_positive_duration' then 1 else 0 end)   as excluded_non_positive_duration,
        sum(case when exclusion_reason = 'over_max_duration' then 1 else 0 end)       as excluded_over_max_duration,
        sum(case when exclusion_reason is null and end_station_id is null then 1 else 0 end) as valid_missing_end_station
    from {{ ref('int_trips__classified') }}
    group by 1
)

select
    r.source_file,
    r.raw_rows,
    r.raw_rows - coalesce(c.deduplicated_rows, 0) as duplicates_removed,
    coalesce(c.excluded_outside_window, 0)        as excluded_outside_window,
    coalesce(c.excluded_missing_start_station, 0) as excluded_missing_start_station,
    coalesce(c.excluded_non_positive_duration, 0) as excluded_non_positive_duration,
    coalesce(c.excluded_over_max_duration, 0)     as excluded_over_max_duration,
    coalesce(c.valid_trips, 0)                    as valid_trips,
    coalesce(c.valid_missing_end_station, 0)      as valid_missing_end_station
from raw_counts r
left join classified c on c.source_file = r.source_file
