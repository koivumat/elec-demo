# Decisions

Every decision, dated, with who decided and why. Analysis choices also live in
`code/choices.py`; this log says when and why they were set.

## 2026-11-23 (before and in step 00)

- **Workflow rules** as in AGENTS.md, from the teacher's project brief.
  (teacher)
- **Initial commit on main.** The repository was empty, so a pull request had
  nothing to merge into. The agent made one commit on `main` with a one-line
  README; everything else goes through PRs. This is the only direct commit to
  main. (agent, reported to teacher)
- **Fingrid key kept as an option.** `.env` may hold `FINGRID_API_KEY` as a
  second line in case we extend to Fingrid data later. Not used yet.
  (teacher)
- **LaTeX.** The teacher compiles with pdflatex when needed; the agent may
  compile and commit PDFs too. (teacher)
- **Sample period default: 2022-01-01 to 2026-10-31.** Includes the 2022 price
  crisis; the end is fixed so reruns give the same data. Registered as
  choices `sample_start`, `sample_end`. (agent proposed, teacher agreed)
- **Price resolution is a choice.** Day-ahead prices are hourly until
  2025-09-30 and 15-minute from delivery day 2025-10-01. Default `native`
  keeps both; alternatives `hourly` and `15min`. Registered as
  `price_resolution`. (agent)
- **Bidding zone is a choice**, default FI; SE1 and EE allow comparisons.
  Registered as `bidding_zone`. (agent)
- **Tariff step added** (step 04) because buying and selling prices differ a
  lot for a Finnish household. (agent proposed, teacher agreed)
- **LP or MILP** will be a choice in step 05: a pure LP can charge and
  discharge at once when prices are negative; a binary variable prevents it.
  (agent proposed)
- **One standard loop for every step**, with a block for committing verified
  outputs from the teacher's run (downloaded data, reports that depend on the
  teacher's machine). Merge with "Create a merge commit". (agent)
- **Line endings.** `.gitattributes` stores text with LF, and scripts write
  `\n`, so reports from Windows and Linux are identical. (agent)
- **Pinned packages** (requirements.txt) chosen as the current versions that
  work with Python 3.13 on 2026-11-23. The modelling library is added in
  step 05. (agent)

## 2026-11-25 (step 01)

- **Fetch everything, choose later.** Step 01 downloads all three zones (FI,
  SE1, EE) for every year from 2015-01-01 to 2026-10-31 and reads no
  choices. The choices `bidding_zone`, `sample_start`, `sample_end` now start
  in step 02. Raw data is the same for every variant; forks start at
  processing. (agent proposed, teacher agreed)
- **Start in 2015** (about 22 MB of CSV in total, no file above 2 MB).
  (teacher)
- **No raw XML kept.** The CSV is what the standard client (entsoe-py)
  returns; the check report lists what the client changes. (teacher)
- **One CSV per zone and calendar year (Helsinki time)** with columns
  `time_utc, time_helsinki, price_eur_mwh, minutes`. UTC is the key;
  Helsinki time is for reading. (agent)
- **Retries and rate limits** (teacher asked for robust handling): our own
  retry layer, the client's own retries switched off; 120 s time-out per
  request; 2 s between requests; network errors, time-outs and HTTP 5xx
  retried after 10, 30, 60, 120, 300 s; HTTP 429 waits 660 s (ENTSO-E bans
  for about 10 minutes after 400 requests per minute per token); other errors
  (401 wrong key, 400) fail at once. A failed file does not stop the others;
  the run ends with exit code 1 and the command can simply be run again.
  Files are written to a temporary name and renamed, so no half-written file
  is ever left. (agent)
- **Existing files are not downloaded again** (teacher). A run downloads
  only the files missing from `data/raw/`; to refresh a file (for example
  after ENTSO-E corrects data), delete it and run again. The key is needed
  only when something is missing. The report does not say which files were
  downloaded in this run (the terminal does), so it changes only when the
  data changes. This replaces the earlier plan to download everything on
  every run. (teacher asked, agent implemented)
- **Steps that read no choices run once per run_all call**, not once per
  variant in a sweep (`uses_choices=False` in run_all.py). (agent)
