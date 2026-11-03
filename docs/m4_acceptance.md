# Step 4 (M4) acceptance checklist — 20-point scorecard

Step 4 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m4_check.py` reruns every automated item and writes `data\clean\step4\m4_check_report.txt`.
Builds on Step 3 (commit c1b856f). Cutoff 2026-11-02. Estimates snapshot: `20261103T180459Z` (fetched 2026-11-03 18:04 UTC, 1 day after the cutoff).

Pre-check in Claude's workspace (2026-11-03, PostgreSQL 16) with a **synthetic** estimates snapshot, to test the code only:
SC1–SC5 pass; 306 cells of the Step 4 views equal the Python recomputation; reruns byte-identical; Step 4 offline tests
18 passed, database tests 3 passed. None of those estimate values are real; only your fetch is.

Kyan's run (2026-11-03 18:10 UTC, PostgreSQL 18.6): offline 103 passed; db 7 passed; reconciliation 11 passed; E1, E2, SC1–SC5 pass;
estimates and exports byte-identical on rerun; V2 306 cells equal. NVIDIA 18/20 (P/E 25.25 and FCF conversion 80.5% near misses).

## T — technical (it runs) — on Kyan's machine
- [x] `fetch_step4.py`: EPS estimates saved for all six companies (revenue estimates optional)
- [x] Offline suite passes, including `tests\test_step4.py`
- [x] `run_step4.py all` exits 0: E1, E2 and SC1–SC5 pass
- [x] Estimates rerun byte-identical; second database rebuild gives byte-identical exports
- [x] `& $vpy -m pytest -m db` passes (Step 3 and Step 4 database tests)

## V — data verified
- [x] V2: every cell of `v_beta`, `v_wacc`, `v_peg`, `v_scorecard_detail`, `v_scorecard` equals the independent Python recomputation
- [x] Consensus cross-check (S4-D2): NVIDIA `0y` and `+1y` EPS within 5% of a second public source, recorded with URL and date
- [x] Estimates fetched within 7 days of the cutoff (E2, 1 day); fiscal years behind `0y` / `+1y` verified for NVDA, AVGO and QCOM (I-49); provider differences for AVGO and QCOM logged, test results unaffected (I-50)
- [x] Every test's inputs read against the Step 3 exports for NVIDIA (the report prints them)
- [x] Betas and the provisional WACC judged plausible, with I-48 carried to Step 6 (analyst review: betas 1.5–2.5 vs SPY are consistent with the group's 5-year volatility; WACC barely affects test 9 because every company's ROIC is either far above or below it, except AVGO, whose near miss (ROIC 15.7% vs WACC 12.0%) is sensitive to the beta)
- [x] Scorecard result read and judged: two sentences written for the Excel tab (guide Step 4.5)

## S — sign-off (Kyan)
- [x] S4-D2 to S4-D8 accepted in `decision_log.md` (D13 and D14 now confirmed; recommendations taken as analyst, confirmed by the commit)
- [x] Excel tab `Scorecard` built from `data\clean\step4\exports\v_scorecard.csv` (guide Step 4.4)
- [ ] `m4_check_report.txt` saved as `docs\evidence\m4_check_report_<date>.txt`
- [ ] Step 4 commit made
- [ ] Approval to start Step 5

Signed off by: ____________  Date: ____________
