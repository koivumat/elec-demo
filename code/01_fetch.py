"""Step 01: download day-ahead prices from ENTSO-E into data/raw/.

Needs the API key in .env, so it runs only with:  python run_all.py --fetch
(or directly: python code/01_fetch.py)

Downloads every zone (FI, SE1, EE) and every year from 2015-01-01 to
2026-10-31, one CSV file per zone and calendar year (Helsinki time), e.g.
data/raw/prices_FI_2024.csv. This step reads no analysis choices: the raw data
is the same for every variant; choices start in step 02.

Writes checks/01_fetch.md and figures/01_fetch_monthly_mean.svg.
"""

import sys

import matplotlib

matplotlib.use("Agg")  # draw to files only, no window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import fetch_tools as ft  # noqa: E402
from common import ROOT, Report, mask, output_dir, read_secret, rel, run, say, start_step  # noqa: E402

STEP = "01_fetch"
RAW_DIR = ROOT / "data" / "raw"
FIGURE = "01_fetch_monthly_mean.svg"
SERIES_COLORS = {"FI": "#257de0", "SE1": "#f47230", "EE": "#00b894"}


# ---------------------------------------------------------------- download


def make_client(api_key):
    from entsoe import EntsoePandasClient

    # retry_count=1: the client does not retry by itself; call_with_retry()
    # does all retrying, with the waits described in fetch_tools.py.
    return EntsoePandasClient(api_key=api_key, retry_count=1,
                              timeout=ft.TIMEOUT_SECONDS)


def fetch_all(client, windows, raw_dir, log=say, sleep=None, throttle=None):
    """Download every window; return {filename: status}.

    A window that fails after all retries keeps any older file and is marked
    FAILED; the other windows still run.
    """
    from entsoe.exceptions import NoMatchingDataError

    kwargs = {} if sleep is None else {"sleep": sleep}
    throttle = throttle if throttle is not None else ft.Throttle()
    status = {}
    for i, w in enumerate(windows, start=1):
        label = f"{w.zone} {w.year}"
        log(f"  [{i:2d}/{len(windows)}] {label}")
        try:
            series = ft.call_with_retry(
                lambda w=w: client.query_day_ahead_prices(
                    ft.ZONES[w.zone], start=w.start, end=w.end),
                label, log, throttle=throttle, **kwargs,
            )
        except NoMatchingDataError:
            status[w.filename] = "no data"
            log(f"    {label}: ENTSO-E has no data for this period")
            continue
        except Exception as error:  # noqa: BLE001 (keep going with the others)
            kept = "older file kept" if (raw_dir / w.filename).exists() else "no file"
            status[w.filename] = f"FAILED: {ft.describe_error(error)} ({kept})"
            log(mask(f"    {label}: FAILED: {error}"))
            continue
        frame = ft.to_raw_frame(series, w.start, w.end)
        ft.write_raw_csv(frame, raw_dir / w.filename)
        status[w.filename] = "downloaded"
    return status


# ------------------------------------------------------------------ report


def fmt(x, digits=2):
    return "-" if pd.isna(x) else f"{x:.{digits}f}"


def load_files(windows, raw_dir):
    """{filename: DataFrame} for the files that exist."""
    return {w.filename: ft.read_raw_csv(raw_dir / w.filename)
            for w in windows if (raw_dir / w.filename).exists()}


def excerpt(rep, df, first, last, caption):
    """Rows of df with first <= time_utc < last, as a table."""
    t0 = pd.Timestamp(first, tz=ft.FILE_TZ).tz_convert("UTC")
    t1 = pd.Timestamp(last, tz=ft.FILE_TZ).tz_convert("UTC")
    rows = df[(df["time_utc"] >= t0) & (df["time_utc"] < t1)]
    rep.text(caption)
    rep.table(
        ["time_utc", "time_helsinki", "price_eur_mwh", "minutes"],
        [[t.strftime("%Y-%m-%dT%H:%M:%SZ"), h, fmt(p), m]
         for t, h, p, m in rows[ft.COLUMNS].itertuples(index=False)],
    )


