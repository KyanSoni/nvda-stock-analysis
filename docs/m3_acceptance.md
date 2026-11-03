# Step 3 (M3) acceptance checklist — extended facts, PostgreSQL database, ratio views

Step 3 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m3_check.py` reruns every automated item and writes `data\clean\step3\m3_check_report.txt`.
Collection: `20261102T230040Z` (the signed-off Step 2 collection). Cutoff: 2026-11-02. Database: PostgreSQL, schema `analytics`.

Pre-check in Claude's workspace (2026-11-03, PostgreSQL 16, Python 3.13, a temporary local server — **not** evidence for sign-off):
facts stage 156/156 error-level checks pass and rerun byte-identical; database DB1–DB6 pass and a second rebuild gives
byte-identical exports (10/10); 6,996 SQL cells equal the Python recomputation; 60 filing references and 2 reported ratios tie;
Step 3 offline tests 11 passed, database tests 4 passed.

## T — technical (it runs) — on Kyan's machine
- [ ] PostgreSQL 13 or later reachable; `psql` found; database `nvda_analysis` exists; password only in `$env:PGPASSWORD`
- [ ] Offline suite passes (`& $vpy -m pytest`), including `tests\test_step3.py`
- [ ] `run_step3.py all` exits 0; every error-level check passes; facts rerun byte-identical
- [ ] Database builds; DB1–DB6 pass; second rebuild gives byte-identical exports
- [ ] `& $vpy -m pytest -m db` passes (constraints reject a reported row without accession and an unknown basis)

## V — data verified
- [ ] C24: every Step 2 row carried into Step 3 unchanged
- [ ] C19/C20: split-adjusted EPS × shares reproduces net income in every window year; no share jumps in the window
- [ ] C21–C23: derived sums recompute; declared zeros only where configured; manual facts file empty and valid
- [ ] 60 Step 3 filing references (10 new line items × 6 companies, latest 10-Ks) tie exactly, including every derived sum and declared zero
- [ ] Reported ratios tie: NVIDIA FY2026 gross margin 71.1% and effective tax rate 15.1%
- [ ] V1: every numeric cell of `v_ratios_annual`, `v_ratios_ltm`, `v_valuation_cutoff` equals the independent Python recomputation
- [ ] Warnings reviewed: W3 coverage gaps (I-34), W4 LTM gaps and the EBITDA fallback (I-35, S3-D11)
- [ ] Kyan spot-checked at least three references against the 10-Ks (suggested: NVDA total debt 999 + 7,469; AVGO no short-term investments line; INTC D&A 10,757 + 949)
- [ ] Valuation table and the three query results read and judged sensible

## S — sign-off (Kyan)
- [ ] S3-D9 to S3-D11 accepted; S3-D6 deviation (I-40) and C20 tightening accepted in `decision_log.md`
- [ ] **S3-D12 decided** (NVIDIA short-term investments: debt securities only, or the balance-sheet line)
- [ ] Open issues reviewed (I-34, I-36, I-40, I-41; none blocks Step 3 except S3-D12)
- [ ] `m3_check_report.txt` saved as `docs\evidence\m3_check_report_<date>.txt`
- [ ] Step 3 commit made
- [ ] Approval to start Step 4

Signed off by: ____________  Date: ____________
