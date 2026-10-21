"""Shared settings for the pipeline."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
TRIPS_RAW_DIR = RAW_DIR / "citibike"
WEATHER_RAW_DIR = RAW_DIR / "weather"
DUCKDB_PATH = Path(os.environ.get("DUCKDB_PATH", ROOT / "data" / "warehouse.duckdb")).resolve()
DBT_DIR = ROOT / "dbt"
EXPORT_DIR = ROOT / "exports" / "tableau"
REPORT_DIR = ROOT / "reports"

TRIPDATA_BUCKET_URL = "https://s3.amazonaws.com/tripdata"
TRIPDATA_PREFIX = "JC-"  # Jersey City / Hoboken system files

WEATHER_API_URL = "https://archive-api.open-meteo.com/v1/archive"
JERSEY_CITY = (40.7178, -74.0431)
WEATHER_DAILY_FIELDS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "snowfall_sum",
    "wind_speed_10m_max",
]

DEFAULT_START = "2025-10"
DEFAULT_END = "2026-09"

TRIP_COLUMNS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]


def month_range(start: str, end: str) -> list[str]:
    """'2025-10', '2026-01' -> ['202510', '202511', '202512', '202601']"""
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    if (y, m) > (ey, em):
        raise ValueError(f"start {start} is after end {end}")
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def month_bounds(start: str, end: str) -> tuple[date, date]:
    """First day of the start month and last day of the end month."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    ny, nm = (ey + 1, 1) if em == 12 else (ey, em + 1)
    return date(sy, sm, 1), date.fromordinal(date(ny, nm, 1).toordinal() - 1)
