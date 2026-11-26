"""Tools for step 01 (fetch): download windows, retries, CSV files, checks.

Kept apart from 01_fetch.py so the tests can import them (a module name
cannot start with a digit) and so none of them needs the API.

The ENTSO-E service is not always stable. Every download goes through
call_with_retry():
- waits at least MIN_SECONDS_BETWEEN_CALLS between calls (ENTSO-E allows 400
  requests per minute per token; a full download is about 120),
- a request that hangs is cut after TIMEOUT_SECONDS,
- network errors, time-outs and server errors (HTTP 500, 502, 503, 504, 527,
  599) are retried after 10 s, 30 s, 60 s, 120 s, 300 s,
- "too many requests" (HTTP 429) means a ban of about 10 minutes, so we wait
  RATE_LIMIT_WAIT_SECONDS before trying again,
- other errors (e.g. 401: wrong key, 400: bad request) are not retried,
  because trying again cannot help.
"""

import os
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests

# ------------------------------------------------------------ constants
# These are not analysis choices: the download covers everything any choice
# can select (see notes/decisions.md). Forks start at step 02.

# Our zone name -> the entsoe-py zone(s) behind it, each with the moment it
# starts. Germany was one zone with Austria and Luxembourg (DE-AT-LU) until
# delivery day 2018-09-30; from delivery day 2018-10-01 Austria has its own
# zone and Germany is DE-LU. Our "DE" joins the two at that moment.
DE_SPLIT = pd.Timestamp("2018-10-01 00:00", tz="Europe/Berlin")
ZONES = {
    "FI": [("FI", None)],
    "SE1": [("SE_1", None)],
    "SE3": [("SE_3", None)],
    "EE": [("EE", None)],
    "DE": [("DE_AT_LU", None), ("DE_LU", DE_SPLIT)],
}
FETCH_START = "2015-01-01"  # first day downloaded
FETCH_END = "2026-11-01"  # first day NOT downloaded (so: up to 2026-10-31)
FILE_TZ = "Europe/Helsinki"  # one file per calendar year in Helsinki time

# Day-ahead prices are hourly until this moment and 15-minute after it.
# Delivery day 2025-10-01 starts at midnight Central European (summer) time,
# which is 2025-10-01 01:00 in Helsinki.
GO_LIVE_15MIN = pd.Timestamp("2025-09-30 22:00", tz="UTC")

PRICE_FLOOR = -500.0  # harmonised minimum clearing price in day-ahead (EUR/MWh)

# Retry policy
TIMEOUT_SECONDS = 120
MIN_SECONDS_BETWEEN_CALLS = 2.0
RETRY_WAITS = (10, 30, 60, 120, 300)  # seconds before attempts 2, 3, 4, 5, 6
RATE_LIMIT_WAIT_SECONDS = 660  # ENTSO-E bans for about 10 minutes
RETRY_STATUS = {500, 502, 503, 504, 527, 599}

COLUMNS = ["time_utc", "time_helsinki", "price_eur_mwh", "minutes"]


# ------------------------------------------------------- download windows


@dataclass(frozen=True)
class Window:
    zone: str  # our name, e.g. "SE1"
    year: int
    start: pd.Timestamp  # inclusive, Helsinki time
    end: pd.Timestamp  # exclusive, Helsinki time

    @property
    def filename(self):
        return f"prices_{self.zone}_{self.year}.csv"


def year_windows(zones=tuple(ZONES), start=FETCH_START, end=FETCH_END, tz=FILE_TZ):
    """One Window per zone and calendar year, cut to [start, end)."""
    start = pd.Timestamp(start, tz=tz)
    end = pd.Timestamp(end, tz=tz)
    windows = []
    for zone in zones:
        for year in range(start.year, (end - pd.Timedelta("1ns")).year + 1):
            w_start = max(start, pd.Timestamp(f"{year}-01-01", tz=tz))
            w_end = min(end, pd.Timestamp(f"{year + 1}-01-01", tz=tz))
            windows.append(Window(zone, year, w_start, w_end))
    return windows


