-- Every raw row must be accounted for: duplicate, excluded for a reason, or a valid trip.
select *
from {{ ref('agg_data_quality') }}
where raw_rows <> duplicates_removed
               + excluded_outside_window
               + excluded_missing_start_station
               + excluded_non_positive_duration
               + excluded_over_max_duration
               + valid_trips
