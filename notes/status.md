# Project status

Read this first in every session. If it disagrees with git, git wins.

Last updated: step 01 (branch `step-01-fetch`, PR open, not yet verified).

## Steps

| step | branch | what | status |
|---|---|---|---|
| 00 | step-00-skeleton | folders, rules, notes, run_all.py, choices, setup check, tests, LaTeX stubs | verified (`verified-00-skeleton`) |
| 01 | step-01-fetch | download FI, SE1, EE day-ahead prices 2015-01-01..2026-10-31 from ENTSO-E to data/raw (CSV); needs `--fetch` | PR open |
| 02 | step-02-process | pick zone and sample period; resolution (hourly/15 min), gaps; Parquet | planned |
| 03 | step-03-describe | describe prices: levels, daily spreads, negative prices; figures | planned |
| 04 | step-04-tariff | household buy and sell prices: margin, transmission, electricity tax, VAT | planned |
| 05 | step-05-battery | one-day battery optimisation (LP, with MILP as a choice), run over the sample | planned |
| 06 | step-06-robustness | sweep the choices; do conclusions change? | planned |
| 07 | step-07-paper | paper and slides with results | planned |

Step 04 (tariff) was added to the original plan: the gap between buying and
selling prices likely matters more for the answer than the optimiser.

## Findings from the teacher's checks

- Step 00: setup check on the teacher's computer 23 OK, 0 warnings, 0
  problems; both API keys found.
- Step 01: the fetch code was tested only offline, with a simulated client
  (retries, rate limit, a missing hour, daylight saving, the 15-minute
  switch). The teacher's `--fetch` run is the first real download.

## Open questions

- Battery setup: pure grid arbitrage, or behind the meter with a household
  load profile? Decide before step 04.
- Tariff components and their sources (retail margin, transmission fee,
  electricity tax, VAT, selling margin). Decide in step 04.
- Battery parameters: energy (kWh), power (kW), round-trip efficiency, price,
  lifetime, discount rate. Decide before step 05.
- Modelling library for step 05: Pyomo or PuLP (both with the HiGHS solver).
- The planning day for the battery (step 05): the market day (00:00-24:00
  Central European time = 01:00-01:00 Helsinki) or the Helsinki calendar
  day? To be registered as a choice in step 05.
- Gaps in the raw data (if the teacher's run finds any): how to fill them is
  a choice for step 02.
