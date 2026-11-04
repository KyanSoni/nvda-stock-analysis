# Step 7 (M7) acceptance checklist — comparable companies

Step 7 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m7_check.py` reruns every automated item and writes `data\clean\step7\m7_check_report.txt`.
Builds on Steps 2–6. Inputs: Step 3 `v_valuation_cutoff` and `v_ratios_ltm`, Step 4 consensus snapshot, Step 6 DCF,
Step 2 prices, `config\comps.yaml`.

Pre-check in Claude's workspace (2026-11-04; LibreOffice available): C1–C6 pass; X4 the workbook's Comps tab,
recalculated by LibreOffice, equals Python for 147 values (worst relative difference 5e-15); Step 5 X1 and Step 6 X3
still pass with the new tabs; CSV outputs byte-identical on rerun; inputs tie to Steps 3, 4 and 6; NVIDIA NTM EPS
14.40 agrees with the Nasdaq consensus within 5%; Step 7 offline tests 9 passed, reconciliation 4 passed.
NVIDIA: NTM P/E 14.0× (peer median 26.1×), NTM EV/EBITDA 11.5× (17.4×); comps value 338.80; DCF 157.47;
blended 248.13 vs 202.06 (+22.8%).

Kyan's run (2026-11-04 14:11 UTC): Step 7 tests 9 passed; offline 127 passed; run_step7 C1–C6 PASS; 6/6 CSV outputs
reproducible; reconciliation 18 passed, 3 skipped (LibreOffice comparisons, replaced by the Excel checks); m7_check all
PASS except MANUAL items; results identical to the pre-check. Decisions S7-D1 to S7-D9 confirmed 2026-11-04 (analyst review
delegated by Kyan).

## T — technical (it runs) — on Kyan's machine
- [x] Offline suite passes, including `tests\test_step7.py`
- [x] `run_step7.py` exits 0 (C1–C6 pass)
- [x] CSV outputs byte-identical on rerun
- [x] `excel\NVDA_Forecast.xlsx` opens in Excel without repair messages and has Comps and CompsData tabs with two charts

## V — data verified
- [x] Comps inputs tie to Step 3, Step 4 and Step 6 outputs; NVIDIA NTM EPS within 5% of the second source (reconciliation)
- [x] In Excel: Comps tab blended value 248.13, comps value 338.80, NVIDIA NTM P/E 14.0× — matching `comps_blend.csv` and the m7 report
- [x] X4: workbook Comps equals Python (automatic only where LibreOffice is installed; otherwise the Excel check above)
- [x] Comps table read: NTM weights, exclusions (marked *), each peer's multiples plausible
- [x] Football field and growth-vs-multiple chart read; the DCF–comps gap understood (I-65)

## S — sign-off (Kyan)
- [x] S7-D1 to S7-D9 accepted in `decision_log.md` (or changes requested)
- [x] `m7_check_report.txt` saved as `docs\evidence\m7_check_report_<date>.txt`
- [x] Step 7 commit made
- [x] Approval to start Step 8

Signed off by: ___Kyan Soni_________  Date: ____2026-11-04________
