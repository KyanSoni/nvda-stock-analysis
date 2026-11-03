# Step 3 (M3) acceptance checklist — extended facts, PostgreSQL database, ratio views

Step 3 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m3_check.py` reruns every automated item and writes `data\clean\step3\m3_check_report.txt`.
Collection: `20261102T230040Z` (the signed-off Step 2 collection). Cutoff: 2026-11-02. Database: PostgreSQL, schema `analytics`.

Pre-check in Claude's workspace (2026-11-03, PostgreSQL 16, Python 3.13, a temporary local server — **not** evidence for sign-off):
facts stage 156/156 error-level checks pass and rerun byte-identical; database DB1–DB6 pass and a second rebuild gives
byte-identical exports (10/10); 6,996 SQL cells equal the Python recomputation; 60 filing references and 2 reported ratios tie;
Step 3 offline tests 11 passed, database tests 4 passed.

Kyan's run (2026-11-03 15:21 UTC, PostgreSQL 18.6, Python 3.14.8): offline 85 passed; db 4 passed; reconciliation 9 passed;
156/156 error-level checks; facts rerun 4/4 and exports 10/10 byte-identical; V1 6,996 cells equal. The only FAIL (S_git) was
a bug in `m3_check.py` itself (I-43), fixed the same day; rerun the check for the evidence copy.

## T — technical (it runs) — on Kyan's machine
- [x] PostgreSQL 13 or later reachable; `psql` found; database `nvda_analysis` exists; password only in `$env:PGPASSWORD`
- [x] Offline suite passes (`& $vpy -m pytest`), including `tests\test_step3.py`
- [x] `run_step3.py all` exits 0; every error-level check passes; facts rerun byte-identical
- [x] Database builds; DB1–DB6 pass; second rebuild gives byte-identical exports
- [x] `& $vpy -m pytest -m db` passes (constraints reject a reported row without accession and an unknown basis)

## V — data verified
- [x] C24: every Step 2 row carried into Step 3 unchanged
- [x] C19/C20: split-adjusted EPS × shares reproduces net income in every window year; no share jumps in the window
- [x] C21–C23: derived sums recompute; declared zeros only where configured; manual facts file empty and valid
- [x] 60 Step 3 filing references (10 new line items × 6 companies, latest 10-Ks) tie exactly, including every derived sum and declared zero
- [x] Reported ratios tie: NVIDIA FY2026 gross margin 71.1% and effective tax rate 15.1%
- [x] V1: every numeric cell of `v_ratios_annual`, `v_ratios_ltm`, `v_valuation_cutoff` equals the independent Python recomputation
- [x] Warnings reviewed: W3 coverage gaps (I-34), W4 LTM gaps and the EBITDA fallback (I-35, S3-D11)
- [x] Kyan spot-checked at least three references against the 10-Ks (suggested: NVDA total debt 999 + 7,469; AVGO no short-term investments line; INTC D&A 10,757 + 949)
- [x] Valuation table and the three query results read and judged sensible (analyst review, 2026-11-03):
    - NVDA 25.2× LTM P/E and 24.1× EV/EBITDA on 302,969 LTM revenue; net cash (−23,220) even after the $25.0bn June 2026 notes, checked in the Q2 FY2027 10-Q (I-45), so EV < market cap. Consistent with the reported FY2026 margin (71.1%) and tax rate (15.1%)
    - AMD's 112.3× EV/EBITDA uses FY2025 EBITDA against today's EV (S3-D11): treat as indicative only; Step 7 must not rank AMD on it
    - INTC has negative LTM net income, so P/E is correctly blank, not negative
    - AVGO (net debt 35,444), QCOM (6,966) and MRVL (1,030) have EV above market cap; AMD, INTC and NVDA are net cash
    - NVDA 3-year average ROE 104% is arithmetic, not an error: net income is large relative to average equity in each year

## S — sign-off (Kyan)
- [x] S3-D9 to S3-D11 accepted (decided by Claude as analyst at Kyan's request; confirmed by the commit); S3-D6 deviation (I-40) and C20 tightening accepted in `decision_log.md`
- [x] **S3-D12 decided**: debt securities only, matching NVIDIA's own "marketable debt securities" line (34,143 at the valuation date); equity stakes (42,783) go into the Step 6 bridge separately (I-44). D21 decided: capex history accepted as a gap
- [x] Open issues reviewed (I-34, I-36, I-40, I-41; none blocks Step 3 except S3-D12)
- [ ] `m3_check_report.txt` saved as `docs\evidence\m3_check_report_<date>.txt`
- [ ] Step 3 commit made
- [ ] Approval to start Step 4

Signed off by: ____________  Date: ____________
