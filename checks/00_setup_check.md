# Check report 00_setup_check: Setup check

Written by `code/00_setup_check.py`. Rerun with `python run_all.py --steps 00`.

Is this computer ready? Each row compares what we EXPECT with what we SEE on the machine that ran this script.

## Summary

| status | count |
|---|---|
| OK | 22 |
| WARNING | 1 |
| PROBLEM | 0 |

## Python

| item | expected | seen | status |
|---|---|---|---|
| Python version | 3.13 | 3.13 | OK |

## Packages (pinned in requirements.txt)

| item | expected | seen | status |
|---|---|---|---|
| entsoe-py | 1.0.0 | 1.0.0 | OK |
| matplotlib | 3.11.2 | 3.11.2 | OK |
| numpy | 2.5.5 | 2.5.5 | OK |
| pandas | 3.1.1 | 3.1.1 | OK |
| pyarrow | 26.0.1 | 26.0.1 | OK |
| pytest | 9.2.0 | 9.2.0 | OK |
| python-dotenv | 1.2.4 | 1.2.4 | OK |
| requests | 2.34.2 | 2.34.2 | OK |

## Project folders

| item | expected | seen | status |
|---|---|---|---|
| code/ | exists | exists | OK |
| tests/ | exists | exists | OK |
| data/raw/ | exists | exists | OK |
| data/processed/ | exists | exists | OK |
| checks/ | exists | exists | OK |
| results/ | exists | exists | OK |
| figures/ | exists | exists | OK |
| paper/ | exists | exists | OK |
| slides/ | exists | exists | OK |
| notes/ | exists | exists | OK |

## Secrets

| item | expected | seen | status |
|---|---|---|---|
| ENTSOE_API_KEY in .env | found | NOT FOUND | WARNING |
| FINGRID_API_KEY in .env | optional, not used yet | not set | OK |
| .env listed in .gitignore | yes | yes | OK |
| .env.example holds a placeholder | yes | yes | OK |

## Choices in effect

| choice | value | default | first step | reason |
|---|---|---|---|---|
| bidding_zone | FI | FI | 01_fetch | The research question is about Finland; neighbours allow comparison. |
| sample_start | 2022-01-01 | 2022-01-01 | 01_fetch | Includes the 2022 price crisis; 2025-10-01 starts the 15-minute era. |
| sample_end | 2026-10-31 | 2026-10-31 | 01_fetch | Last full month before the project started; fixed so reruns agree. |
| price_resolution | native | native | 02_process | Keep prices as traded: hourly until 2025-09-30, 15 minutes after. |

## What a person should check

- Every row says OK. A PROBLEM must be fixed before the next step.
- ENTSOE_API_KEY says WARNING when .env is missing. Steps that download data (run with --fetch) need it; other steps do not.
- Python and package versions match on every computer: if your report differs from the committed one, your environment differs.
- The key value never appears here, only whether it was found.
