# Step 6 (M6) acceptance checklist — DCF valuation

Step 6 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m6_check.py` reruns every automated item and writes `data\clean\step6\m6_check_report.txt`.
Builds on Step 5. Inputs: Step 5 model and assumptions, Step 3 `v_valuation_cutoff`, Step 4 `v_beta`, `config\dcf.yaml`.

Pre-check in Claude's workspace (2026-11-03; LibreOffice available): D1–D4 pass; X3 the workbook's WACC and DCF,
recalculated by LibreOffice, equal Python in all 18 ticker × scenario cases (worst relative difference 9e-14) and the
NVIDIA Base WACC × g grid matches; Step 5 X1 still passes with the new tabs; CSV outputs byte-identical on rerun;
6 NVIDIA 10-Q references tie; Step 6 offline tests 7 passed, reconciliation 3 passed.
NVIDIA: WACC 13.87%; Bear 66.09, Base 168.42, Bull 226.92; weighted 157.47 vs 202.06 (−22.1%).

Kyan's run (2026-11-04 00:30 UTC): Step 6 tests 7 passed; offline 118 passed; run_step6 D1–D4 PASS, D5 warnings INTC and
QCOM as expected; 6/6 CSV outputs reproducible; reconciliation 15 passed, 2 skipped (LibreOffice comparisons, replaced by the
Excel check); m6_check all PASS except MANUAL items. 10-Q spot-check by Kyan: all six values tie (marketable equity securities
42,783 on the balance sheet). Decisions S6-D1 to S6-D10 confirmed 2026-11-04 (analyst review delegated by Kyan; reasons in
the decision log; new issues I-62, I-63).

## T — technical (it runs) — on Kyan's machine
- [x] Offline suite passes, including `tests\test_step6.py`
- [x] `run_step6.py` exits 0 (D1–D4 pass; D5 warnings for INTC and QCOM expected, I-58)
- [x] CSV outputs byte-identical on rerun
- [x] `excel\NVDA_Forecast.xlsx` opens in Excel without repair messages and has WACC, DCF and DcfData tabs

## V — data verified
- [x] 6 NVIDIA references (cash, marketable debt and equity securities, debt, diluted shares, H1 revenue) tie to the Q2 FY2027 10-Q; Kyan spot-checks marketable equity securities 42,783 on its balance sheet
- [x] In Excel: DCF tab shows **OK** for "live value equals Python" and "terminal growth below WACC" for NVDA in all three scenarios and for one peer (ticker switch)
- [x] X3: workbook DCF equals Python (automatic only where LibreOffice is installed; otherwise the Excel check above)
- [x] WACC tab read: beta 2.205 raw → 1.807 adjusted, Ke 13.95%, WACC 13.87%; judged against the sensitivity grid
- [x] Valuation read: Bear / Base / Bull, weighted, terminal-value share (58–69%), implied exit multiple (about 7×) vs peer multiple (26×)
- [x] Reverse DCF read: the price implies FY2028 Data Center growth 110% (model 72%), or WACC 12.0%, or terminal growth 5.3%
- [x] Peer flags understood (I-58) and the sector-wide pattern noted for Step 7 (I-60)

## S — sign-off (Kyan)
- [x] S6-D1 to S6-D10 accepted in `decision_log.md` (confirmed 2026-11-04)
- [x] `m6_check_report.txt` saved as `docs\evidence\m6_check_report_<date>.txt`
- [x] Step 6 commit made
- [x] Approval to start Step 7

Signed off by: __Kyan Soni__________  Date: ____2026-11-04_______
