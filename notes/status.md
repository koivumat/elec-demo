# Project status

Read this first in every session. If it disagrees with git, git wins.

Last updated: steps 02 and 03 (one branch `step-02-03-process-describe`, PR
open, not yet verified).

## Steps

| step | branch | what | status |
|---|---|---|---|
| 00 | step-00-skeleton | folders, rules, notes, run_all.py, choices, setup check, tests, LaTeX stubs | verified (`verified-00-skeleton`) |
| 01 | step-01-fetch | download FI, SE1, SE3, EE, DE day-ahead prices 2015-01-01..2026-10-31 from ENTSO-E to data/raw (CSV); needs `--fetch` | verified (`verified-01-fetch`) |
| 02 | step-02-03-process-describe | pick zone, sample, planning day; incomplete days; anomalies; resolution; Parquet | PR open |
| 03 | step-02-03-process-describe | yearly prices, daily spreads, upper bound of battery earnings, hour profile; figures | PR open |
| 04 | step-04-tariff | household buy and sell prices: margin, transmission, electricity tax, VAT | planned |
| 05 | step-05-battery | one-day battery optimisation (LP, with MILP as a choice), run over the sample | planned |
| 06 | step-06-robustness | sweep the choices; do conclusions change? | planned |
| 07 | step-07-paper | paper and slides with results | planned |

Step 04 (tariff) was added to the original plan: the gap between buying and
selling prices likely matters more for the answer than the optimiser.
Steps 02 and 03 share one branch and PR (teacher's request: the figures of
03 help to verify 02).

## Findings from the teacher's checks

- Step 00: setup check on the teacher's computer 23 OK, 0 warnings, 0
  problems; both API keys found.
- Step 01, teacher's first run: `DE 2018: FAILED: Both dates must have the
  same UTC offset` (a request mixed Helsinki and Berlin time). Fixed; tests
  now also run the real entsoe-py client on fake XML.
- Step 01, verified data: 60 files, 59 complete. DE 2015 lacks 97 hours:
  ENTSO-E's DE-AT-LU data starts 2015-01-05 00:00 Berlin time. All facts in
  the report matched (FI highest yearly mean 2022; FI 2023-11-24 nine hours
  at -500, only FI affected; DE highest month 2022-08; SE3 above SE1 since
  2020).
- Step 01 report bug, found while building step 03 and fixed in the step
  02-03 PR: the per-file "mean" was a plain mean of rows, so in 2025 a
  quarter-hour counted as much as an hour (FI 2025: 42.09 instead of the
  time-weighted 40.47). Only 2025 means changed (and SE1 2015 by 0.01 from
  rounding); the data did not.
- Steps 02-03, agent's run on the committed data (to be confirmed by the
  teacher): FI 2022-01-01..2026-10-31 has 1765 days, all complete. Upper
  bound for a 2-hour battery (one cycle a day, no losses, spot prices):
  69 EUR/kWh in 2022, 23-29 EUR/kWh a year in 2023-2025.

## Open questions

- Battery setup: pure grid arbitrage, or behind the meter with a household
  load profile? Decide before step 04.
- Tariff components and their sources (retail margin, transmission fee,
  electricity tax, VAT, selling margin). Decide in step 04.
- Battery parameters: energy (kWh), power (kW), round-trip efficiency, price,
  lifetime, discount rate. Decide before step 05.
- Modelling library for step 05: Pyomo or PuLP (both with the HiGHS solver).
- Default sample: 2022 dominates averages (upper bound 69 vs 23-29 EUR/kWh).
  Should the headline number in the paper use 2023 onwards, with 2022 as a
  robustness check? Decide before step 05.
