# Check report 02_process: Process prices

Written by `code/02_process.py`. Rerun with `python run_all.py --steps 02`.

From the raw files of zone **FI** to one price series in `data/processed/prices.parquet`, for the planning days 2022-01-01 to 2026-10-31.

## Rows at each stage

| stage | rows | hours of prices |
|---|---|---|
| raw files (12: prices_FI_2015.csv .. prices_FI_2026.csv) | 132240 | 103728 |
| days 2022-01-01 to 2026-10-31 (helsinki days) | 70872 | 42360 |
| known anomalies: keep | 70872 | 42360 |
| incomplete days: drop | 70872 | 42360 |
| resolution: native | 70872 | 42360 |

EXPECT: the hours of prices do not change in the last stage; only the number of rows can (one hour = 1 or 4 rows).

## Days

| what | days |
|---|---|
| days in the sample | 1765 |
| complete | 1765 |
| incomplete | 0 |
| dropped as known anomalies | 0 |
| days in the output | 1765 |

No incomplete days.

EXPECT for the default (FI, 2022-01-01 to 2026-10-31, Helsinki days): 1765 days, all complete. With planning_day=market the last day is incomplete, because the raw data ends at midnight Helsinki time, an hour before the market day ends.

## Rows per day

| rows in a day | number of days |
|---|---|
| 23 | 4 |
| 24 | 1362 |
| 25 | 3 |
| 92 | 1 |
| 93 | 1 |
| 96 | 392 |
| 100 | 2 |

EXPECT, native resolution with Helsinki days: 24 rows on ordinary days before the switch and 96 after; 23 and 25 on daylight saving days (92 and 100 after the switch); 93 on 2025-10-01 (one hour, then 92 quarter-hours). Hourly: 23, 24, 25 only. 15min: 92, 96, 100 only.

## Does the resolution change keep the prices?

| check | before | after |
|---|---|---|
| time-weighted mean price (EUR/MWh) | 71.2476 | 71.2476 |
| largest change in a day's mean price |  | 0.000000 |

EXPECT: the same mean before and after, and 0 change in every day.

## The output file: `data/processed/prices.parquet`

| column | type | meaning |
|---|---|---|
| time_utc | datetime64[us, UTC] | start of the interval (UTC; convert to Helsinki for reading) |
| day | object (Parquet date) | planning day (helsinki) |
| price_eur_mwh | float64 | day-ahead price, EUR/MWh |
| minutes | int16 | length of the interval: 60 or 15 |

70872 rows. Read back from disk and compared with what was written: identical.

First and last rows:

| time_utc | Helsinki time | day | price_eur_mwh | minutes |
|---|---|---|---|---|
| 2021-12-31T22:00:00Z | 2022-01-01 00:00 | 2022-01-01 | 29.76 | 60 |
| 2021-12-31T23:00:00Z | 2022-01-01 01:00 | 2022-01-01 | 46.60 | 60 |
| 2022-01-01T00:00:00Z | 2022-01-01 02:00 | 2022-01-01 | 41.33 | 60 |
| 2026-10-31T21:15:00Z | 2026-10-31 23:15 | 2026-10-31 | 24.26 | 15 |
| 2026-10-31T21:30:00Z | 2026-10-31 23:30 | 2026-10-31 | 22.67 | 15 |
| 2026-10-31T21:45:00Z | 2026-10-31 23:45 | 2026-10-31 | 21.23 | 15 |

## Choices in effect

| choice | value | default | first step | reason |
|---|---|---|---|---|
| bidding_zone | FI | FI | 02_process | The research question is about Finland; neighbours and DE (a higher-price benchmark) allow comparison. |
| sample_start | 2022-01-01 | 2022-01-01 | 02_process | Includes the 2022 price crisis; 2025-10-01 starts the 15-minute era. |
| sample_end | 2026-10-31 | 2026-10-31 | 02_process | Last full month before the project started; fixed so reruns agree. |
| planning_day | helsinki | helsinki | 02_process | A Finnish household thinks in local days; 'market' is the market's own day (00-24 Central European time, 01-01 Helsinki). |
| incomplete_days | drop | drop | 02_process | A day with missing prices cannot be planned as a whole; only DE before 2015-01-05 and edge days are affected. |
| known_anomalies | keep | keep | 02_process | FI 2023-11-24 (-500, a trader's erroneous bid) was a real price that was paid; 'drop' shows how much one day matters. |
| price_resolution | native | native | 02_process | Keep prices as traded: hourly until 2025-09-30, 15 minutes after. |

## What a person should check

- Rows at each stage: nothing disappears that you did not ask for.
- Days: the number of days is right for the sample period, and any dropped day makes sense.
- Rows per day: only the counts listed under EXPECT appear.
- The resolution change keeps every day's mean price.
- The output file has the four columns, and the first and last rows are the first and last hours you expect.
