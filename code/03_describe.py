"""Step 03: describe the prices that the battery will face.

Reads data/processed/prices.parquet (step 02; or the variant's copy) and
writes:
- checks/03_describe.md                   the check report
- results/03_yearly.csv                   price level and daily spreads per year
- results/03_upper_bound.csv              upper bound of what a battery can earn
- figures/03_monthly.svg                  monthly mean price and daily spread
- figures/03_hour_profile.svg             mean price by hour of day, per year
- figures/03_spread_by_year.svg           daily 2-hour spread, per year
(non-default runs: the same under variants/<name>/).

Run:  python run_all.py --steps 03     (needs step 02 first: --steps 02-03)
"""

import matplotlib

matplotlib.use("Agg")  # draw to files only, no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import describe_tools as dt  # noqa: E402
from common import Report, output_dir, rel, run, say, start_step  # noqa: E402

STEP = "03_describe"
BLUE = "#257de0"
# Ordinal blue ramp (light -> dark) for years; validated, see notes/decisions.md
YEAR_RAMP = ["#84b9f3", "#6aabf1", "#519ced", "#338ced", "#257de0",
             "#2370cd", "#1b64be", "#1757ac", "#0f4a96", "#0e3d7e"]
TEXT = "#333333"
GRID = "#e6e6e6"


def fmt(x, digits=2):
    return "-" if pd.isna(x) else f"{x:.{digits}f}"


def year_colors(years):
    """Evenly spaced steps of the ramp, light for early years, dark for late."""
    idx = np.linspace(0, len(YEAR_RAMP) - 1, num=len(years)).round().astype(int)
    return dict(zip(years, (YEAR_RAMP[i] for i in idx)))


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, format="svg", metadata={"Date": None})
    plt.close(fig)


# ------------------------------------------------------------------ figures


def figure_monthly(daily, path):
    monthly = daily.groupby("month").agg(mean=("mean", "mean"),
                                         spread=("spread_2h", "mean"))
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    a.plot(monthly.index, monthly["mean"], color=BLUE, linewidth=1.6)
    a.set_title("Mean price, EUR/MWh (monthly mean of daily means)", loc="left", fontsize=10)
    b.plot(monthly.index, monthly["spread"], color=BLUE, linewidth=1.6)
    b.set_title("Daily 2-hour spread, EUR/MWh (monthly mean)", loc="left", fontsize=10)
    for ax in (a, b):
        style(ax)
        ax.axhline(0, color="#999999", linewidth=0.8)
    save(fig, path)


def figure_hour_profile(profile, path):
    years = list(profile.columns)
    colors = year_colors(years)
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ends = []
    for y in years:
        ax.plot(profile.index, profile[y], color=colors[y], linewidth=1.6, label=str(y))
        ends.append((float(profile[y].iloc[-1]), y))
    low, high = ax.get_ylim()
    gap, placed = 0.05 * (high - low), []
    for value, y in sorted(ends):  # labels at the line ends, pushed apart
        pos = max(value, placed[-1] + gap) if placed else value
        placed.append(pos)
        ax.text(23.4, pos, str(y), va="center", fontsize=8, color=TEXT)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlim(0, 24.5)
    ax.set_xlabel("hour of day, Helsinki time", fontsize=9)
    ax.set_title("Mean price by hour of day, EUR/MWh", loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8, ncols=min(len(years), 6),
              loc="upper center", bbox_to_anchor=(0.5, -0.2))  # below: off the lines
    style(ax)
    save(fig, path)


def figure_spread_by_year(daily, path):
    years = sorted(daily["year"].unique())
    data = [daily.loc[daily["year"] == y, "spread_2h"].to_numpy() for y in years]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.boxplot(data, tick_labels=[str(y) for y in years], whis=(5, 95),
               showfliers=False, widths=0.5,
               medianprops={"color": BLUE, "linewidth": 2},
               boxprops={"color": TEXT}, whiskerprops={"color": TEXT},
               capprops={"color": TEXT})
    ax.set_title("Daily 2-hour spread, EUR/MWh (box: middle half of days; "
                 "whiskers: 5th to 95th percentile)", loc="left", fontsize=10)
    style(ax)
    save(fig, path)


