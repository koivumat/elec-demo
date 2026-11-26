"""Zone comparisons (steps 02-03): same processing for all zones. Offline."""

import pandas as pd
import pytest

import describe_tools as dt
import fetch_tools as ft
import process_tools as pt
from test_process import raw_frame


def write_raw(tmp_path, zone, price):
    frame = raw_frame("2024-01-01", "2024-01-03", price=price)
    frame["time_helsinki"] = frame["time_utc"].dt.tz_convert("Europe/Helsinki")
    ft.write_raw_csv(frame, tmp_path / f"prices_{zone}_2024.csv")


SETTINGS = {"sample_start": "2024-01-01", "sample_end": "2024-01-03",
            "planning_day": "helsinki", "known_anomalies": "keep",
            "incomplete_days": "drop", "price_resolution": "native"}


@pytest.fixture
def every(tmp_path):
    write_raw(tmp_path, "FI", lambda t: 10.0 + t.hour)
    write_raw(tmp_path, "EE", lambda t: 10.0 + t.hour if t.hour < 12 else 50.0)
    results = {z: pt.process_zone(z, SETTINGS, tmp_path) for z in ["FI", "EE"]}
    return results, pt.all_zones(results)


def test_all_zones_file_holds_each_zone_unchanged(every):
    results, table = every
    assert list(table.columns) == ["zone", "time_utc", "day", "price_eur_mwh", "minutes"]
    fi = table[table["zone"] == "FI"].drop(columns="zone").reset_index(drop=True)
    assert fi.equals(results["FI"]["out"])


def test_equal_price_share_counts_time_with_the_same_price(every):
    _, table = every
    # EE equals FI in the UTC hours 0-11 only: half of the time
    assert dt.equal_price_share(table, "FI", "EE") == pytest.approx(0.5)
    assert dt.equal_price_share(table, "FI", "FI") == pytest.approx(1.0)


def test_zone_hour_profile_has_one_column_per_zone(every):
    _, table = every
    profile = dt.zone_hour_profile(table)
    assert list(profile.columns) == ["FI", "EE"]
    assert len(profile) == 24


def test_zone_daily_gives_a_table_per_zone(every):
    _, table = every
    daily = dt.zone_daily(table)
    assert set(daily) == {"FI", "EE"}
    assert all(len(d) == 3 for d in daily.values())
    assert isinstance(daily["FI"]["day"].iloc[0], type(pd.Timestamp("2024-01-01").date()))