def segments(window):
    """The requests needed for one window: [(entsoe-py zone, start, end)].

    One request for most zones; two for DE in 2018 (before and after the
    zone change)."""
    parts = ZONES[window.zone]
    tz = window.start.tz
    out = []
    for i, (code, valid_from) in enumerate(parts):
        valid_to = parts[i + 1][1] if i + 1 < len(parts) else None
        s = window.start if valid_from is None else max(window.start, valid_from)
        e = window.end if valid_to is None else min(window.end, valid_to)
        if s < e:
            # Same time zone for start and end: the client trims with
            # Series.truncate(), which pandas refuses for mixed time zones.
            out.append((code, s.tz_convert(tz), e.tz_convert(tz)))
    return out


# --------------------------------------------------------------- retries


class Throttle:
    """Keeps at least `min_seconds` between calls."""

    def __init__(self, min_seconds=MIN_SECONDS_BETWEEN_CALLS, clock=time.monotonic,
                 sleep=time.sleep):
        self.min_seconds = min_seconds
        self.clock = clock
        self.sleep = sleep
        self.last = None

    def wait(self):
        if self.last is not None:
            remaining = self.min_seconds - (self.clock() - self.last)
            if remaining > 0:
                self.sleep(remaining)
        self.last = self.clock()


def retry_wait(error, attempt):
    """Seconds to wait before the next attempt, or None if we should give up.

    `attempt` is the number of the attempt that just failed (1, 2, ...).
    """
    if attempt > len(RETRY_WAITS):
        return None
    status = getattr(getattr(error, "response", None), "status_code", None)
    if isinstance(error, requests.HTTPError):
        if status == 429:
            return RATE_LIMIT_WAIT_SECONDS
        if status in RETRY_STATUS:
            return RETRY_WAITS[attempt - 1]
        return None  # 400, 401, 403, ...: trying again cannot help
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return RETRY_WAITS[attempt - 1]
    return None


def describe_error(error):
    """Short, key-free description such as 'HTTP 503' or 'ReadTimeout'."""
    status = getattr(getattr(error, "response", None), "status_code", None)
    if status is not None:
        return f"HTTP {status}"
    return type(error).__name__


def call_with_retry(func, label, log, sleep=time.sleep, throttle=None):
    """Call func() until it succeeds, retrying as described at the top.

    Errors that are not retried (including 'no data') are raised at once.
    After the last attempt the last error is raised.
    """
    attempt = 0
    while True:
        attempt += 1
        if throttle is not None:
            throttle.wait()
        try:
            return func()
        except Exception as error:  # noqa: BLE001 (we decide below)
            wait = retry_wait(error, attempt)
            if wait is None:
                raise
            log(f"    {label}: {describe_error(error)} on attempt {attempt}, "
                f"retrying in {wait} s")
            sleep(wait)


# ------------------------------------------------------------ raw frames


def expected_index(start, end):
    """The time stamps (UTC) we expect in [start, end): hourly before the
    15-minute go-live, every 15 minutes after it."""
    start = pd.Timestamp(start).tz_convert("UTC")
    end = pd.Timestamp(end).tz_convert("UTC")
    hourly = pd.date_range(start, min(end, GO_LIVE_15MIN), freq="h", inclusive="left")
    quarter = pd.date_range(max(start, GO_LIVE_15MIN), end, freq="15min",
                            inclusive="left")
    return hourly.append(quarter)


def minutes_for(times_utc):
    """Length of each interval by the market rule: 60 before go-live, 15 after."""
    return np.where(times_utc < GO_LIVE_15MIN, 60, 15)


def to_raw_frame(series, start, end):
    """Turn the client's price Series into the rows of one raw CSV file.

    The client returns prices in the zone's local time and keeps a value at
    `end` (its end is inclusive); we keep [start, end) only.
    """
    s = series.copy()  # empty prices are kept, so the check report can count them
    s.index = pd.DatetimeIndex(s.index).tz_convert("UTC")
    start_utc = pd.Timestamp(start).tz_convert("UTC")
    end_utc = pd.Timestamp(end).tz_convert("UTC")
    s = s[(s.index >= start_utc) & (s.index < end_utc)].sort_index()
    return pd.DataFrame({
        "time_utc": s.index,
        "time_helsinki": s.index.tz_convert(FILE_TZ),
        "price_eur_mwh": s.to_numpy(dtype=float),
        "minutes": minutes_for(s.index),
    })


