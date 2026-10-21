# Building the Tableau dashboard

This guide rebuilds the **Citi Bike Jersey City Operations** dashboard from the dbt marts. It takes about 30 to 45 minutes.

## 1. Connect to the data

| Tableau edition | Connect to |
|---|---|
| **Tableau Public** (free) | The CSVs in [`exports/tableau/`](../exports/tableau/). Tableau Public cannot connect to Snowflake. |
| **Tableau Desktop / Cloud** | Snowflake → database `CITIBIKE`, schemas `ANALYTICS` and `CORE`. Use the same tables as below. |

Add these as **separate data sources**. Each table is already at the grain its sheet needs, so no joins are required:

| Data source | Grain | Used for |
|---|---|---|
| `daily_ridership` (`ANALYTICS.AGG_DAILY_RIDERSHIP`) | one row per day | KPIs, monthly trend, weather |
| `hourly_demand` (`ANALYTICS.AGG_HOURLY_DEMAND`) | day type × hour × rider type | hourly heatmap |
| `station_summary` (`ANALYTICS.AGG_STATION_SUMMARY`) | one row per station | map and rebalancing ranking |
| `data_quality` (`ANALYTICS.AGG_DATA_QUALITY`) | one row per source file | data quality table |

In `daily_ridership`, set `date_day` to the **Date** type. In `station_summary`, set `latitude` and `longitude` to the **Latitude** and **Longitude** geographic roles.

## 2. Calculated fields

In `daily_ridership`:

```
// Casual share
SUM([casual_trips]) / SUM([trips])

// E-bike share
SUM([ebike_trips]) / SUM([trips])

// Weather
IF [is_wet_day] THEN "Wet day" ELSE "Dry day" END
```

In `station_summary`:

```
// Rebalancing status
IF [avg_daily_net_flow] <= -1 THEN "Needs restocking"
ELSEIF [avg_daily_net_flow] >= 1 THEN "Needs bikes removed"
ELSE "Balanced"
END
```

In `hourly_demand`:

```
// Hour label
IF [start_hour] = 0 THEN "12am"
ELSEIF [start_hour] < 12 THEN STR([start_hour]) + "am"
ELSEIF [start_hour] = 12 THEN "12pm"
ELSE STR([start_hour] - 12) + "pm"
END
```

## 3. Sheets

1. **KPIs.** Create four text sheets from `daily_ridership`: total `SUM([trips])`, `Casual share`, `E-bike share`, and `AVG([avg_duration_min])`. Format the shares as percentages.
2. **Monthly trend.** Put `MONTH(date_day)` (continuous) on Columns and `SUM([member_trips])` and `SUM([casual_trips])` on Rows as a stacked bar. Use Measure Names on Color, members blue and casual orange.
3. **Hourly heatmap.** Put `Hour label` on Columns (sorted by `start_hour`) and `day_type` on Rows. Use `SUM([avg_trips_per_day])` on Color with a single-hue sequential palette, and add a text label.
4. **Station map.** Put `longitude` and `latitude` on Columns and Rows. Put `avg_daily_net_flow` on Color with a **diverging** red-blue palette centered at 0, and `avg_daily_activity` on Size. Add `station_name`, `area`, `days_draining_5plus` and `days_filling_5plus` to the tooltip.
5. **Rebalancing ranking.** Put `station_name` on Rows, sorted by `avg_daily_net_flow`, and `avg_daily_net_flow` on Columns. Color by `Rebalancing status`, and filter to the top and bottom 10.
6. **Weather.** Put `temp_mean_c` on Columns and `trips` on Rows, with the `Weather` field on Color. Add per-color trend lines from the Analytics pane. Wet days should sit below dry days at the same temperature.
7. **Data quality.** Show a text table of `source_file` with `raw_rows`, `duplicates_removed`, the `excluded_*` columns and `valid_trips`.

## 4. Dashboard layout

```
+------------------------------------------------------------------+
| Citi Bike Jersey City Operations             [Month filter]      |
| [Total trips] [Casual share] [E-bike share] [Avg duration]       |
+---------------------------------+--------------------------------+
| Monthly trend                   | Hourly heatmap                 |
+---------------------------------+--------------------------------+
| Station map (net flow)          | Rebalancing ranking            |
+---------------------------------+--------------------------------+
| Weather vs ridership            | Data quality                   |
+---------------------------------+--------------------------------+
```

Apply the month filter to the `daily_ridership` sheets only, since `station_summary` already covers the full window. Use the map as a filter action on the ranking.

## 5. Check your numbers

Your dashboard should match [`reports/analysis.md`](../reports/analysis.md):

- **Total trips:** 971,486 over October 2025 to September 2026.
- **Peak and low months:** August 2026 is the peak at 111,172 trips, and February 2026 is the low at 25,758.
- **Most-draining station:** Oakland Ave, at about −5.0 bikes per day.

If yours differ, check that the date field is a Date type and that no extract filters are applied.
