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
