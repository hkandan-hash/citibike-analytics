"""Extract: download source files into an immutable raw layer (data/raw).

Files are never modified after download. Re-running skips files that already exist, so
extraction is safe to repeat and every load can be replayed from the same bytes.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date

from . import config

log = logging.getLogger(__name__)
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
# The bucket mixes "JC-202604-citibike-tripdata.zip" and "JC-202605-citibike-tripdata.csv.zip".
TRIP_FILE_RE = re.compile(r"^JC-(\d{6})-citibike-tripdata(\.csv)?\.zip$")


def list_trip_files(prefix: str = config.TRIPDATA_PREFIX) -> dict[str, str]:
    """Map YYYYMM -> object key by listing the public bucket, instead of guessing file names."""
    keys: dict[str, str] = {}
    marker = ""
    while True:
        query = urllib.parse.urlencode({"prefix": prefix, "marker": marker})
        with urllib.request.urlopen(f"{config.TRIPDATA_BUCKET_URL}/?{query}", timeout=60) as resp:
            root = ET.fromstring(resp.read())
        contents = root.findall("s3:Contents", S3_NS)
        for item in contents:
            key = item.findtext("s3:Key", namespaces=S3_NS) or ""
            match = TRIP_FILE_RE.match(key)
            if match:
                keys[match.group(1)] = key
        if root.findtext("s3:IsTruncated", namespaces=S3_NS) != "true" or not contents:
            return keys
        marker = contents[-1].findtext("s3:Key", namespaces=S3_NS) or ""


def extract_trips(months: list[str]) -> list[str]:
    """Download the monthly trip zips. Returns the months that are missing from the source."""
    available = list_trip_files()
    config.TRIPS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for month in months:
        key = available.get(month)
        if key is None:
            log.warning("No Citi Bike file published for %s", month)
            missing.append(month)
            continue
        target = config.TRIPS_RAW_DIR / key
        if target.exists():
            log.info("Already have %s", key)
            continue
        log.info("Downloading %s", key)
        tmp = target.with_suffix(".part")
        urllib.request.urlretrieve(f"{config.TRIPDATA_BUCKET_URL}/{key}", tmp)
        tmp.rename(target)  # only complete files ever appear under their final name
    return missing


def extract_weather(start: date, end: date) -> None:
    """Daily weather for Jersey City from the Open-Meteo archive (ERA5 reanalysis)."""
    config.WEATHER_RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = config.WEATHER_RAW_DIR / f"weather_daily_{start.isoformat()}_{end.isoformat()}.json"
    if target.exists():
        log.info("Already have %s", target.name)
        return
    lat, lon = config.JERSEY_CITY
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": ",".join(config.WEATHER_DAILY_FIELDS),
        "timezone": "America/New_York",
    })
    with urllib.request.urlopen(f"{config.WEATHER_API_URL}?{params}", timeout=60) as resp:
        payload = json.load(resp)
    target.write_text(json.dumps(payload), encoding="utf-8")
    log.info("Saved %s", target.name)
