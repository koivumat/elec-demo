"""Tools for step 02 (process): from raw CSVs to one clean price series.

Kept apart from 02_process.py so the tests can import them. Every
judgement call here is a choice in code/choices.py; this module only does
what the choices say.
"""

import pandas as pd

import fetch_tools as ft

# The time zone whose midnight starts a day, for each planning_day choice.
# "market": the day-ahead market's own day, Central European time.
DAY_TZ = {"helsinki": "Europe/Helsinki", "market": "Europe/Brussels"}

# Days we know are odd, per zone, as dates in the planning day's own calendar.
KNOWN_ANOMALIES = {
    "FI": {"2023-11-24": "prices down to -500 EUR/MWh after a trader's erroneous bid"},
}


def load_raw(zone, raw_dir):
    """All raw files of one zone as one DataFrame, sorted by time."""
    files = sorted(raw_dir.glob(f"prices_{zone}_*.csv"))
    if not files:
        raise FileNotFoundError(f"No raw files for zone {zone} in data/raw/. "
                                "Run: python run_all.py --fetch")
    df = pd.concat([ft.read_raw_csv(f) for f in files], ignore_index=True)
    return df.sort_values("time_utc", ignore_index=True), files


def day_of(times_utc, planning_day):
    """The planning day each time stamp belongs to (as a date)."""
    return pd.DatetimeIndex(times_utc).tz_convert(DAY_TZ[planning_day]).date


def day_bounds(first_day, last_day, planning_day):
    """Start (inclusive) and end (exclusive) of the days first..last, in UTC."""
    tz = DAY_TZ[planning_day]
    start = pd.Timestamp(first_day).tz_localize(tz)
    end = (pd.Timestamp(last_day) + pd.Timedelta(days=1)).tz_localize(tz)
    return start.tz_convert("UTC"), end.tz_convert("UTC")


def expected_per_day(first_day, last_day, planning_day):
    """How many raw rows each day should have (hours, or quarter-hours after
    the 15-minute switch; daylight saving days are shorter or longer)."""
    start, end = day_bounds(first_day, last_day, planning_day)
    idx = ft.expected_index(start, end)
    return pd.Series(1, index=day_of(idx, planning_day)).groupby(level=0).sum()


def select_sample(df, first_day, last_day, planning_day):
    """Rows whose planning day is within first_day..last_day; adds column 'day'."""
    out = df.copy()
    out["day"] = day_of(out["time_utc"], planning_day)
    first, last = pd.Timestamp(first_day).date(), pd.Timestamp(last_day).date()
    return out[(out["day"] >= first) & (out["day"] <= last)].reset_index(drop=True)


def day_completeness(df, first_day, last_day, planning_day):
    """Per day: expected rows, seen rows, and whether the day is complete.

    A day is complete when it has every expected row and no empty price.
    Days with no rows at all are included (seen = 0).
    """
    exp = expected_per_day(first_day, last_day, planning_day)
    valid = df.dropna(subset=["price_eur_mwh"])
    seen = valid.groupby("day").size().reindex(exp.index, fill_value=0)
    table = pd.DataFrame({"expected": exp, "seen": seen})
    table["complete"] = table["expected"] == table["seen"]
    return table


def drop_anomalies(df, zone, choice):
    """Remove known anomaly days if the choice is 'drop'. Returns (df, days)."""
    days = [pd.Timestamp(d).date() for d in KNOWN_ANOMALIES.get(zone, {})]
    if choice != "drop" or not days:
        return df, []
    present = sorted(set(days) & set(df["day"]))
    return df[~df["day"].isin(present)].reset_index(drop=True), present


def to_resolution(df, choice):
    """Change the time resolution as the price_resolution choice says.

    native: unchanged (hourly before 2025-10-01 01:00 Helsinki, 15 min after)
    hourly: each hour of quarter-hours becomes one row with their mean price
    15min:  each hourly row becomes four quarter-hour rows with the same price
    Both conversions keep the time-weighted mean price of every day.
    """
    if choice == "native":
        return df.copy()
    quarter = df[df["minutes"] == 15]
    hourly = df[df["minutes"] == 60]
    if choice == "hourly":
        hours = quarter.assign(time_utc=quarter["time_utc"].dt.floor("h")).groupby(
            ["time_utc", "day"], as_index=False)["price_eur_mwh"].mean()
        hours["minutes"] = 60
        out = pd.concat([hourly, hours], ignore_index=True)
    elif choice == "15min":
        parts = [quarter]
        for k in range(4):
            parts.append(hourly.assign(
                time_utc=hourly["time_utc"] + pd.Timedelta(minutes=15 * k), minutes=15))
        out = pd.concat(parts, ignore_index=True)
    else:
        raise ValueError(f"Unknown price_resolution '{choice}'")
    out["minutes"] = out["minutes"].astype("int16")
    return out.sort_values("time_utc", ignore_index=True)


weighted_mean = ft.weighted_mean  # time-weighted mean price (see fetch_tools)


def finish(df):
    """Final column order and types for the Parquet file."""
    out = df[["time_utc", "day", "price_eur_mwh", "minutes"]].copy()
    out["day"] = pd.to_datetime(out["day"]).dt.date  # stored as a Parquet date
    out["minutes"] = out["minutes"].astype("int16")
    out["price_eur_mwh"] = out["price_eur_mwh"].astype("float64")
    return out.reset_index(drop=True)
