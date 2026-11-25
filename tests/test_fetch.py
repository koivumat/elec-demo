"""Step 01 (fetch): windows, retries, raw files and checks, all offline.

A fake client stands in for ENTSO-E: no test ever calls the API.
"""

import importlib

import pandas as pd
import pytest
import requests

import choices
import fetch_tools as ft

FAKE_KEY = "11111111-2222-3333-4444-555555555555"
TZ = ft.FILE_TZ


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=response)


# --------------------------------------------------------------- windows


def test_zones_match_the_bidding_zone_choice():
    c = choices.CHOICES["bidding_zone"]
    assert set(ft.ZONES) == {c.default, *c.alternatives}


def test_year_windows_cover_the_period_without_overlap():
    windows = ft.year_windows(zones=["FI"], start="2015-01-01", end="2026-11-01")
    assert [w.year for w in windows] == list(range(2015, 2027))
    for a, b in zip(windows, windows[1:]):
        assert a.end == b.start  # no gap, no overlap
    assert windows[-1].end == pd.Timestamp("2026-11-01", tz=TZ)
    assert windows[0].filename == "prices_FI_2015.csv"


# ------------------------------------------------------- expected counts


def test_expected_rows_in_hourly_years():
    assert len(ft.expected_index(pd.Timestamp("2023-01-01", tz=TZ),
                                 pd.Timestamp("2024-01-01", tz=TZ))) == 8760
    assert len(ft.expected_index(pd.Timestamp("2024-01-01", tz=TZ),
                                 pd.Timestamp("2025-01-01", tz=TZ))) == 8784


def test_daylight_saving_days_have_23_25_or_92_100_rows():
    days = {str(d): (h, n) for d, h, n in ft.daylight_saving_days(
        pd.Timestamp("2024-01-01", tz=TZ), pd.Timestamp("2026-07-01", tz=TZ))}
    assert days["2024-03-31"] == (23, 23)  # hourly era, spring
    assert days["2024-10-27"] == (25, 25)  # hourly era, autumn
    assert days["2025-10-26"] == (25, 100)  # 15-minute era, autumn
    assert days["2026-03-29"] == (23, 92)  # 15-minute era, spring


def test_switch_day_has_one_hour_then_quarter_hours():
    day = pd.Timestamp("2025-10-01", tz=TZ)
    idx = ft.expected_index(day, day + pd.Timedelta(days=1))
    assert len(idx) == 1 + 23 * 4
    assert ft.minutes_for(idx)[0] == 60 and ft.minutes_for(idx)[1] == 15


# --------------------------------------------------------------- retries


def run_with_failures(errors, result="ok"):
    """Call a function that raises `errors` one by one, then returns."""
    errors = list(errors)
    calls, waits, logs = [], [], []

    def func():
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return result

    out = ft.call_with_retry(func, "FI 2024", logs.append, sleep=waits.append)
    return out, len(calls), waits, logs


def test_server_errors_and_timeouts_are_retried_with_growing_waits():
    out, calls, waits, _ = run_with_failures(
        [http_error(503), requests.ReadTimeout("slow"), requests.ConnectionError("x")])
    assert out == "ok" and calls == 4
    assert waits == list(ft.RETRY_WAITS[:3])


def test_rate_limit_waits_out_the_ban():
    out, calls, waits, _ = run_with_failures([http_error(429)])
    assert out == "ok" and waits == [ft.RATE_LIMIT_WAIT_SECONDS]


def test_wrong_key_is_not_retried():
    with pytest.raises(requests.HTTPError):
        run_with_failures([http_error(401)])


def test_gives_up_after_the_last_attempt():
    errors = [http_error(503)] * (len(ft.RETRY_WAITS) + 1)
    with pytest.raises(requests.HTTPError):
        run_with_failures(errors)


def test_throttle_spaces_calls():
    now, waits = [0.0], []
    throttle = ft.Throttle(2.0, clock=lambda: now[0], sleep=waits.append)
    throttle.wait()
    now[0] = 0.5
    throttle.wait()
    assert waits == [1.5]


# ------------------------------------------------------- raw files, checks


def fake_series(start, end, tz="Europe/Helsinki"):
    """Prices like the client returns them: local time, end included."""
    idx = ft.expected_index(start, end).append(pd.DatetimeIndex([end.tz_convert("UTC")]))
    values = [float(i % 7) - 1.25 for i in range(len(idx))]
    return pd.Series(values, index=idx.tz_convert(tz))


