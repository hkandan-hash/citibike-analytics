"""Export the marts Tableau needs to CSV (exports/tableau/).

These are the aggregated and dimension tables, small enough to commit, so the dashboard can be
rebuilt in Tableau Public (which cannot connect to Snowflake) straight from the repo. With
Tableau Desktop or Cloud, connect to the Snowflake ANALYTICS and CORE schemas instead.
fct_trips (~1M rows) is not exported; the aggregates cover the dashboard.
"""
from __future__ import annotations

import logging

import duckdb

from . import config

log = logging.getLogger(__name__)

EXPORTS = {
    "daily_ridership.csv": "select * from analytics.agg_daily_ridership order by date_day",
    "hourly_demand.csv": "select * from analytics.agg_hourly_demand order by day_type, start_hour, rider_type",
    "station_summary.csv": "select * from analytics.agg_station_summary order by departures desc",
    "station_daily_flow.csv": "select * from analytics.agg_station_daily_flow order by flow_date, station_id",
    "stations.csv": "select * from core.dim_stations order by station_id",
    "data_quality.csv": "select * from analytics.agg_data_quality order by source_file",
}


def export_marts() -> None:
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        for name, sql in EXPORTS.items():
            df = con.sql(sql).df()
            df.to_csv(config.EXPORT_DIR / name, index=False)
            log.info("Exported %s rows to %s", f"{len(df):,}", name)
    finally:
        con.close()