def write_raw_csv(frame, path):
    """Write a raw CSV: same bytes for the same data on every computer.

    Written to a temporary file first and then renamed, so a crash never
    leaves a half-written file behind.
    """
    out = pd.DataFrame({
        "time_utc": frame["time_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_helsinki": [t.isoformat() for t in frame["time_helsinki"]],
        "price_eur_mwh": frame["price_eur_mwh"],
        "minutes": frame["minutes"].astype(int),
    })
    tmp = path.with_name(path.name + ".tmp")
    out.to_csv(tmp, index=False, lineterminator="\n", encoding="utf-8")
    os.replace(tmp, path)


def read_raw_csv(path):
    """Read a raw CSV back, with time_utc as a UTC time stamp."""
    df = pd.read_csv(path, dtype={"time_helsinki": str})
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df


# ---------------------------------------------------------------- checks


def weighted_mean(df, by=None):
    """Time-weighted mean price: an hour counts as much as four quarter-hours.

    A plain mean of rows would count each quarter-hour as much as an hour.
    `by`: optional keys (a Series aligned with df) to get one mean per group.
    """
    valid = df.dropna(subset=["price_eur_mwh"])
    pw = valid["price_eur_mwh"] * valid["minutes"]
    if by is None:
        return float(pw.sum() / valid["minutes"].sum()) if len(valid) else float("nan")
    keep = df["price_eur_mwh"].notna().to_numpy()
    by = np.asarray(by)[keep]
    pw, minutes = pw.to_numpy(), valid["minutes"].to_numpy()
    return (pd.Series(pw).groupby(by).sum() / pd.Series(minutes).groupby(by).sum())


def check_frame(df, start, end):
    """Counts a person (and a test) can check for one raw file."""
    expected = expected_index(start, end)
    seen = pd.DatetimeIndex(df["time_utc"])
    prices = df["price_eur_mwh"]
    valid = prices.dropna()
    return {
        "rows": len(df),
        "expected": len(expected),
        "missing": len(expected.difference(seen)),
        "extra": len(seen.difference(expected)),
        "duplicates": int(seen.duplicated().sum()),
        "empty_prices": int(prices.isna().sum()),
        "rows_60": int((df["minutes"] == 60).sum()),
        "rows_15": int((df["minutes"] == 15).sum()),
        "min": float(valid.min()) if len(valid) else float("nan"),
        "mean": weighted_mean(df),
        "max": float(valid.max()) if len(valid) else float("nan"),
        "negative": int((valid < 0).sum()),
        "below_floor": int((valid < PRICE_FLOOR).sum()),
    }


def day_counts(times_utc, tz=FILE_TZ):
    """Number of rows per local calendar day."""
    local = pd.DatetimeIndex(times_utc).tz_convert(tz)
    return pd.Series(1, index=local).groupby(local.date).sum()


def odd_days(df, start, end, tz=FILE_TZ):
    """Days whose number of rows differs from what we expect for that day.

    Expected counts come from expected_index(), so daylight saving days
    (23 or 25 hours; 92 or 100 quarter-hours) are expected, not odd.
    """
    exp = day_counts(expected_index(start, end), tz)
    seen = day_counts(df["time_utc"], tz).reindex(exp.index, fill_value=0)
    diff = seen[seen != exp]
    return [(day, int(exp[day]), int(diff[day])) for day in diff.index]


def daylight_saving_days(start, end, tz=FILE_TZ):
    """Local days that are not 24 hours long, with their expected row count."""
    exp = day_counts(expected_index(start, end), tz)
    out = []
    for day, count in exp.items():
        midnight = pd.Timestamp(day).tz_localize(tz)
        next_midnight = (pd.Timestamp(day) + pd.Timedelta(days=1)).tz_localize(tz)
        hours = (next_midnight - midnight) / pd.Timedelta("1h")
        if hours != 24:
            out.append((day, int(hours), int(count)))
    return out
