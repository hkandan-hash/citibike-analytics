-- Daily ridership must add up to exactly the number of trips in the fact table.
select
    (select sum(trips) from {{ ref('agg_daily_ridership') }}) as daily_total,
    (select count(*) from {{ ref('fct_trips') }})             as fact_total
where (select sum(trips) from {{ ref('agg_daily_ridership') }})
   <> (select count(*) from {{ ref('fct_trips') }})
