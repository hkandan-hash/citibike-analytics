-- One row per calendar day in the analysis window.
with spine as (
    {{ dbt.date_spine(
        datepart="day",
        start_date="cast('" ~ var('analysis_start') ~ "' as date)",
        end_date=dbt.dateadd('day', 1, "cast('" ~ var('analysis_end') ~ "' as date)")
    ) }}
),

days as (
    select
        cast(date_day as date)                    as date_day,
        extract(year from date_day)               as year,
        extract(month from date_day)              as month,
        {{ day_of_week('date_day') }}             as day_of_week
    from spine
)

select
    d.date_day,
    d.year,
    d.month,
    cast(d.year as {{ dbt.type_string() }}) || '-' || lpad(cast(d.month as {{ dbt.type_string() }}), 2, '0') as year_month,
    case d.month
        when 1 then 'Jan' when 2 then 'Feb' when 3 then 'Mar' when 4 then 'Apr'
        when 5 then 'May' when 6 then 'Jun' when 7 then 'Jul' when 8 then 'Aug'
        when 9 then 'Sep' when 10 then 'Oct' when 11 then 'Nov' when 12 then 'Dec'
    end                                                    as month_name,
    d.day_of_week,
    case d.day_of_week
        when 0 then 'Sun' when 1 then 'Mon' when 2 then 'Tue' when 3 then 'Wed'
        when 4 then 'Thu' when 5 then 'Fri' when 6 then 'Sat'
    end                                                    as day_name,
    d.day_of_week in (0, 6)                                as is_weekend,
    h.holiday_name is not null                             as is_holiday,
    h.holiday_name,
    case when d.day_of_week in (0, 6) or h.holiday_name is not null
         then 'Weekend/holiday' else 'Workday' end         as day_type
from days d
left join {{ ref('us_holidays') }} h on h.holiday_date = d.date_day
