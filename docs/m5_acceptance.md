# Step 5 (M5) acceptance checklist — 3-statement forecast model

Step 5 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m5_check.py` reruns every automated item and writes `data\clean\step5\m5_check_report.txt`.
Builds on Step 4. Inputs: collection `20261102T230040Z`, Step 3 exports, consensus snapshot `20261103T180459Z`.

Pre-check in Claude's workspace (2026-11-03; LibreOffice available): F1, F3 pass, NVIDIA history complete (F2);
37 10-K references tie; X2 balances for 6 companies × 3 scenarios × 5 years; X1 the workbook recalculated by LibreOffice
equals the Python model in all 18 cases (worst relative difference 9e-15); NVIDIA Base FY2027 revenue 411,573 vs
consensus 411,653, EPS 9.33 vs 9.31; Step 5 offline tests 8 passed, reconciliation 3 passed.

Kyan's run (2026-11-03 22:00 UTC): offline 111 passed; reconciliation 13 passed, 1 skipped (LibreOffice comparison, replaced by the Excel check);
m5_check all PASS except MANUAL items. Excel checks done by Kyan (Cover OK for NVDA Bear/Base/Bull and AMD); FY2026 Data Center
193,737 confirmed in the 10-K segment note (also FY2025 115,186, FY2024 47,525); Step 5 decisions accepted unchanged.

## T — technical (it runs) — on Kyan's machine
- [x] Offline suite passes, including `tests\test_step5.py`
- [x] `run_step5.py all` exits 0 (F1, F3, X2 pass; NVIDIA F2 complete)
- [x] CSV outputs byte-identical on rerun
- [x] `excel\NVDA_Forecast.xlsx` opens in Excel without repair messages

## V — data verified
- [x] 37 Step 5 references (NVIDIA FY2026 new items and Data Center revenue; 3–6 items per peer) tie to the 10-Ks
- [x] NVIDIA Data Center revenue FY2022–FY2026 entered with provenance (`config\manual_facts_step5.csv`); Kyan spot-checks FY2026 193,737 in the 10-K
- [x] In Excel: Cover shows **OK** for the balance check for NVDA in all three scenarios, and for AMD (ticker switch)
- [x] X1: workbook equals the Python model (automatic only where LibreOffice is installed; otherwise the Excel check above)
- [x] NVIDIA Base equals consensus for FY2027–FY2028 within 0.5%; Bear and Bull read and judged
- [x] Each NVIDIA driver's reason read (Assumptions tab, column I); disagreements changed in `config\model.yaml`
- [x] Peer warnings understood (I-51): their cases are mechanical (S5-D6)

## S — sign-off (Kyan)
- [x] S5-D1, S5-D3 driver values, S5-D5 to S5-D8 accepted in `decision_log.md`
- [ ] `m5_check_report.txt` saved as `docs\evidence\m5_check_report_<date>.txt`
- [ ] Step 5 commit made
- [ ] Approval to start Step 6

Signed off by: ____________  Date: ____________
