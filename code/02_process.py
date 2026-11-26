"""Step 02: from the raw CSVs to one clean price series for the analysis.

Reads data/raw/ (written by step 01) and the choices bidding_zone,
sample_start, sample_end, planning_day, known_anomalies, incomplete_days and
price_resolution. Writes data/processed/prices.parquet (the chosen zone),
data/processed/prices_all_zones.parquet (every zone, processed the same way,
for comparisons) and checks/02_process.md (or the same under
variants/<name>/).

Run:  python run_all.py --steps 02      (or with --set name=value)
"""

import pandas as pd

import fetch_tools as ft
import process_tools as pt
from common import ROOT, Report, output_dir, rel, run, say, start_step

STEP = "02_process"
RAW_DIR = ROOT / "data" / "raw"
OUT_NAME = "prices.parquet"
ALL_NAME = "prices_all_zones.parquet"


def fmt(x, digits=2):
    return "-" if pd.isna(x) else f"{x:.{digits}f}"


def rows_table(df, n=3):
    """First and last n rows of the output, as table rows."""
    part = pd.concat([df.head(n), df.tail(n)])
    return [[t.strftime("%Y-%m-%dT%H:%M:%SZ"),
             t.tz_convert("Europe/Helsinki").strftime("%Y-%m-%d %H:%M"),
             str(d), fmt(p), m]
            for t, d, p, m in part.itertuples(index=False)]