def test_raw_frame_drops_the_end_point_and_stores_utc():
    start, end = pd.Timestamp("2025-09-30", tz=TZ), pd.Timestamp("2025-10-02", tz=TZ)
    frame = ft.to_raw_frame(fake_series(start, end, "Europe/Stockholm"), start, end)
    assert frame["time_utc"].max() < end
    c = ft.check_frame(frame, start, end)
    assert (c["missing"], c["extra"], c["duplicates"]) == (0, 0, 0)
    assert c["rows_60"] == 24 + 1 and c["rows_15"] == 23 * 4


def test_csv_round_trip_gives_the_same_bytes(tmp_path):
    start, end = pd.Timestamp("2024-03-30", tz=TZ), pd.Timestamp("2024-04-01", tz=TZ)
    frame = ft.to_raw_frame(fake_series(start, end), start, end)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    ft.write_raw_csv(frame, a)
    ft.write_raw_csv(ft.to_raw_frame(fake_series(start, end), start, end), b)
    assert a.read_bytes() == b.read_bytes()
    first = a.read_text(encoding="utf-8").splitlines()[:2]
    assert first[0] == "time_utc,time_helsinki,price_eur_mwh,minutes"
    assert first[1] == "2024-03-29T22:00:00Z,2024-03-30T00:00:00+02:00,-1.25,60"
    back = ft.read_raw_csv(a)
    assert ft.check_frame(back, start, end)["missing"] == 0


def test_checks_find_a_missing_hour_and_a_duplicate():
    start, end = pd.Timestamp("2024-01-01", tz=TZ), pd.Timestamp("2024-01-02", tz=TZ)
    frame = ft.to_raw_frame(fake_series(start, end), start, end)
    broken = pd.concat([frame.drop(index=5), frame.iloc[[10]]]).reset_index(drop=True)
    c = ft.check_frame(broken, start, end)
    assert c["missing"] == 1 and c["duplicates"] == 1


# ------------------------------------------------- the step, fake client


class FakeClient:
    """Answers like EntsoePandasClient; fails the first call with HTTP 503,
    then a URL with the key in it, to check retries and masking."""

    def __init__(self, fail_zone_year=None):
        self.calls = 0
        self.fail_zone_year = fail_zone_year

    def query_day_ahead_prices(self, area, start, end):
        self.calls += 1
        if self.calls == 1:
            raise http_error(503)
        if (area, start.year) == self.fail_zone_year:
            raise http_error(401).__class__(
                f"401 for url https://web-api.tp.entsoe.eu/api?securityToken={FAKE_KEY}",
                response=http_error(401).response)
        return fake_series(start, end)


def test_fetch_all_retries_continues_after_a_failure_and_masks_the_key(tmp_path):
    step = importlib.import_module("01_fetch")
    windows = ft.year_windows(zones=["FI", "EE"], start="2024-12-30", end="2025-01-02")
    logs = []
    status = step.fetch_all(FakeClient(fail_zone_year=("EE", 2025)), windows, tmp_path,
                            log=logs.append,  # raw: masking must happen in fetch_all
                            sleep=lambda s: None, throttle=ft.Throttle(0))
    assert status["prices_FI_2024.csv"] == "present"  # after one 503 retry
    assert status["prices_EE_2025.csv"].startswith("FAILED: HTTP 401")
    assert status["prices_EE_2024.csv"] == "present"
    assert any("retrying" in line for line in logs)
    assert FAKE_KEY not in "\n".join(logs)


def test_existing_files_are_not_downloaded_again(tmp_path):
    step = importlib.import_module("01_fetch")
    windows = ft.year_windows(zones=["FI"], start="2024-12-30", end="2025-01-02")
    existing = tmp_path / "prices_FI_2024.csv"
    existing.write_text("kept as it is\n", encoding="utf-8")

    class CountingClient:
        def __init__(self):
            self.asked = []

        def query_day_ahead_prices(self, area, start, end):
            self.asked.append(start.year)
            return fake_series(start, end)

    client = CountingClient()
    status = step.fetch_all(client, windows, tmp_path, log=lambda m: None,
                            sleep=lambda s: None, throttle=ft.Throttle(0))
    assert client.asked == [2025]  # only the missing file was requested
    assert existing.read_text(encoding="utf-8") == "kept as it is\n"
    assert status == {"prices_FI_2024.csv": "present", "prices_FI_2025.csv": "present"}
