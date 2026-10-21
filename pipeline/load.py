"""Load: copy raw files into the warehouse's RAW schema, exactly as received (all text).

Typing and cleaning happen later in dbt. Each file is loaded with delete-then-insert keyed on
its file name, inside one transaction, and recorded in raw.load_log with a checksum, so:
  * re-running a load never duplicates rows,
  * an unchanged file is skipped,
  * a corrected file published under the same name replaces the old rows.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)

TRIPS_TABLE = "citibike_trips"
WEATHER_TABLE = "weather_daily"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_trip_zip(path: Path) -> pd.DataFrame:
    """Read the trip CSV inside a monthly zip, ignoring macOS metadata entries."""
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX")]
        if len(members) != 1:
            raise ValueError(f"{path.name}: expected one CSV, found {members}")
        with z.open(members[0]) as fh:
            df = pd.read_csv(io.TextIOWrapper(fh, "utf-8"), dtype=str, keep_default_na=False)
    missing = set(config.TRIP_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
    df = df[config.TRIP_COLUMNS].replace({"": None})
    return df


def read_weather_json(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # "date" is a keyword in Snowflake, so land it as weather_date.
    df = pd.DataFrame(payload["daily"]).rename(columns={"time": "weather_date"})
    return df.astype(str).replace({"nan": None, "None": None})


class Warehouse(ABC):
    """The two operations the pipeline needs from a warehouse."""

    @abstractmethod
    def replace_file(self, table: str, columns: list[str], df: pd.DataFrame, source_file: str, checksum: str) -> None:
        """Atomically replace all rows from `source_file` in raw.<table> and log the load."""

    @abstractmethod
    def loaded_checksum(self, source_file: str) -> str | None:
        """Checksum recorded for the last successful load of this file, if any."""

    def close(self) -> None:  # pragma: no cover - trivial
        pass


class DuckDBWarehouse(Warehouse):
    def __init__(self, path: Path = config.DUCKDB_PATH):
        import duckdb

        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute("create schema if not exists raw")
        self.con.execute(
            """create table if not exists raw.load_log (
                   source_file varchar primary key, table_name varchar, row_count bigint,
                   checksum varchar, loaded_at timestamp)"""
        )

    def _ensure_table(self, table: str, columns: list[str]) -> None:
        cols = ", ".join(f"{c} varchar" for c in columns)
        self.con.execute(f"create table if not exists raw.{table} ({cols}, _source_file varchar, _loaded_at timestamp)")

    def replace_file(self, table, columns, df, source_file, checksum):
        self._ensure_table(table, columns)
        loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
        frame = df.assign(_source_file=source_file, _loaded_at=loaded_at)
        self.con.register("incoming", frame)
        try:
            self.con.execute("begin transaction")
            self.con.execute(f"delete from raw.{table} where _source_file = ?", [source_file])
            # BY NAME: a renamed or missing source column errors instead of shifting data into the wrong column.
            self.con.execute(f"insert into raw.{table} by name select * from incoming")
            self.con.execute("delete from raw.load_log where source_file = ?", [source_file])
            self.con.execute(
                "insert into raw.load_log values (?, ?, ?, ?, ?)",
                [source_file, table, len(df), checksum, loaded_at],
            )
            self.con.execute("commit")
        except Exception:
            self.con.execute("rollback")
            raise
        finally:
            self.con.unregister("incoming")

    def loaded_checksum(self, source_file):
        row = self.con.execute("select checksum from raw.load_log where source_file = ?", [source_file]).fetchone()
        return row[0] if row else None

    def close(self):
        self.con.close()


class SnowflakeWarehouse(Warehouse):
    """Loads into <SNOWFLAKE_DATABASE>.RAW using write_pandas (stage + COPY INTO under the hood).

    Credentials come from the same environment variables as the dbt Snowflake target.
    """

    def __init__(self):
        import os

        import snowflake.connector

        self.con = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            password=os.environ["SNOWFLAKE_PASSWORD"],
            role=os.environ.get("SNOWFLAKE_ROLE", "TRANSFORMER"),
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "TRANSFORMING"),
            database=os.environ.get("SNOWFLAKE_DATABASE", "CITIBIKE"),
        )
        cur = self.con.cursor()
        cur.execute("create schema if not exists raw")
        cur.execute(
            """create table if not exists raw.load_log (
                   source_file varchar primary key, table_name varchar, row_count number,
                   checksum varchar, loaded_at timestamp_ntz)"""
        )

    def replace_file(self, table, columns, df, source_file, checksum):
        from snowflake.connector.pandas_tools import write_pandas

        cur = self.con.cursor()
        cols = ", ".join(f"{c} varchar" for c in columns)
        cur.execute(f"create table if not exists raw.{table} ({cols}, _source_file varchar, _loaded_at timestamp_ntz)")
        loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
        frame = df.assign(_source_file=source_file, _loaded_at=loaded_at.isoformat(sep=" "))
        frame.columns = [c.upper() for c in frame.columns]
        cur.execute("begin")
        try:
            cur.execute(f"delete from raw.{table} where _source_file = %s", (source_file,))
            write_pandas(self.con, frame, table.upper(), schema="RAW", quote_identifiers=False)
            cur.execute("delete from raw.load_log where source_file = %s", (source_file,))
            cur.execute(
                "insert into raw.load_log values (%s, %s, %s, %s, %s)",
                (source_file, table, len(df), checksum, loaded_at),
            )
            cur.execute("commit")
        except Exception:
            cur.execute("rollback")
            raise

    def loaded_checksum(self, source_file):
        row = self.con.cursor().execute(
            "select checksum from raw.load_log where source_file = %s", (source_file,)
        ).fetchone()
        return row[0] if row else None

    def close(self):
        self.con.close()


def connect(target: str) -> Warehouse:
    return SnowflakeWarehouse() if target == "snowflake" else DuckDBWarehouse()


def load_all(warehouse: Warehouse, months: list[str], force: bool = False) -> dict[str, int]:
    """Load every downloaded trip file for `months`, plus all weather files. Returns rows loaded per file."""
    loaded: dict[str, int] = {}
    trip_files = [p for p in sorted(config.TRIPS_RAW_DIR.glob("JC-*.zip")) if p.name[3:9] in months]
    for path in trip_files:
        checksum = sha256(path)
        if not force and warehouse.loaded_checksum(path.name) == checksum:
            log.info("Skipping %s (already loaded, unchanged)", path.name)
            continue
        df = read_trip_zip(path)
        warehouse.replace_file(TRIPS_TABLE, config.TRIP_COLUMNS, df, path.name, checksum)
        loaded[path.name] = len(df)
        log.info("Loaded %s rows from %s", f"{len(df):,}", path.name)

    for path in sorted(config.WEATHER_RAW_DIR.glob("weather_daily_*.json")):
        checksum = sha256(path)
        if not force and warehouse.loaded_checksum(path.name) == checksum:
            continue
        df = read_weather_json(path)
        warehouse.replace_file(WEATHER_TABLE, list(df.columns), df, path.name, checksum)
        loaded[path.name] = len(df)
        log.info("Loaded %s rows from %s", len(df), path.name)
    return loaded
