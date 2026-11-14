# Step 9 (M9) acceptance checklist — investment memo

Step 9 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m9_check.py` reruns every automated item and writes `data\clean\step9\m9_check_report.txt`.
Builds on Steps 4–7 (Step 8, the Power BI dashboard, is skipped for now). Memo: `docs\memo\NVDA_investment_memo.md` and `.pdf`.

Pre-check in Claude's workspace (2026-11-09): M1–M7 pass (8 comparative claims true; 77 numbers each with a source;
target arithmetic; rating follows the bands; rating and target in the first line; 761 words before the exhibits; the memo
in docs is the current render); memo, exhibit and numbers byte-identical on two renders; Step 9 offline tests and
reconciliation pass; PDF is two A4 pages. The call: **Buy, 12-month target $260 (+28.7% vs $202.06 on 2 Nov 2026).**

Kyan's run (2026-11-14 16:06 UTC): run_step9 M1–M6 PASS; Step 9 tests 10 passed; offline 137 passed; m9_check M1–M7
PASS, memo reproducible; reconciliation 20 passed, 3 skipped (LibreOffice comparisons from Steps 5–7, done in Excel then);
Git ready (17 files, no secrets); results identical to the pre-check. Decisions S9-D1 to S9-D7 confirmed 2026-11-14
(analyst review delegated by Kyan).

## T — technical (it runs) — on Kyan's machine
- [x] Offline suite passes, including `tests\test_step9.py`
- [x] `run_step9.py --check` exits 0 (M1–M7 pass; the committed memo is current)
- [x] Memo, exhibit and numbers byte-identical on two renders
- [x] `build_simple_dcf.py` rebuilds `excel\NVDA_Simple_DCF.xlsx`; its DCF tab shows 168.42

## V — content verified
- [x] Target and headline figures tie to Steps 6–7 (reconciliation)
- [x] Memo read in full (PDF): rating and target in the first line; each thesis bullet has a test; the variant view, valuation, scorecard caveat, risks with a metric each, and catalysts with dates are present
- [x] Every comparative claim checked by M1; no adjective without a number behind it
- [x] Catalyst dates verified (Q3 FY2027 results 17 Nov 2026, NVIDIA newsroom)

## S — sign-off (Kyan)
- [x] S9-D1 to S9-D7 accepted in `decision_log.md` (or changes requested)
- [x] `m9_check_report.txt` saved as `docs\evidence\m9_check_report_<date>.txt`
- [x] Step 9 commit made
- [x] Approval to start Step 10

Signed off by: _____Kyan Soni_______  Date: _____2026-11-14_______
