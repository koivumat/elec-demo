"""Tools for step 03 (describe): daily spreads, yearly tables, profiles.

The key quantity for a battery is the daily spread: how much more the
expensive hours of a day cost than the cheap ones. spread(..., hours=h) is
the mean price of the most expensive h hours of a day minus the mean price
of the cheapest h hours, with every interval weighted by its length, so it
works for hourly, 15-minute and mixed days alike.

Upper bound: a battery storing 1 kWh that fills or empties in h hours, one
full cycle a day, no losses, buying and selling at the day-ahead price,
earns at most spread(h) / 1000 EUR per day (prices are EUR/MWh). Summed
over a year this is an upper bound before losses, taxes, fees and wear.
"""

import numpy as np
import pandas as pd

HELSINKI = "Europe/Helsinki"
SPREAD_HOURS = (1, 2, 4)


def mean_of_extreme_hours(prices, minutes, hours, most_expensive):
    """Mean price of the most expensive (or cheapest) `hours` of one day.

    Intervals are taken in price order until `hours` hours are filled; the
    last one may count only in part.
    """
    order = np.argsort(prices)
    if most_expensive:
        order = order[::-1]
    p = np.asarray(prices, dtype=float)[order]
    w = np.asarray(minutes, dtype=float)[order] / 60.0
    need = float(hours)
    if w.sum() < need:
        return np.nan
    taken = np.minimum(w, np.maximum(need - np.concatenate([[0.0], np.cumsum(w)[:-1]]), 0))
    return float((p * taken).sum() / need)


def spread(prices, minutes, hours):
    """Mean of the most expensive `hours` minus mean of the cheapest `hours`."""
    return (mean_of_extreme_hours(prices, minutes, hours, True)
            - mean_of_extreme_hours(prices, minutes, hours, False))


def daily_table(df):
    """One row per planning day: mean, min, max, spreads, negative hours."""
    rows = []
    for day, g in df.groupby("day", sort=True):
        p, m = g["price_eur_mwh"].to_numpy(), g["minutes"].to_numpy()
        row = {
            "day": day,
            "hours": m.sum() / 60,
            "mean": float((p * m).sum() / m.sum()),
            "min": float(p.min()),
            "max": float(p.max()),
            "negative_hours": float(m[p < 0].sum() / 60),
        }
        for h in SPREAD_HOURS:
            row[f"spread_{h}h"] = spread(p, m, h)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["year"] = pd.to_datetime(out["day"]).dt.year
    out["month"] = pd.to_datetime(out["day"]).dt.to_period("M").dt.to_timestamp()
    return out


def yearly_table(df, daily):
    """One row per year: price level and spread statistics."""
    year = df["day"].map(lambda d: d.year)
    w = df["minutes"]
    level = pd.DataFrame({
        "mean": (df["price_eur_mwh"] * w).groupby(year).sum() / w.groupby(year).sum(),
        "min": df.groupby(year)["price_eur_mwh"].min(),
        "max": df.groupby(year)["price_eur_mwh"].max(),
    })
    by_day = daily.groupby("year")
    spreads = pd.DataFrame({
        "days": by_day.size(),
        "negative_hours": by_day["negative_hours"].sum(),
        **{f"mean_spread_{h}h": by_day[f"spread_{h}h"].mean() for h in SPREAD_HOURS},
    })
    return spreads.join(level)[["days", "mean", "min", "max", "negative_hours"]
                               + [f"mean_spread_{h}h" for h in SPREAD_HOURS]]


def upper_bound_table(daily):
    """EUR per kWh of storage per year, one cycle a day, no losses."""
    by_year = daily.groupby("year")
    out = pd.DataFrame({"days": by_year.size()})
    for h in SPREAD_HOURS:
        out[f"eur_per_kwh_{h}h"] = by_year[f"spread_{h}h"].sum() / 1000
    return out


def zone_daily(every):
    """daily_table() for each zone of the all-zones file: {zone: table}."""
    return {z: daily_table(g.drop(columns="zone"))
            for z, g in every.groupby("zone", observed=True, sort=False)}


def equal_price_share(every, zone, other, tol=0.005):
    """Share of time (by duration) when `other` has the same price as `zone`.

    Neighbouring zones have the same price whenever the cable between them
    is not full: then they are, in effect, one market.
    """
    a = every[every["zone"] == zone][["time_utc", "price_eur_mwh", "minutes"]]
    b = every[every["zone"] == other][["time_utc", "price_eur_mwh"]]
    both = a.merge(b, on="time_utc", suffixes=("", "_other"))
    same = (both["price_eur_mwh"] - both["price_eur_mwh_other"]).abs() < tol
    return float(both.loc[same, "minutes"].sum() / both["minutes"].sum())


def zone_hour_profile(every):
    """Mean price by hour of day (Helsinki time), one column per zone."""
    local = pd.DatetimeIndex(every["time_utc"]).tz_convert(HELSINKI)
    w = every["minutes"].to_numpy()
    frame = pd.DataFrame({"zone": every["zone"].astype(str).to_numpy(), "hour": local.hour,
                          "pw": every["price_eur_mwh"].to_numpy() * w, "w": w})
    g = frame.groupby(["hour", "zone"])[["pw", "w"]].sum()
    out = (g["pw"] / g["w"]).unstack("zone")
    return out[[z for z in every["zone"].cat.categories if z in out.columns]]


def hour_profile(df):
    """Mean price by hour of day (Helsinki time), one column per year."""
    local = pd.DatetimeIndex(df["time_utc"]).tz_convert(HELSINKI)
    w = df["minutes"].to_numpy()
    frame = pd.DataFrame({"year": df["day"].map(lambda d: d.year).to_numpy(),
                          "hour": local.hour, "pw": df["price_eur_mwh"].to_numpy() * w,
                          "w": w})
    g = frame.groupby(["hour", "year"])[["pw", "w"]].sum()
    return (g["pw"] / g["w"]).unstack("year")
