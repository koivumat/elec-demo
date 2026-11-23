# Project status

Read this first in every session. If it disagrees with git, git wins.

Last updated: step 00 (branch `step-00-skeleton`, PR open, not yet verified).

## Steps

| step | branch | what | status |
|---|---|---|---|
| 00 | step-00-skeleton | folders, rules, notes, run_all.py, choices, setup check, tests, LaTeX stubs | PR open |
| 01 | step-01-fetch | download FI day-ahead prices from ENTSO-E to data/raw (CSV); needs `--fetch` | planned |
| 02 | step-02-process | clean: resolution (hourly/15 min), daylight saving days, gaps; Parquet | planned |
| 03 | step-03-describe | describe prices: levels, daily spreads, negative prices; figures | planned |
| 04 | step-04-tariff | household buy and sell prices: margin, transmission, electricity tax, VAT | planned |
| 05 | step-05-battery | one-day battery optimisation (LP, with MILP as a choice), run over the sample | planned |
| 06 | step-06-robustness | sweep the choices; do conclusions change? | planned |
| 07 | step-07-paper | paper and slides with results | planned |

Step 04 (tariff) was added to the original plan: the gap between buying and
selling prices likely matters more for the answer than the optimiser.

## Findings from the teacher's checks

None yet.

## Open questions

- Battery setup: pure grid arbitrage, or behind the meter with a household
  load profile? Decide before step 04.
- Tariff components and their sources (retail margin, transmission fee,
  electricity tax, VAT, selling margin). Decide in step 04.
- Battery parameters: energy (kWh), power (kW), round-trip efficiency, price,
  lifetime, discount rate. Decide before step 05.
- Modelling library for step 05: Pyomo or PuLP (both with the HiGHS solver).