# -------------------------------------------------------------------- main


def main():
    settings, variant = start_step(__doc__)
    src = output_dir("data/processed", variant) / "prices.parquet"
    if not src.exists():
        say(f"ERROR: {rel(src)} not found. Run step 02 first: "
            "python run_all.py --steps 02-03")
        raise SystemExit(2)
    df = pd.read_parquet(src)

    daily = dt.daily_table(df)
    yearly = dt.yearly_table(df, daily)
    bound = dt.upper_bound_table(daily)
    profile = dt.hour_profile(df)

    results = output_dir("results", variant)
    yearly.round(4).to_csv(results / "03_yearly.csv", lineterminator="\n")
    bound.round(4).to_csv(results / "03_upper_bound.csv", lineterminator="\n")

    plt.rcParams["svg.hashsalt"] = "elec-demo"  # fixed ids: same file each run
    figs = output_dir("figures", variant)
    figure_monthly(daily, figs / "03_monthly.svg")
    figure_hour_profile(profile, figs / "03_hour_profile.svg")
    figure_spread_by_year(daily, figs / "03_spread_by_year.svg")

    # ------------------------------------------------------------- report
    zone = settings["bidding_zone"]
    rep = Report(STEP, "Describe prices")
    rep.text(
        f"Zone **{zone}**, planning days {daily['day'].min()} to {daily['day'].max()} "
        f"({len(daily)} days, {len(df)} rows, resolution "
        f"{settings['price_resolution']}), from `{rel(src)}`. All means are "
        "time-weighted: an hour counts as much as four quarter-hours."
    )
    rep.text("**Daily spread** (h hours): the mean price of the most expensive h "
             "hours of a day minus the mean price of its cheapest h hours. It is "
             "what one battery cycle a day can gain, per MWh, before losses.")

    rep.heading("Per year")
    rep.table(["year", "days", "mean", "min", "max", "negative hours",
               "spread 1 h", "spread 2 h", "spread 4 h"],
              [[y, int(r.days), fmt(r["mean"]), fmt(r["min"]), fmt(r["max"]),
                fmt(r.negative_hours, 2).rstrip("0").rstrip("."),
                fmt(r.mean_spread_1h), fmt(r.mean_spread_2h), fmt(r.mean_spread_4h)]
               for y, r in yearly.iterrows()])
    rep.text("Prices in EUR/MWh; spreads are means over the days of the year. "
             "The same table: `" + rel(results / "03_yearly.csv") + "`.")

    rep.heading("Upper bound: what a battery could earn at most")
    rep.text("EUR per kWh of storage per year, for a battery that fills or empties "
             "in 1, 2 or 4 hours, makes one full cycle a day, has no losses, and "
             "buys and sells at the day-ahead price. Day-ahead prices are known "
             "the day before, so the planning itself is realistic; everything "
             "else (losses, wear, taxes, fees, the gap between buying and "
             "selling prices) only lowers this. Steps 04 and 05 add those.")
    rep.table(["year", "days", "1-hour battery", "2-hour battery", "4-hour battery"],
              [[y, int(r.days), fmt(r.eur_per_kwh_1h), fmt(r.eur_per_kwh_2h),
                fmt(r.eur_per_kwh_4h)] for y, r in bound.iterrows()])
    full = bound[bound["days"] >= 365]
    if len(full):
        rep.text(f"Over the full years here ({full.index.min()}-{full.index.max()}), "
                 f"a 2-hour battery could earn at most "
                 f"{fmt(full['eur_per_kwh_2h'].mean())} EUR per kWh a year on average "
                 f"(a 10 kWh battery: {fmt(10 * full['eur_per_kwh_2h'].mean(), 0)} EUR). "
                 f"Table: `{rel(results / '03_upper_bound.csv')}`.")

    rep.heading("Facts to recognise: EXPECT next to SEE")
    rep.text("The EXPECT column is written for FI; other zones may differ.")
    overall = (df.assign(hour=pd.DatetimeIndex(df["time_utc"]).tz_convert(dt.HELSINKI).hour,
                         pw=df["price_eur_mwh"] * df["minutes"])
               .groupby("hour")[["pw", "minutes"]].sum())
    by_hour = (overall["pw"] / overall["minutes"]).sort_values()
    facts = [
        ["Highest mean price in 2022 (energy crisis)",
         f"{yearly['mean'].idxmax()} ({fmt(yearly['mean'].max())})"],
        ["Largest daily spreads in 2022",
         f"largest mean 2-hour spread: {yearly['mean_spread_2h'].idxmax()} "
         f"({fmt(yearly['mean_spread_2h'].max())})"],
        ["Cheapest hours at night (about 02-05), most expensive in the morning "
         "(about 08-09) and evening (about 18-20), Helsinki time",
         "cheapest: " + ", ".join(f"{h:02d}" for h in by_hour.index[:3])
         + "; most expensive: " + ", ".join(f"{h:02d}" for h in by_hour.index[::-1][:3])],
        ["Negative prices rare in 2022, frequent from 2023",
         "; ".join(f"{y}: {fmt(h, 2).rstrip('0').rstrip('.')} h"
                   for y, h in yearly["negative_hours"].items())],
    ]
    quarter_days = df.groupby("day")["minutes"].transform("min") == 15
    q = df[quarter_days & (df["minutes"] == 15)]
    if len(q):
        q_daily = dt.daily_table(q.groupby("day").filter(lambda g: g["minutes"].sum() >= 23 * 60))
        hourly = (q.assign(time_utc=q["time_utc"].dt.floor("h"))
                  .groupby(["time_utc", "day"], as_index=False)["price_eur_mwh"].mean()
                  .assign(minutes=60))
        h_daily = dt.daily_table(hourly[hourly["day"].isin(set(q_daily["day"]))])
        facts.append([
            "On 15-minute days, the 1-hour spread from quarter-hours is at least "
            "as large as from hourly means (averaging hides the extremes)",
            f"{len(q_daily)} days: {fmt(q_daily['spread_1h'].mean())} from quarter-hours, "
            f"{fmt(h_daily['spread_1h'].mean())} from hourly means"])
    rep.table(["EXPECT", "SEE"], facts)

    rep.heading("Days with the largest 2-hour spread")
    rep.text("Do you recognise these days?")
    top = daily.nlargest(8, "spread_2h")
    rep.table(["day", "mean", "min", "max", "spread 2 h"],
              [[str(r.day), fmt(r["mean"]), fmt(r["min"]), fmt(r["max"]),
                fmt(r.spread_2h)] for _, r in top.iterrows()])

    rep.heading("Figures")
    for name, text in [
        ("03_monthly.svg", "Monthly mean price and mean daily 2-hour spread. "
         "EXPECT: both high in 2022; spreads stay large after prices fall."),
        ("03_hour_profile.svg", "Mean price by hour of day, one line per year "
         "(light: early years, dark: late). EXPECT: a night low and morning and "
         "evening peaks every year."),
        ("03_spread_by_year.svg", "Daily 2-hour spread per year. EXPECT: most "
         "days well below the mean, a few very large days pulling the mean up."),
    ]:
        rep.text(f"![{name}](../figures/{name})")
        rep.text(text)

    rep.choices_in_effect(settings)
    rep.heading("What a person should check")
    rep.bullets([
        "Per year: the days add up to step 02's count; the means look like the "
        "prices you know.",
        "Upper bound: the order of magnitude is plausible (tens of EUR per kWh "
        "a year, not thousands). It is a ceiling, not a forecast.",
        "Facts: the hours and years match what you know about Finnish prices.",
        "Figures: the profile has the night low and the two peaks.",
    ])
    report = rep.write(variant)
    say(f"{zone}: {len(daily)} days described")
    say(f"Report written: {rel(report)}")


if __name__ == "__main__":
    run(main)
