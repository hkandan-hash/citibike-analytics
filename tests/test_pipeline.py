import io
import zipfile
from datetime import date

import duckdb
import pandas as pd
import pytest

from pipeline import config
from pipeline.extract import TRIP_FILE_RE
from pipeline.load import DuckDBWarehouse, read_trip_zip

ROW = {
    "ride_id": "A1", "rideable_type": "classic_bike", "started_at": "2026-09-08 08:11:36.020",
    "ended_at": "2026-09-08 08:28:50.409", "start_station_name": "Grand St", "start_station_id": "JC102",
    "end_station_name": "City Hall", "end_station_id": "JC003", "start_lat": "40.715", "start_lng": "-74.037",
    "end_lat": "40.717", "end_lng": "-74.043", "member_casual": "member",
}


def make_zip(path, rows, include_macos_junk=True, columns=None):
    df = pd.DataFrame(rows, columns=columns or config.TRIP_COLUMNS)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("JC-202609-citibike-tripdata.csv", df.to_csv(index=False))
        if include_macos_junk:
            z.writestr("__MACOSX/._JC-202609-citibike-tripdata.csv", b"\x00\x05junk")
    return path


def test_month_range_crosses_year():
    assert config.month_range("2025-11", "2026-02") == ["202511", "202512", "202601", "202602"]


def test_month_range_rejects_reversed_range():
    with pytest.raises(ValueError):
        config.month_range("2026-02", "2025-11")


def test_month_bounds():
    assert config.month_bounds("2025-10", "2026-02") == (date(2025, 10, 1), date(2026, 2, 28))


@pytest.mark.parametrize("key, month", [
    ("JC-202604-citibike-tripdata.zip", "202604"),
    ("JC-202605-citibike-tripdata.csv.zip", "202605"),
])
def test_trip_file_regex_matches_both_naming_styles(key, month):
    assert TRIP_FILE_RE.match(key).group(1) == month


def test_trip_file_regex_ignores_other_files():
    assert TRIP_FILE_RE.match("202605-citibike-tripdata.zip") is None  # NYC system file
    assert TRIP_FILE_RE.match("JC-202605-citibike-tripdata.csv") is None


def test_read_trip_zip_skips_macos_metadata_and_keeps_text(tmp_path):
    df = read_trip_zip(make_zip(tmp_path / "f.zip", [ROW, {**ROW, "ride_id": "A2", "end_station_id": ""}]))
    assert list(df.columns) == config.TRIP_COLUMNS
    assert df.loc[0, "start_lat"] == "40.715"  # raw layer stays text
    assert df.loc[1, "end_station_id"] is None  # empty string -> NULL


def test_read_trip_zip_rejects_missing_columns(tmp_path):
    cols = [c for c in config.TRIP_COLUMNS if c != "member_casual"]
    path = make_zip(tmp_path / "f.zip", [{k: ROW[k] for k in cols}], columns=cols)
    with pytest.raises(ValueError, match="member_casual"):
        read_trip_zip(path)


def test_load_is_idempotent_and_replaces_by_file(tmp_path):
    wh = DuckDBWarehouse(tmp_path / "w.duckdb")
    df = pd.DataFrame([ROW, {**ROW, "ride_id": "A2"}])
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, df, "JC-202609.zip", "sha-1")
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, df, "JC-202609.zip", "sha-1")
    count = wh.con.execute("select count(*) from raw.citibike_trips").fetchone()[0]
    assert count == 2  # loading the same file twice does not duplicate

    corrected = pd.DataFrame([ROW])
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, corrected, "JC-202609.zip", "sha-2")
    assert wh.con.execute("select count(*) from raw.citibike_trips").fetchone()[0] == 1
    assert wh.loaded_checksum("JC-202609.zip") == "sha-2"
    assert wh.loaded_checksum("never-loaded.zip") is None
    wh.close()


def test_load_keeps_other_files_untouched(tmp_path):
    wh = DuckDBWarehouse(tmp_path / "w.duckdb")
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, pd.DataFrame([ROW]), "a.zip", "1")
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, pd.DataFrame([{**ROW, "ride_id": "B"}]), "b.zip", "2")
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, pd.DataFrame([{**ROW, "ride_id": "B2"}]), "b.zip", "3")
    rows = wh.con.execute("select _source_file, ride_id from raw.citibike_trips order by 1").fetchall()
    assert rows == [("a.zip", "A1"), ("b.zip", "B2")]
    wh.close()


def test_schema_drift_fails_loudly_and_rolls_back(tmp_path):
    wh = DuckDBWarehouse(tmp_path / "w.duckdb")
    wh.replace_file("citibike_trips", config.TRIP_COLUMNS, pd.DataFrame([ROW]), "a.zip", "1")
    renamed = pd.DataFrame([ROW]).rename(columns={"member_casual": "rider_kind"})
    with pytest.raises(duckdb.Error):
        wh.replace_file("citibike_trips", config.TRIP_COLUMNS, renamed, "a.zip", "2")
    # The failed reload rolled back: the original rows and checksum are still there.
    assert wh.con.execute("select count(*) from raw.citibike_trips").fetchone()[0] == 1
    assert wh.loaded_checksum("a.zip") == "1"
    wh.close()