def draw_figure(frames, path):
    """Monthly mean price per zone, one line each, labelled at the right end."""
    plt.rcParams["svg.hashsalt"] = "elec-demo"  # fixed ids: same file each run
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ends = []  # (last value, last month, zone) for the line-end labels
    for zone, color in SERIES_COLORS.items():
        parts = [df for name, df in frames.items() if name.startswith(f"prices_{zone}_")]
        if not parts:
            continue
        df = pd.concat(parts)
        monthly = (df.set_index(df["time_utc"].dt.tz_convert(ft.FILE_TZ).dt.tz_localize(None))
                   ["price_eur_mwh"].resample("MS").mean())
        ax.plot(monthly.index, monthly.to_numpy(), color=color, linewidth=1.6, label=zone)
        ends.append((float(monthly.iloc[-1]), monthly.index[-1], zone))
    # Labels at the line ends, pushed apart when the lines end close together
    low, high = ax.get_ylim()
    gap = 0.06 * (high - low)
    placed = []
    for y, x, zone in sorted(ends):
        y_label = max(y, placed[-1] + gap) if placed else y
        placed.append(y_label)
        ax.text(x + pd.Timedelta(days=45), y_label, zone, va="center",
                fontsize=9, color="#333333")
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.set_ylabel("EUR/MWh (monthly mean)")
    ax.set_title("Day-ahead prices, monthly mean", loc="left", fontsize=11)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncols=3, loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, format="svg", metadata={"Date": None})
    plt.close(fig)


