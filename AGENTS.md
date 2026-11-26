# Rules for this project

This file holds every rule for working on this repository. It is written for
the AI agent that writes the code, and for students who want to see how the
work is organised. `CLAUDE.md` only points here.

**Start of every session:** read `notes/status.md` first. If it disagrees with
git (branches, tags, files), git wins; fix status.md in the next PR.

## The project

A live teaching demo for a course on quantitative economics with Python.
Research question: **what is a home battery worth under Finnish day-ahead
electricity prices?** Prices come from the ENTSO-E Transparency Platform.
The point is as much HOW the work is done as WHAT it finds: the agent writes
all code; the human (the teacher) steers, runs and verifies every step.
Everything must stay readable for students new to git, tests and the terminal.

## Roles and limits

- The teacher works through a chat with the agent and has GitHub access.
- The agent's workspace cannot reach the ENTSO-E API and cannot push tags.
  Steps that download data run on the teacher's computer. The teacher tags.
- The agent may push branches and open pull requests. It never commits to
  `main`. (One exception, logged in notes/decisions.md: the first commit that
  created `main` in the empty repository.)

## Branches, pull requests, tags

- One step = one branch `step-NN-name` = one pull request.
  Small fixes between steps: branch `fix-short-name`.
  When the teacher asks to do two steps together: one branch
  `step-NN-MM-name` and one tag `verified-NN-MM-name` (steps 02-03 did this).
- Merge with "Create a merge commit" (not squash), so `git branch -d` works.
- After merging, the teacher deletes the branch and tags the verified state
  `verified-NN-name`. A tag never has the same name as a branch.
  Tags are the lecture safety net.

## Exact commands, always

- The teacher uses Windows with two terminals in the project folder:
  **PY** (Anaconda Prompt, `cmd` syntax) and **GIT**.
- Every chat turn that hands work to the teacher ends with the exact
  commands to run, in order, ready to copy and paste, in blocks labelled
  PY or GIT.
- Every PR description contains the same commands, so the PR on its own is
  enough to verify and merge it.
- The sequence stays the same from step to step. It is written down in
  `notes/dev-loop.md`; PRs copy it with `NN-name` filled in and say what is
  different, if anything (`--fetch`, `--latex`, expected changed files).

## Human verification: check reports

- Every analysis step is a script `code/NN_name.py` that ends by writing a
  human-readable check report `checks/NN_name.md` (use `common.Report`).
- A report contains: excerpts of input and output; counts and ranges; facts a
  person can recognise, with what we EXPECT next to what we SEE; the choices
  in effect (`Report.choices_in_effect`); and a small figure where a picture
  is faster than a table.
- Means of prices are time-weighted (`fetch_tools.weighted_mean`): an hour
  counts as much as four quarter-hours. Never a plain mean of rows.
- Reports are deterministic: no run times, no dates of running, no absolute
  paths, no machine names. A changed report in a PR means changed results.
- Figures: SVG with fixed metadata (no creation date, fixed hash salt), so an
  unchanged figure is byte-identical. Text files are written with `\n` line
  endings (`newline="\n"`).
- A report may record things that differ by machine only when the teacher
  must see them (for example whether the API key was found). The committed
  report is the one from the teacher's run.

## Tests

- Tests check invariants a machine can check; reports cover what a person
  must judge.
- Tests are illustrative, not exhaustive: a few fast offline pytest tests per
  step, with tiny hand-written data. Tests never call the API.
- Where a library does work for us, test through the real library with a
  fake network (e.g. entsoe-py fed with fake XML) rather than only with a
  hand-made imitation of it: an imitation misses what we did not think of.
  (Lesson from step 01, see notes/status.md.)

## Garden of forking paths: choices

- Never hard-code a judgement call (missing hours, resolution, sample period,
  outliers, tariffs, battery parameters, ...). Register it in
  `code/choices.py` with a default, the alternatives, a one-line reason and
  the first step that reads it. Log it in `notes/decisions.md`.
  When in doubt, make it a choice.
