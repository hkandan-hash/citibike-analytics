"""Analysis: answer business questions from the marts and write reports/analysis.md + figures.

Every number in the report is computed here from the warehouse, never typed in by hand.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import config  # noqa: E402

log = logging.getLogger(__name__)

# Validated categorical/diverging steps (light mode) from the project's chart palette.
BLUE, ORANGE = "#2a78d6", "#eb6834"
RED = "#e34948"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(width: float = 9, height: float = 4.6) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(width, height), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    return fig, ax


def title(ax: plt.Axes, headline: str, subtitle: str) -> None:
    ax.set_title(headline, loc="left", fontsize=13, color=INK, fontweight="bold", pad=26)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK_2)


@dataclass
class Regression:
    names: list[str]
    coef: np.ndarray
    se: np.ndarray
    r2: float
    n: int


def ols(y: np.ndarray, X: np.ndarray, names: list[str]) -> Regression:
    """Ordinary least squares with classical standard errors."""
    X = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(y) - X.shape[1]
    sigma2 = resid @ resid / dof
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return Regression(["intercept", *names], coef, se, float(r2), len(y))


def analyze() -> None:
    fig_dir = config.REPORT_DIR / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    q = lambda sql: con.sql(sql).df()  # noqa: E731

    daily = q("select * from analytics.agg_daily_ridership order by date_day")
    hourly = q("select * from analytics.agg_hourly_demand")
    stations = q("select * from analytics.agg_station_summary")
    dq = q("select * from analytics.agg_data_quality")
    trips = q("""select count(*) as n, avg(case when rider_type='casual' then 1.0 else 0 end) as casual_share,
                        avg(case when rideable_type='electric_bike' then 1.0 else 0 end) as ebike_share,
                        median(duration_min) as med_min, median(distance_km) as med_km,
                        avg(case when start_area <> end_area then 1.0 else 0 end) as cross_area,
                        avg(case when is_to_nyc then 1.0 else 0 end) as to_nyc
                 from core.fct_trips""").iloc[0]
    con.close()

    # ---------------------------------------------------------------- 1. seasonality
    monthly = daily.groupby("year_month", as_index=False)[["trips", "member_trips", "casual_trips"]].sum()
    peak = monthly.loc[monthly.trips.idxmax()]
    low = monthly.loc[monthly.trips.idxmin()]
    fig, ax = new_figure()
    x = np.arange(len(monthly))
    ax.bar(x, monthly.member_trips, color=BLUE, width=0.62, label="Members")
    ax.bar(x, monthly.casual_trips, bottom=monthly.member_trips, color=ORANGE, width=0.62, label="Casual riders",
           edgecolor=SURFACE, linewidth=1.5)
    ax.set_xticks(x, [pd.Timestamp(m + "-01").strftime("%b\n%Y") if i in (0, len(x) - 1) or m.endswith("-01")
                      else pd.Timestamp(m + "-01").strftime("%b") for i, m in enumerate(monthly.year_month)])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    for i in (monthly.trips.idxmax(), monthly.trips.idxmin()):
        ax.text(i, monthly.trips[i] + 1500, f"{monthly.trips[i]:,}", ha="center", fontsize=9, color=INK_2)
    ax.legend(frameon=False, loc="upper left", fontsize=9, ncol=2, bbox_to_anchor=(0, 1.0))
    title(ax, f"Ridership in {pd.Timestamp(peak.year_month + '-01'):%B} was {peak.trips / low.trips:.1f}x {pd.Timestamp(low.year_month + '-01'):%B}'s",
          "Trips per month, Citi Bike Jersey City and Hoboken")
    fig.tight_layout()
    fig.savefig(fig_dir / "monthly_ridership.png", facecolor=SURFACE)
    plt.close(fig)
    casual_summer = monthly[monthly.year_month.str[-2:].isin(["06", "07", "08"])]
    casual_winter = monthly[monthly.year_month.str[-2:].isin(["12", "01", "02"])]
    casual_share_summer = casual_summer.casual_trips.sum() / casual_summer.trips.sum()
    casual_share_winter = casual_winter.casual_trips.sum() / casual_winter.trips.sum()

    # ---------------------------------------------------------------- 2. hourly pattern
    by_hour = hourly.groupby(["day_type", "start_hour"], as_index=False).avg_trips_per_day.sum()
    fig, ax = new_figure()
    for day_type, color in (("Workday", BLUE), ("Weekend/holiday", ORANGE)):
        s = by_hour[by_hour.day_type == day_type].sort_values("start_hour")
        ax.plot(s.start_hour, s.avg_trips_per_day, color=color, linewidth=2, label=day_type)
    work = by_hour[by_hour.day_type == "Workday"].set_index("start_hour").avg_trips_per_day
    weekend = by_hour[by_hour.day_type == "Weekend/holiday"].set_index("start_hour").avg_trips_per_day
    am_peak, pm_peak = work.loc[5:11].idxmax(), work.loc[12:23].idxmax()
    ax.set_xticks(range(0, 24, 3), [f"{h % 12 or 12}{'am' if h < 12 else 'pm'}" for h in range(0, 24, 3)])
    ax.set_xlim(0, 23)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    title(ax, f"Workdays peak at {am_peak % 12 or 12}am and {pm_peak % 12 or 12}pm; weekends build to one midday hump",
          "Average trips started per hour, all riders")
    fig.tight_layout()
    fig.savefig(fig_dir / "hourly_demand.png", facecolor=SURFACE)
    plt.close(fig)

    # ---------------------------------------------------------------- 3. weather
    d = daily.dropna(subset=["temp_mean_c", "precipitation_mm"]).copy()
    d["weekend_or_holiday"] = (d.day_type == "Weekend/holiday").astype(float)
    naive = d.groupby("is_wet_day").trips.mean()
    naive_temp = d.groupby("is_wet_day").temp_mean_c.mean()
    reg = ols(
        d.trips.to_numpy(float),
        np.column_stack([d.temp_mean_c, d.temp_mean_c ** 2, d.precipitation_mm, d.weekend_or_holiday]),
        ["temp_c", "temp_c_squared", "precip_mm", "weekend_or_holiday"],
    )
    rain_coef, rain_se = reg.coef[3], reg.se[3]
    # Matched comparison: wet vs dry days within the same 5 C temperature band and day type.
    d["temp_band"] = (d.temp_mean_c // 5) * 5
    cells = d.groupby(["temp_band", "day_type", "is_wet_day"]).trips.mean().unstack()
    counts = d.groupby(["temp_band", "day_type", "is_wet_day"]).trips.size().unstack()
    valid = cells[(counts.min(axis=1) >= 3)].dropna()
    matched_effect = ((valid[True] - valid[False]) / valid[False]).mean()

    fig, ax = new_figure()
    for wet, color, label in ((False, BLUE, "Dry day"), (True, ORANGE, f"Wet day (≥{1:.0f} mm)")):
        s = d[d.is_wet_day == wet]
        ax.scatter(s.temp_mean_c, s.trips, s=18, color=color, alpha=0.75, label=label, edgecolors=SURFACE, linewidths=0.6)
    ax.set_xlabel("Daily mean temperature (°C)", color=MUTED, fontsize=9)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    title(ax, "Temperature drives ridership; rain lowers it once temperature is held equal",
          "Trips per day vs mean temperature. At the same temperature, wet days (orange) tend to sit below dry days.")
    fig.tight_layout()
    fig.savefig(fig_dir / "weather_effect.png", facecolor=SURFACE)
    plt.close(fig)

    # ---------------------------------------------------------------- 4. rebalancing
    top = pd.concat([stations.nsmallest(8, "avg_daily_net_flow"), stations.nlargest(8, "avg_daily_net_flow")])
    top = top.sort_values("avg_daily_net_flow")
    fig, ax = new_figure(9, 5.6)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    colors = [RED if v < 0 else BLUE for v in top.avg_daily_net_flow]
    ax.barh(top.station_name, top.avg_daily_net_flow, color=colors, height=0.62)
    ax.axvline(0, color=AXIS, linewidth=1)
    for y, (v, area) in enumerate(zip(top.avg_daily_net_flow, top.area)):
        ax.text(v + (0.15 if v >= 0 else -0.15), y, f"{v:+.1f} ({area})", va="center",
                ha="left" if v >= 0 else "right", fontsize=8.5, color=INK_2)
    lim = top.avg_daily_net_flow.abs().max() * 1.6
    ax.set_xlim(-lim, lim)
    ax.tick_params(axis="y", labelsize=8.5, colors=INK_2)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.text(0.02, 0.955, "A handful of stations drain every day while others fill up",
             fontsize=13, color=INK, fontweight="bold")
    fig.text(0.02, 0.915, "Average daily arrivals minus departures. Red: needs restocking. Blue: needs bikes removed.",
             fontsize=9.5, color=INK_2)
    fig.savefig(fig_dir / "rebalancing.png", facecolor=SURFACE)
    plt.close(fig)
    drains = stations.nsmallest(3, "avg_daily_net_flow")
    fullest = stations.nlargest(1, "avg_daily_net_flow").iloc[0]
    worst = drains.iloc[0]
    total_abs_flow = stations.avg_daily_net_flow.abs().sum()
    top10_share = stations.avg_daily_net_flow.abs().nlargest(10).sum() / total_abs_flow

    # ---------------------------------------------------------------- report
    total_raw = int(dq.raw_rows.sum())
    excluded = total_raw - int(dq.valid_trips.sum())
    lines = [
        "# Citi Bike Jersey City: analysis",
        "",
        f"Window: {daily.date_day.min():%B %d, %Y} to {daily.date_day.max():%B %d, %Y}. "
        f"{int(trips.n):,} valid trips. Generated by `pipeline/analyze.py` from the dbt marts; every figure below is computed, not hand-entered.",
        "",
        "## Key findings",
        "",
        f"1. **Strong seasonality.** {pd.Timestamp(peak.year_month + '-01'):%B %Y} had {int(peak.trips):,} trips, "
        f"{peak.trips / low.trips:.1f}x the low of {int(low.trips):,} in {pd.Timestamp(low.year_month + '-01'):%B %Y}. "
        f"Casual riders are {casual_share_summer:.0%} of summer trips but {casual_share_winter:.0%} in winter, so the summer surge is disproportionately casual riders.",
        f"2. **A commuter system on workdays.** Workday demand peaks at {am_peak % 12 or 12}am "
        f"({work[am_peak]:.0f} trips/hour) and {pm_peak % 12 or 12}pm ({work[pm_peak]:.0f} trips/hour); weekends and holidays have no morning peak "
        f"and top out at {weekend.max():.0f} trips/hour around {int(weekend.idxmax()) % 12 or 12}{'am' if weekend.idxmax() < 12 else 'pm'}.",
        f"3. **Rain lowers ridership more than the raw numbers show.** Wet days average {naive[True]:,.0f} trips vs {naive[False]:,.0f} on dry days, "
        f"only {1 - naive[True] / naive[False]:.0%} fewer. But wet days in this period were warmer ({naive_temp[True]:.1f} °C vs {naive_temp[False]:.1f} °C), which masks the effect. "
        f"Holding temperature and day type fixed, each millimetre of rain is associated with {abs(rain_coef):.0f} fewer trips that day "
        f"(±{1.96 * rain_se:.0f}, 95% interval). Comparing wet and dry days within the same 5 °C band and day type, wet days average "
        f"{abs(matched_effect):.0%} {'fewer' if matched_effect < 0 else 'more'} trips.",
        f"4. **Rebalancing need is concentrated.** Of {len(stations)} Jersey City and Hoboken stations, the 10 most imbalanced account for "
        f"{top10_share:.0%} of total daily imbalance. "
        + ", ".join(f"{r.station_name} ({r.avg_daily_net_flow:+.1f}/day)" for r in drains.itertuples())
        + f" drain the most; {worst.station_name} lost 5+ bikes on {int(worst.days_draining_5plus)} days. "
        f"{fullest.station_name} ({fullest.area}) fills fastest ({fullest.avg_daily_net_flow:+.1f}/day). "
        "Transit hubs appear on both sides (Hudson Pl & Hoboken Terminal drains; Grove St PATH fills), so neither geography nor transit access alone explains the pattern.",
        f"5. **Short local hops.** The median trip is {trips.med_min:.1f} minutes and {trips.med_km:.2f} km. {trips.ebike_share:.0%} of trips are on e-bikes. "
        f"{trips.cross_area:.1%} of trips cross between Jersey City, Hoboken and New York City, and only {trips.to_nyc:.2%} end in New York City.",
        "",
        "## Charts",
        "",
        "![Monthly ridership](figures/monthly_ridership.png)",
        "",
        "![Hourly demand](figures/hourly_demand.png)",
        "",
        "![Weather effect](figures/weather_effect.png)",
        "",
        "![Rebalancing](figures/rebalancing.png)",
        "",
        "## Weather model",
        "",
        f"Ordinary least squares on {reg.n} days: `trips ~ temp + temp² + precipitation_mm + weekend_or_holiday`. R² = {reg.r2:.2f}.",
        "",
        "| term | coefficient | std. error |",
        "|---|---:|---:|",
        *[f"| {n} | {c:,.2f} | {s:,.2f} |" for n, c, s in zip(reg.names, reg.coef, reg.se)],
        "",
        "This is correlational. Daily weather comes from ERA5 reanalysis (a gridded estimate, not a rain gauge), and one year of data cannot separate weather from other seasonal changes such as school terms or tourism.",
        "",
        "## Data quality",
        "",
        f"{total_raw:,} raw rows were received; {excluded:,} ({excluded / total_raw:.2%}) were excluded:",
        "",
        "| reason | rows |",
        "|---|---:|",
        f"| duplicate ride_id across files | {int(dq.duplicates_removed.sum()):,} |",
        f"| started outside the analysis window | {int(dq.excluded_outside_window.sum()):,} |",
        f"| missing start station | {int(dq.excluded_missing_start_station.sum()):,} |",
        f"| ended before it started | {int(dq.excluded_non_positive_duration.sum()):,} |",
        f"| longer than 24 hours (lost or unreturned) | {int(dq.excluded_over_max_duration.sum()):,} |",
        "",
        f"A further {int(dq.valid_missing_end_station.sum()):,} valid trips have no end station (bike not returned to a dock). They count as trips but are left out of station-flow figures.",
        "",
    ]
    (config.REPORT_DIR / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote reports/analysis.md and %d figures", len(list(fig_dir.glob("*.png"))))
