"""Pipeline entry point.

    python -m pipeline.run all                          # extract -> load -> dbt build -> export -> analyze
    python -m pipeline.run extract --start 2026-09 --end 2026-09
    python -m pipeline.run load --target snowflake      # load raw files into Snowflake instead of DuckDB
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from . import config

log = logging.getLogger("pipeline")
STEPS = ["extract", "load", "transform", "export", "analyze"]


def run_dbt(target: str, start: str, end: str) -> None:
    """dbt build (models + tests + seeds) for the same window the extract/load steps used."""
    env = {**os.environ, "DBT_PROFILES_DIR": str(config.DBT_DIR), "DUCKDB_PATH": str(config.DUCKDB_PATH)}
    window_start, window_end = config.month_bounds(start, end)
    dbt_vars = f'{{"analysis_start": "{window_start}", "analysis_end": "{window_end}"}}'
    cmd = [sys.executable, "-m", "dbt.cli.main", "build", "--project-dir", str(config.DBT_DIR),
           "--target", target, "--vars", dbt_vars]
    log.info("Running: %s", " ".join(cmd[2:]))
    subprocess.run(cmd, check=True, env=env)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Citi Bike Jersey City analytics pipeline")
    parser.add_argument("step", choices=STEPS + ["all"])
    parser.add_argument("--start", default=config.DEFAULT_START, help="first month, YYYY-MM")
    parser.add_argument("--end", default=config.DEFAULT_END, help="last month, YYYY-MM")
    parser.add_argument("--target", choices=["dev", "snowflake"], default="dev", help="dev = local DuckDB")
    parser.add_argument("--force", action="store_true", help="reload files even if unchanged")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    months = config.month_range(args.start, args.end)
    steps = STEPS if args.step == "all" else [args.step]

    if "extract" in steps:
        from .extract import extract_trips, extract_weather

        missing = extract_trips(months)
        if missing:
            log.warning("Source has no files for: %s", ", ".join(missing))
        extract_weather(*config.month_bounds(args.start, args.end))

    if "load" in steps:
        from .load import connect, load_all

        warehouse = connect(args.target)
        try:
            load_all(warehouse, months, force=args.force)
        finally:
            warehouse.close()

    if "transform" in steps:
        run_dbt(args.target, args.start, args.end)

    if "export" in steps:
        if args.target != "dev":
            log.info("Skipping CSV export for %s: point Tableau at the Snowflake marts directly.", args.target)
        else:
            from .export import export_marts

            export_marts()

    if "analyze" in steps:
        if args.target != "dev":
            log.info("Skipping local analysis for %s.", args.target)
        else:
            from .analyze import analyze

            analyze()


if __name__ == "__main__":
    main()
