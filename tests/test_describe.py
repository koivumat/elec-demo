"""Step 03 (describe): spreads, upper bound, hour profile. Offline."""

import numpy as np
import pandas as pd
import pytest

import describe_tools as dt


def test_spread_on_a_four_hour_day():
    p, m = [10, 20, 30, 40], [60] * 4
    assert dt.spread(p, m, 1) == pytest.approx(30)  # 40 - 10
    assert dt.spread(p, m, 2) == pytest.approx(20)  # (30+40)/2 - (10+20)/2


def test_spread_is_the_same_for_hours_and_their_equal_quarters():
    p, m = [10, 20, 30, 40], [60] * 4
    assert dt.spread(np.repeat(p, 4), [15] * 16, 2) == pytest.approx(dt.spread(p, m, 2))


def test_quarter_hours_can_widen_the_spread():
    # one hour whose quarters are 0, 0, 0, 80: hourly mean 20
    quarters = [0, 0, 0, 80] + [20] * 4
    assert dt.spread(quarters, [15] * 8, 0.25) == pytest.approx(80)
    assert dt.spread([20, 20], [60, 60], 1) == pytest.approx(0)


def test_last_interval_counts_only_in_part():
    assert dt.mean_of_extreme_hours([10, 20], [60, 60], 1.5, False) == pytest.approx(40 / 3)


def test_spread_is_empty_when_the_day_is_too_short():
    assert np.isnan(dt.spread([10, 20], [60, 60], 4))


def make_days(prices_per_day, first="2024-01-01"):
    """Hourly rows for consecutive days, each day given as a list of prices."""
    rows = []
    for i, prices in enumerate(prices_per_day):
        day = pd.Timestamp(first) + pd.Timedelta(days=i)
        start = day.tz_localize("Europe/Helsinki").tz_convert("UTC")
        for h, price in enumerate(prices):
            rows.append({"time_utc": start + pd.Timedelta(hours=h), "day": day.date(),
                         "price_eur_mwh": float(price), "minutes": 60})
    return pd.DataFrame(rows)


def test_upper_bound_is_the_sum_of_daily_spreads_in_eur_per_kwh():
    flat = [50] * 24
    peaky = [0] * 22 + [100, 100]
    daily = dt.daily_table(make_days([flat, peaky]))
    bound = dt.upper_bound_table(daily)
    # day 1 earns nothing; day 2: 2 hours at 100 minus 2 hours at 0 = 100 EUR/MWh
    assert bound.loc[2024, "eur_per_kwh_2h"] == pytest.approx(0.1)


def test_negative_hours_and_yearly_days():
    df = make_days([[-5] * 3 + [10] * 21, [10] * 24])
    daily = dt.daily_table(df)
    yearly = dt.yearly_table(df, daily)
    assert yearly.loc[2024, "days"] == 2
    assert yearly.loc[2024, "negative_hours"] == pytest.approx(3)


def test_hour_profile_uses_helsinki_hours():
    df = make_days([[h for h in range(24)]])
    profile = dt.hour_profile(df)
    assert profile.loc[7, 2024] == pytest.approx(7)  # price h at Helsinki hour h
