"""Step 02 (process): days, completeness, anomalies, resolution. Offline."""

import pandas as pd
import pytest

import fetch_tools as ft
import process_tools as pt


def raw_frame(first_day, last_day, tz="Europe/Helsinki", price=lambda t: t.hour % 5 - 1.0):
    """Raw rows like a raw CSV, for the Helsinki days first..last."""
    idx = ft.expected_index(pd.Timestamp(first_day, tz=tz),
                            pd.Timestamp(last_day, tz=tz) + pd.Timedelta(days=1))
    return pd.DataFrame({
        "time_utc": idx,
        "price_eur_mwh": [float(price(t)) for t in idx],
        "minutes": ft.minutes_for(idx),
    })


def test_market_day_starts_an_hour_after_helsinki_midnight():
    t = pd.DatetimeIndex([pd.Timestamp("2025-10-01 00:30", tz="Europe/Helsinki")])
    assert str(pt.day_of(t, "helsinki")[0]) == "2025-10-01"
    assert str(pt.day_of(t, "market")[0]) == "2025-09-30"


def test_rows_expected_per_day():
    h = pt.expected_per_day("2025-09-30", "2025-10-26", "helsinki")
    m = pt.expected_per_day("2025-09-30", "2025-10-26", "market")
    days = {str(d): n for d, n in h.items()}
    assert days["2025-09-30"] == 24
    assert days["2025-10-01"] == 1 + 23 * 4  # switch day in Helsinki time
    assert days["2025-10-26"] == 100  # 25 hours of quarter-hours
    assert {str(d): n for d, n in m.items()}["2025-10-01"] == 96  # market day: all quarters


def test_a_missing_hour_makes_a_day_incomplete():
    raw = raw_frame("2024-03-01", "2024-03-03")
    raw = raw.drop(index=30)  # an hour on 2024-03-02
    sample = pt.select_sample(raw, "2024-03-01", "2024-03-03", "helsinki")
    table = pt.day_completeness(sample, "2024-03-01", "2024-03-03", "helsinki")
    assert [str(d) for d in table.index[~table["complete"]]] == ["2024-03-02"]
    assert int(table.loc[pd.Timestamp("2024-03-02").date(), "seen"]) == 23


def test_a_day_without_rows_is_counted_as_incomplete():
    raw = raw_frame("2015-01-02", "2015-01-03")
    sample = pt.select_sample(raw, "2015-01-01", "2015-01-03", "helsinki")
    table = pt.day_completeness(sample, "2015-01-01", "2015-01-03", "helsinki")
    assert int(table["seen"].iloc[0]) == 0 and not table["complete"].iloc[0]


def test_anomalies_are_dropped_only_when_asked_and_only_in_their_zone():
    raw = pt.select_sample(raw_frame("2023-11-23", "2023-11-25"),
                           "2023-11-23", "2023-11-25", "helsinki")
    kept, dropped = pt.drop_anomalies(raw, "FI", "keep")
    assert len(kept) == len(raw) and dropped == []
    kept, dropped = pt.drop_anomalies(raw, "FI", "drop")
    assert [str(d) for d in dropped] == ["2023-11-24"] and kept["day"].nunique() == 2
    kept, dropped = pt.drop_anomalies(raw, "SE1", "drop")
    assert dropped == []


@pytest.mark.parametrize("choice,rows_per_day", [
    ("native", {24, 93, 96}), ("hourly", {24}), ("15min", {96, 92}),
])
def test_resolution_changes_rows_but_keeps_every_days_mean(choice, rows_per_day):
    # quarter-hour prices that differ within the hour, so averaging matters
    raw = raw_frame("2025-09-30", "2025-10-02",
                    price=lambda t: t.hour + (t.minute / 15) * 10.0)
    sample = pt.select_sample(raw, "2025-09-30", "2025-10-02", "helsinki")
    out = pt.to_resolution(sample, choice)
    assert set(out.groupby("day").size()) <= rows_per_day | {93}
    before = sample.groupby("day").apply(pt.weighted_mean, include_groups=False)
    after = out.groupby("day").apply(pt.weighted_mean, include_groups=False)
    assert (before - after).abs().max() < 1e-9
    assert out["minutes"].sum() == sample["minutes"].sum()  # same hours


def test_weighted_mean_counts_an_hour_as_four_quarters():
    df = pd.DataFrame({"price_eur_mwh": [100.0, 0.0, 0.0, 0.0, 0.0],
                       "minutes": [60, 15, 15, 15, 15]})
    assert ft.weighted_mean(df) == pytest.approx(50.0)  # plain mean would say 20


def test_finish_gives_the_documented_columns_and_types():
    raw = pt.select_sample(raw_frame("2024-01-01", "2024-01-01"),
                           "2024-01-01", "2024-01-01", "helsinki")
    out = pt.finish(raw)
    assert list(out.columns) == ["time_utc", "day", "price_eur_mwh", "minutes"]
    assert str(out["time_utc"].dt.tz) == "UTC"
    assert out["minutes"].dtype == "int16"