- Non-default runs write to `variants/<name>/` (same subfolders as the
  project: checks, results, figures, data/processed), so default outputs are
  never overwritten. The name lists the changed choices, sorted:
  `name-value__name-value`.
- Later we sweep the choices and show whether conclusions change.

## Master script: run_all.py

- From the first PR, `run_all.py` reruns all analysis so far. Flags:
  `--fetch` (include steps that need the API key), `--steps` (e.g. `00,02`
  or `01-03`), `--set name=value` (repeatable), `--sweep name=a,b`
  (repeatable; several sweeps run every combination), `--latex` (compile
  paper and slides), `--list`.
- Every PR that adds or changes a step updates `STEPS` in run_all.py.
- A step that reads no choices (`uses_choices=False`, e.g. the download) runs
  once per `run_all.py` call, never once per variant.

## Code layout of a step

- `code/NN_name.py` orchestrates the step and writes its report. A file
  name starting with digits cannot be imported normally, so functions that
  tests need live in an importable module next to it (e.g.
  `code/fetch_tools.py` for step 01).
- Every API call goes through `fetch_tools.call_with_retry` (time-out,
  spacing between calls, retries with growing waits, a long wait on HTTP
  429). Retries are printed in the terminal, never written to reports.

## Repository layout

| folder | holds |
|---|---|
| `code/` | step scripts `NN_name.py`, `choices.py`, `common.py` |
| `tests/` | pytest tests |
| `data/raw/` | API downloads as CSV, one file per zone and year, committed (open and diff them) |
| `data/processed/` | cleaned data as Parquet (types and time zones survive) |
| `checks/` | check reports `NN_name.md` |
| `results/` | tables and numbers for the paper |
| `figures/` | figures for the paper and slides |
| `variants/` | outputs of non-default runs |
| `paper/` | LaTeX paper, compiled PDF committed |
| `slides/` | Beamer slides, compiled PDF committed |
| `notes/` | status, decisions, dev loop |

- Commit data files under 50 MB. Every Parquet file is described (columns,
  types, rows, time zone) in its step's check report.
- Compiled PDFs are committed as a backup. LaTeX sources set fixed PDF
  metadata so an unchanged document compiles to the same file.
- Data source attribution (ENTSO-E Transparency Platform) appears in the
  README and the paper.

## Secrets

- The ENTSO-E key lives only in `.env` (gitignored), as the line
  `ENTSOE_API_KEY=<token>`, exactly this variable name. A second line
  `FINGRID_API_KEY=<token>` is optional and not used yet.
- `.env.example` is committed with a placeholder value; it is shown to students.
- The key never appears in terminal output, check reports, logs, error
  messages or commits. The ENTSO-E client puts the key in request URLs, so
  error text is masked before printing: use `common.say()` for console output
  and `common.run(main)` around every step's `main()`. `Report.render()`
  masks too.
- A setup check may say "key found (value not shown)", nothing more.

## Environment

- Terminal only: no Spyder, no notebooks.
- A conda environment `elec` that holds only Python 3.13. All packages come
  from `requirements.txt` with pinned versions, installed with pip.
  A python.org + `.venv` route is documented in `notes/dev-loop.md`.
- A step that needs a new package adds it, pinned, to requirements.txt.
- Console output is plain ASCII.
- The project folder is named `code/`, which is also the name of a Python
  standard-library module, so never `import code`; scripts import
  `common` and `choices` directly (pytest.ini puts `code/` on the path).

## Notes: nothing lives only in the chat

- `notes/status.md`: where the project stands (steps, findings from the
  teacher's checks, open questions). Every PR updates it.
- `notes/decisions.md`: every decision, dated, with the reason. Anything
  decided in chat goes into a file, never only into the chat.
- `notes/dev-loop.md`: the standard command sequence.
