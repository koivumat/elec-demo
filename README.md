# elec-demo

What is a home battery worth under Finnish day-ahead electricity prices?

A teaching demo for a course on quantitative economics with Python. An AI
agent writes the code; a person steers, runs and checks every step. How the
work is done matters as much as what it finds.

## Where to start

- `notes/dev-loop.md`: setting up your computer, and the commands for each step
- `notes/status.md`: where the project stands
- `AGENTS.md`: the rules we work by
- `checks/`: one human-readable report per step, comparing what we expect
  with what we see

## Run it

```
conda activate elec
python run_all.py --list
python run_all.py
```

## Folders

`code/` scripts, `tests/` tests, `data/raw/` downloads (CSV),
`data/processed/` cleaned data (Parquet), `checks/` check reports,
`results/` tables and numbers, `figures/` figures, `variants/` runs with
non-default choices, `paper/` and `slides/` LaTeX, `notes/` project notes.

## Data

Day-ahead prices from the ENTSO-E Transparency Platform
(https://transparency.entsoe.eu). Downloading needs a free API token in a
file `.env`; see `notes/dev-loop.md`.