def build_report(windows, status, frames, figure_path):
    rep = Report(STEP, "Download day-ahead prices")
    rep.text(
        "Day-ahead prices for FI, SE1 and EE from the ENTSO-E Transparency "
        "Platform (https://transparency.entsoe.eu), one CSV file per zone and "
        "calendar year (Helsinki time) in `data/raw/`. Prices in EUR/MWh."
    )

    rep.heading("Download settings (fixed, not choices)")
    rep.table(["setting", "value"], [
        ["zones", ", ".join(ft.ZONES)],
        ["period", f"{ft.FETCH_START} up to (not including) {ft.FETCH_END}"],
        ["files", "one per zone and calendar year in Helsinki time"],
        ["15-minute prices from", "2025-10-01 01:00 Helsinki (= 2025-09-30 22:00 UTC)"],
        ["time-out per request", f"{ft.TIMEOUT_SECONDS} s"],
        ["retries", "network errors, time-outs, HTTP 5xx: after "
                    + ", ".join(f"{s} s" for s in ft.RETRY_WAITS)
                    + f"; HTTP 429: after {ft.RATE_LIMIT_WAIT_SECONDS} s"],
    ])
    rep.text("This step reads no analysis choices: it downloads everything any "
             "choice can select. Retries are printed in the terminal, not here, "
             "so this report is the same however many retries a run needed.")

    # Summary
    counts = pd.Series(list(status.values())).map(
        lambda s: "FAILED" if s.startswith("FAILED") else s).value_counts()
    total_rows = sum(len(df) for df in frames.values())
    size_mb = sum((RAW_DIR / name).stat().st_size for name in frames) / 1e6
    rep.heading("Summary")
    rep.table(["what", "value"], [
        ["files expected", len(windows)],
        ["downloaded in this run", int(counts.get("downloaded", 0))],
        ["no data at ENTSO-E", int(counts.get("no data", 0))],
        ["FAILED", int(counts.get("FAILED", 0))],
        ["rows in all files", total_rows],
        ["size of all files", f"{size_mb:.1f} MB"],
    ])

    # Files
    checks = {}
    rows = []
    for w in windows:
        df = frames.get(w.filename)
        if df is None:
            rows.append([w.filename, status.get(w.filename, "-")] + ["-"] * 8)
            continue
        c = ft.check_frame(df, w.start, w.end)
        checks[w.filename] = c
        rows.append([w.filename, status.get(w.filename, "-"), c["rows"], c["expected"],
                     c["missing"], c["extra"], c["duplicates"], c["empty_prices"],
                     c["rows_60"], c["rows_15"]])
    rep.heading("Files: rows")
    rep.text("EXPECT: rows = expected (8760 hours a year, 8784 in leap years; "
             "2025 mixes hours and quarter-hours; 2026 has quarter-hours), and "
             "0 missing, 0 extra, 0 duplicates, 0 empty prices.")
    rep.table(["file", "status", "rows", "expected", "missing", "extra",
               "duplicates", "empty prices", "60-min rows", "15-min rows"], rows)

    rep.heading("Files: prices (EUR/MWh)")
    rep.text(f"EXPECT: no price below {ft.PRICE_FLOOR:.0f}, the market's minimum price.")
    rep.table(["file", "min", "mean", "max", "negative rows", f"below {ft.PRICE_FLOOR:.0f}"],
              [[name, fmt(c["min"]), fmt(c["mean"]), fmt(c["max"]), c["negative"],
                c["below_floor"]] for name, c in checks.items()])

    # Days
    rep.heading("Days with an unexpected number of rows")
    odd = []
    for w in windows:
        if w.filename in frames:
            for day, exp, seen in ft.odd_days(frames[w.filename], w.start, w.end):
                odd.append((w.filename, day, exp, seen))
    if odd:
        rep.text(f"{len(odd)} day(s). EXPECT: none. The first 20:")
        rep.table(["file", "day (Helsinki)", "expected rows", "seen rows"],
                  [[n, str(d), e, s] for n, d, e, s in odd[:20]])
    else:
        rep.text("None. EXPECT: none.")

    fi = {w.year: w for w in windows if w.zone == "FI"}
    rep.heading("Daylight saving days (FI)")
    rep.text("EXPECT: 23 hours in spring and 25 in autumn, so 23 or 25 rows; after "
             "the switch to 15 minutes, 92 or 100 rows.")
    dst_rows = []
    for w in fi.values():
        df = frames.get(w.filename)
        seen = ft.day_counts(df["time_utc"]) if df is not None else pd.Series(dtype=int)
        for day, hours, exp in ft.daylight_saving_days(w.start, w.end):
            dst_rows.append([str(day), hours, exp, int(seen.get(day, 0))])
    rep.table(["day", "hours", "expected rows", "seen rows"], dst_rows)

    # Excerpts
    rep.heading("Excerpts")
    if "prices_FI_2015.csv" in frames:
        excerpt(rep, frames["prices_FI_2015.csv"], "2015-01-01 00:00", "2015-01-01 04:00",
                "First rows of `prices_FI_2015.csv`:")
    if "prices_FI_2025.csv" in frames:
        excerpt(rep, frames["prices_FI_2025.csv"], "2025-09-30 23:00", "2025-10-01 02:00",
                "The switch to 15 minutes in `prices_FI_2025.csv` (EXPECT: hourly rows "
                "until 00:00, quarter-hours from 01:00 Helsinki):")
        excerpt(rep, frames["prices_FI_2025.csv"], "2025-10-26 02:45", "2025-10-26 04:15",
                "The autumn daylight saving night 2025-10-26 (EXPECT: the hour 03:00-04:00 "
                "Helsinki twice, first +03:00, then +02:00):")

    # Facts
    rep.heading("Facts to recognise: EXPECT next to SEE")
    facts = []
    all_fi = pd.concat([frames[w.filename] for w in fi.values() if w.filename in frames]) \
        if any(w.filename in frames for w in fi.values()) else None
    if all_fi is not None:
        local = all_fi["time_utc"].dt.tz_convert(ft.FILE_TZ)
        yearly = all_fi.groupby(local.dt.year)["price_eur_mwh"].mean()
        facts.append(["FI: highest yearly mean price in 2022 (energy crisis)",
                      f"highest: {yearly.idxmax()} ({fmt(yearly.max())} EUR/MWh)"])
        day = all_fi[local.dt.date == pd.Timestamp("2023-11-24").date()]
        facts.append(["FI 2023-11-24: many hours at -500 (a trader's erroneous bid)",
                      f"{int((day['price_eur_mwh'] <= -499.99).sum())} rows at -500; "
                      f"day mean {fmt(day['price_eur_mwh'].mean())}"])
        # Count hours, not rows: a 15-minute row is a quarter of an hour.
        neg = (all_fi.assign(year=local.dt.year, hours=all_fi["minutes"] / 60)
               .query("price_eur_mwh < 0").groupby("year")["hours"].sum()
               .reindex(yearly.index, fill_value=0))
        facts.append(["FI: hours with a negative price rare before 2023, "
                      "frequent from 2023",
                      "; ".join(f"{y}: {h:g} h" for y, h in neg.items())])
        is60 = all_fi["minutes"] == 60
        if is60.any() and (~is60).any():
            facts.append(["FI: last hourly row 2025-10-01 00:00, first 15-min row "
                          "01:00 (Helsinki)",
                          f"last hourly {local[is60].max():%Y-%m-%d %H:%M}, "
                          f"first 15-min {local[~is60].min():%Y-%m-%d %H:%M}"])
    lowest = min((c["min"] for c in checks.values()), default=float("nan"))
    facts.append([f"No price below {ft.PRICE_FLOOR:.0f} in any zone",
                  f"lowest price seen: {fmt(lowest)}"])
    rep.table(["EXPECT", "SEE"], facts)

    rep.heading("Highest and lowest prices per zone")
    rep.text("Do you recognise these dates?")
    extremes = []
    for zone in ft.ZONES:
        parts = [df for name, df in frames.items() if name.startswith(f"prices_{zone}_")]
        if not parts:
            continue
        df = pd.concat(parts).dropna(subset=["price_eur_mwh"])
        top = df.nlargest(5, "price_eur_mwh", keep="first")
        bottom = df.nsmallest(5, "price_eur_mwh", keep="first")
        for kind, part in (("highest", top), ("lowest", bottom)):
            for t, h, p, m in part[ft.COLUMNS].itertuples(index=False):
                extremes.append([zone, kind, h, fmt(p)])
    rep.table(["zone", "kind", "time (Helsinki)", "EUR/MWh"], extremes)

    rep.heading("Figure")
    rep.text(f"![Monthly mean day-ahead prices](../figures/{figure_path.name})")
    rep.text("EXPECT: a peak in 2022 for all zones; FI and EE close to each other "
             "most of the time; SE1 lower.")

    rep.heading("What the ENTSO-E client changes")
    rep.bullets([
        "ENTSO-E leaves out a price when it repeats the previous one; the client "
        "fills it back in.",
        "Before 2025-10-01 the client builds a full hourly grid, so a missing "
        "hour shows as an empty price (counted above).",
        "The client returns local time; the files store UTC (`time_utc`) and, "
        "for reading only, Helsinki time (`time_helsinki`).",
        "`minutes` follows the market rule: 60 before the switch, 15 after.",
    ])

    rep.heading("What a person should check")
    rep.bullets([
        "Summary: every file downloaded, none FAILED.",
        "Files: rows = expected, nothing missing or duplicated. If something is "
        "missing, look at the days table: which days, and is it ENTSO-E or us?",
        "Excerpts: the switch to 15 minutes and the double hour in October look right.",
        "Facts and extremes: the dates make sense to you.",
        "Figure: the shape matches what you know about these markets.",
    ])
    return rep