def main():
    settings, variant = start_step(__doc__)
    zone = settings["bidding_zone"]
    first, last = settings["sample_start"], settings["sample_end"]
    pday = settings["planning_day"]

    # Every zone goes through exactly the same steps; the chosen zone is the
    # analysis series, all zones together are for comparisons (step 03).
    results = {z: pt.process_zone(z, settings, RAW_DIR) for z in ft.ZONES}
    r = results[zone]
    raw, files, sample = r["raw"], r["files"], r["sample"]
    no_anomalies, anomaly_days = r["no_anomalies"], r["anomaly_days"]
    days, incomplete, kept, out = r["days"], r["incomplete"], r["kept"], r["out"]

    folder = output_dir("data/processed", variant)
    path = folder / OUT_NAME
    out.to_parquet(path, index=False, engine="pyarrow", compression="zstd")
    back = pd.read_parquet(path)
    every = pt.all_zones(results)
    path_all = folder / ALL_NAME
    every.to_parquet(path_all, index=False, engine="pyarrow", compression="zstd")
    back_all = pd.read_parquet(path_all)

    # ------------------------------------------------------------- report
    rep = Report(STEP, "Process prices")
    rep.text(f"From the raw files of zone **{zone}** to one price series in "
             f"`{rel(path)}`, for the planning days {first} to {last}.")

    rep.heading("Rows at each stage")
    rep.table(["stage", "rows", "hours of prices"], [
        [f"raw files ({len(files)}: {files[0].name} .. {files[-1].name})",
         len(raw), fmt(raw["minutes"].sum() / 60, 0)],
        [f"days {first} to {last} ({pday} days)", len(sample),
         fmt(sample["minutes"].sum() / 60, 0)],
        [f"known anomalies: {settings['known_anomalies']}", len(no_anomalies),
         fmt(no_anomalies["minutes"].sum() / 60, 0)],
        [f"incomplete days: {settings['incomplete_days']}", len(kept),
         fmt(kept["minutes"].sum() / 60, 0)],
        [f"resolution: {settings['price_resolution']}", len(out),
         fmt(out["minutes"].sum() / 60, 0)],
    ])
    rep.text("EXPECT: the hours of prices do not change in the last stage; "
             "only the number of rows can (one hour = 1 or 4 rows).")

    rep.heading("Days")
    n_days = len(days) + len(anomaly_days)
    rep.table(["what", "days"], [
        ["days in the sample", n_days],
        ["complete", int(days["complete"].sum())],
        ["incomplete", len(incomplete)],
        ["dropped as known anomalies", len(anomaly_days)],
        ["days in the output", out["day"].nunique()],
    ])
    if len(incomplete):
        rep.text(f"Incomplete days (first 20 of {len(incomplete)}), "
                 f"{'dropped' if settings['incomplete_days'] == 'drop' else 'kept'}:")
        rep.table(["day", "expected rows", "seen rows"],
                  [[str(d), int(r.expected), int(r.seen)]
                   for d, r in incomplete.head(20).iterrows()])
    else:
        rep.text("No incomplete days.")
    if anomaly_days:
        rep.table(["dropped day", "why"],
                  [[str(d), pt.KNOWN_ANOMALIES[zone][str(d)]] for d in anomaly_days])
    rep.text("EXPECT for the default (FI, 2022-01-01 to 2026-10-31, Helsinki days): "
             "1765 days, all complete. With planning_day=market the last day is "
             "incomplete, because the raw data ends at midnight Helsinki time, "
             "an hour before the market day ends.")

    rep.heading("Rows per day")
    per_day = out.groupby("day").size().value_counts().sort_index()
    rep.table(["rows in a day", "number of days"],
              [[int(k), int(v)] for k, v in per_day.items()])
    rep.text("EXPECT, native resolution with Helsinki days: 24 rows on ordinary "
             "days before the switch and 96 after; 23 and 25 on daylight saving "
             "days (92 and 100 after the switch); 93 on 2025-10-01 (one hour, "
             "then 92 quarter-hours). Hourly: 23, 24, 25 only. 15min: 92, 96, 100 only.")

    rep.heading("Does the resolution change keep the prices?")
    before, after = pt.weighted_mean(kept), pt.weighted_mean(out)
    daily_before = kept.groupby("day").apply(pt.weighted_mean, include_groups=False)
    daily_after = out.groupby("day").apply(pt.weighted_mean, include_groups=False)
    worst = float((daily_before - daily_after.reindex(daily_before.index)).abs().max())
    rep.table(["check", "before", "after"], [
        ["time-weighted mean price (EUR/MWh)", fmt(before, 4), fmt(after, 4)],
        ["largest change in a day's mean price", "", fmt(worst, 6)],
    ])
    rep.text("EXPECT: the same mean before and after, and 0 change in every day.")

    rep.heading(f"The output file: `{rel(path)}`")
    rep.table(["column", "type", "meaning"], [
        ["time_utc", str(back["time_utc"].dtype),
         "start of the interval (UTC; convert to Helsinki for reading)"],
        ["day", f"{back['day'].dtype} (Parquet date)", f"planning day ({pday})"],
        ["price_eur_mwh", str(back["price_eur_mwh"].dtype), "day-ahead price, EUR/MWh"],
        ["minutes", str(back["minutes"].dtype), "length of the interval: 60 or 15"],
    ])
    rep.text(f"{len(back)} rows. Read back from disk and compared with what was "
             f"written: {'identical' if back.equals(out) else 'DIFFERENT (problem)'}.")
    rep.text("First and last rows:")
    rep.table(["time_utc", "Helsinki time", "day", "price_eur_mwh", "minutes"],
              rows_table(back))

    rep.heading(f"All zones, for comparisons: `{rel(path_all)}`")
    rep.text("Every zone went through exactly the same steps and choices as "
             f"{zone} above. Columns as above, plus `zone` (category).")
    rep.table(["zone", "rows", "days", "incomplete days", "dropped anomaly days",
               "time-weighted mean"],
              [[z, len(res["out"]), res["out"]["day"].nunique(), len(res["incomplete"]),
                len(res["anomaly_days"]), fmt(pt.weighted_mean(res["out"]))]
               for z, res in results.items()])
    same = back_all[back_all["zone"] == zone].drop(columns="zone").reset_index(drop=True)
    rep.text(f"{len(back_all)} rows. The {zone} rows equal `{rel(path)}`: "
             f"{'yes' if same.equals(back) else 'NO (problem)'}. EXPECT for the "
             "default: 1765 days in every zone.")

    rep.choices_in_effect(settings)
    rep.heading("What a person should check")
    rep.bullets([
        "Rows at each stage: nothing disappears that you did not ask for.",
        "Days: the number of days is right for the sample period, and any "
        "dropped day makes sense.",
        "Rows per day: only the counts listed under EXPECT appear.",
        "The resolution change keeps every day's mean price.",
        "The output file has the four columns, and the first and last rows "
        "are the first and last hours you expect.",
    ])
    report = rep.write(variant)
    say(f"{zone}: {len(out)} rows, {out['day'].nunique()} days -> {rel(path)}")
    say(f"Report written: {rel(report)}")


if __name__ == "__main__":
    run(main)
