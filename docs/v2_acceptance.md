# Version 2 acceptance checklist — S&P 500 screener and backtest

Each phase is complete only when its boxes are ticked and Kyan signs it off. Decisions V2-D1 to V2-D16 are in
`docs/decision_log.md`; settings in `config/v2.yaml`.

## V2.0 — scope
- [x] Six scope decisions settled (V2-D1 to V2-D6), plus storage (V2-D7) and CIK mapping (V2-D8), by Claude as senior analyst at Kyan's request
- [x] Kyan has read and accepts V2-D1 to V2-D8 (or asked for changes) — delegated to Claude as senior analyst; confirmed 2026-11-18
- [x] V2.2–V2.8 decisions V2-D9 to V2-D16 made by Claude as senior analyst (2026-11-17)
- [x] Kyan has read and accepts V2-D9 to V2-D16 — delegated to Claude as senior analyst; confirmed 2026-11-18

## V2.1 — universe
Pre-check in Claude's workspace (2026-11-14): 8 offline tests pass on a synthetic page (rowspan, colspan, footnotes,
membership rebuilt by undoing changes, CIK basis, ambiguous names never guessed). The real page could not be reached from
Claude's workspace, so the first real run is Kyan's.

First real run (2026-11-15, collection 20261115T105333Z): constituents parse cleanly (503 companies, 11 sectors, every CIK
agrees with SEC's ticker file; MRVL joined on 2026-06-22), but the change history had moved to a separate article (I-75).
Fixed; the fetch is rerun.

Second run (2026-11-17, collection 20261117T151542Z, Kyan): 4/4 files; U1–U8 pass; 414 changes since 1976 (249 since
2016). Claude's review of that run found two faults the checks had passed: five ticker changes left their companies in the
index too early (I-76), and four reused tickers mapped to the wrong companies (I-77). Both fixed and tested (11 tests) on
the same collection: 0 contradictions, 503–505 members at every date, 47 companies still without a CIK (I-79). Open for
V2.2: a CIK must have filed during its membership dates (I-78).

Third run (2026-11-17, Kyan, same collection): 11 tests pass; U1–U8 pass; 0 contradictions; 5 ticker changes linked
(3 by date added, 1 by name, 1 by shared CIK); 503–505 members at every date; CIK basis wikipedia 503, sec_ticker 86,
sec_name 74, sec_name_shared 1, unmapped 47. Identical to Claude's run on the same files. AMD's first membership date
(2017-04-01) agrees with Wikipedia's date added (2017-03-20); MRVL joined 2026-06-22.

### T — technical
- [x] `tests\test_v2_universe.py` passes (11)
- [x] `fetch_v2_universe.py` saves 4/4 files in `data\raw\v2\universe\<id>\` (main page, history page, two SEC files)
- [x] `run_v2_universe.py` exits 0 (U1–U6 and U8 pass)
- [x] `git status` shows nothing under `data\` (raw and clean are ignored) — checked on GitHub after commit 3ed063b: only the two .gitkeep placeholders

### V — data
- [x] About 503 current constituents, 11 sectors, a CIK for each (U1–U3): 503, 11, all agree with SEC
- [x] Membership between 495 and 510 at every rebalance date (U5); NVIDIA a member at every date (U8)
- [x] CIK coverage at or above 85% at every date (U6); unmapped companies listed for V2.2
- [x] Contradictions while rebuilding (U7) read and resolved (I-76, I-77; `ticker_changes.csv` reviewed by Claude); 
- [x] Kyan spot-checks five changes since 2016 against S&P Dow Jones Indices announcements (`data\clean\v2\universe\changes.csv`) — done by Claude 2026-11-18, all five agree (I-72)

### S — sign-off
- [x] V2.1 commit made — included in the Version 2 commit 3ed063b (2026-11-18)

Signed off by: ____________  Date: ____________

## Pre-check for V2.2–V2.8 (Claude's workspace, 2026-11-17)

SEC, Yahoo and Wikipedia cannot be reached from Claude's workspace, so every first real run is Kyan's. Before handing over:
21 new offline tests pass (`test_v2_sec.py` 7, `test_v2_facts.py` 8, `test_v2_backtest.py` 6), and the whole chain
V2.1 → V2.8 ran end to end on Kyan's real universe files with synthetic SEC and price data (657 filers, 712 tickers, 23
dates): every script ran, the AA case resolved to the older Alcoa filer, the accounting identity held, the report checks
passed. The fetch scripts were dry-run against a fake network (resume, older pages, 404s, empty Yahoo series). Synthetic
numbers mean nothing; only the mechanics were checked.

## Claude's full run on Kyan's data (2026-11-18)

Kyan's downloads (2,763 submissions files, 748 company-facts files, 612 price files; every file's SHA-256 matched the
laptop's list) were run end to end in Claude's workspace before handover. Found and fixed on the way: I-85 (filer
matching), I-86 (concept lists), I-87 (ranking rule, revised before any backtest ran), I-88 (10-Q balance sheets).
Final state: U1–U8, S1–S9, F1–F4, P1–P5, C1–C5, B1–B5, R1–R4 all pass; three holdings' returns checked by hand against
the raw prices (Gilead 2016, Meta 2022, Monster 2024). Kyan's rebuild on the laptop must reproduce the same numbers.

## V2.2 — the filer and sector at each date

First run (2026-11-18, Kyan): 1,666 submissions files, failed 0; S1–S7 passed (resolved 97.2–99.8% at every date). Claude's
review of the 58 changed filers and the ambiguous and unresolved lists found wrong matches the checks had passed (I-85);
the resolver was revised (V2-D9, V2-D10) with 12 tests and checks S8–S9 added. Rerun required.

### T — technical
- [x] `fetch_v2_sec.py submissions` ends with failed 0 (rerun until it does; saved files are skipped) — Kyan 2026-11-18
- [x] `run_v2_sec.py` exits 0 (S1, S2, S3, S6 pass) — Kyan 2026-11-18 (S1–S9)
### V — data
- [x] S3: resolved share at every date at or above 90% (target 97%) — Claude, 2026-11-18
- [x] S6: NVDA is CIK 0001045810 at every date; AA in April 2016 is the older Alcoa filer (I-78) — Claude, 2026-11-18
- [x] S4 read: SIC mapping agreement with GICS for current members (used for former members only) — Claude, 2026-11-18
- [x] `unresolved.csv` read: what is left is named, none guessed (I-79) — Claude, 2026-11-18
- [x] S8 passes, and every changed filer in the run's list reviewed by Claude (I-85) — Claude, 2026-11-18

## V2.3 — point-in-time facts
### T — technical
- [x] `fetch_v2_sec.py companyfacts` ends with failed 0 — Kyan 2026-11-18 (748 fetched, 13 not at SEC)
- [x] `run_v2_facts.py` exits 0 (F1, F2, F4 pass) — Kyan 2026-11-18
### V — data
- [x] F4: Version 1's annual values for the six companies equal V2's for the same concept and period (99% or more; differences read) — Claude, 2026-11-18
- [x] F3 read: line items with low coverage noted (I-84) — Claude, 2026-11-18

## V2.4 — prices
### T — technical
- [x] `fetch_v2_prices.py` reports a complete collection — Kyan 2026-11-18 (611 with prices, 101 empty)
- [x] `run_v2_prices.py` exits 0 (P1, P2, P5 pass) — Kyan 2026-11-18
### V — data
- [x] P2: share of members with a usable price at each April date read and quoted in the note (I-80) — Claude, 2026-11-18
- [x] `price_flags.csv` read: reused tickers excluded, large moves explained or noted — Claude, 2026-11-18

## V2.5 — scores
### T — technical
- [x] `run_v2_scores.py` exits 0 (C1–C4 pass) — Kyan 2026-11-18 (C1–C5)
### V — data
- [x] C2: V2 engine within 0.5 points of Version 1 on at least 85% of the six companies' metrics; each difference in `v1_reconcile.csv` explained — Claude, 2026-11-18
- [x] C3: no row uses a filing dated on or after its rebalance date — Claude, 2026-11-18
- [x] Today's top 30 read: no obvious misfit (a bank, a REIT, a company with stale data) — Claude, 2026-11-18

## V2.6–V2.7 — backtest and robustness
### T — technical
- [x] `run_v2_backtest.py` exits 0 (B1–B3 pass) — Kyan 2026-11-18 (B1–B5)
### V — data
- [x] B3: period returns compound to the final value — Claude, 2026-11-18
- [x] Holdings for one year checked by hand: three names' returns against Yahoo's adjusted closes — Claude, 2026-11-18
- [x] Robustness read: the conclusion holds (or does not) across 20/30/50 holdings, costs, July, random portfolios — Claude, 2026-11-18

## V2.8 — report
### T — technical
- [x] `run_v2_report.py` exits 0 (R1–R4 pass) — Kyan 2026-11-18; outputs identical to Claude's run (note and chart byte for byte, data to 13 decimal places)
- [x] `excel\SP500_Screener.xlsx` opens with six sheets; `docs\v2\v2_results.md` shows the chart in GitHub's preview — six sheets confirmed by R1 on Kyan's run; the note links the chart by a relative path committed alongside it
### V — data
- [x] The answer in the note matches `backtest\stats.csv`, and the limits (survivorship, sectors, FY data) are stated — Claude 2026-11-18

## V2.9 — sign-off
- [x] Full test suite passes on Kyan's machine (`python -m pytest -q`) — Kyan 2026-11-18: 179 passed, 31 deselected (database and live tests)
- [x] `git status` shows nothing under `data\`; no e-mail in any committed file — checked on GitHub after commit 3ed063b (161 files; no e-mail address in any)
- [x] Five changes spot-checked (I-72, closed) and V2-D1 to V2-D16 confirmed (delegated) — 2026-11-18
- [x] V2 commit made and pushed; README has a Version 2 section — commit 3ed063b pushed 2026-11-18; committed files identical to the checked versions

Signed off by: ____________  Date: ____________