# -------------------------------------------------------------------- main


def main(client=None, windows=None, sleep=None, throttle=None):
    settings, variant = start_step(__doc__)
    if variant is not None:
        say("Note: step 01 reads no choices, so --set is ignored here. "
            "Raw data is the same for every variant.")

    if client is None:
        key = read_secret("ENTSOE_API_KEY")
        if key is None:
            say("ERROR: ENTSOE_API_KEY not found in .env (see notes/dev-loop.md).")
            sys.exit(2)
        client = make_client(key)

    windows = windows if windows is not None else ft.year_windows()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    say(f"Downloading {len(windows)} files (zone x year) into data/raw/ ...")
    status = fetch_all(client, windows, RAW_DIR, sleep=sleep, throttle=throttle)

    frames = load_files(windows, RAW_DIR)
    figure_path = output_dir("figures") / FIGURE
    draw_figure(frames, figure_path)
    path = build_report(windows, status, frames, figure_path).write()

    failed = [name for name, s in status.items() if s.startswith("FAILED")]
    nodata = [name for name, s in status.items() if s == "no data"]
    say(f"Downloaded {len(status) - len(failed) - len(nodata)} of {len(windows)}; "
        f"no data: {len(nodata)}; failed: {len(failed)}")
    say(f"Report written: {rel(path)}")
    say(f"Figure written: {rel(figure_path)}")
    if failed:
        say("Some downloads failed. Run the same command again later; "
            "files that worked are simply downloaded again.")
        sys.exit(1)


if __name__ == "__main__":
    run(main)
