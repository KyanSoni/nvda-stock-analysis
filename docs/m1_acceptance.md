# M1 acceptance checklist — NVIDIA SEC companyfacts retrieval and validation

M1 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m1_check.py` re-runs every automated item and writes `data\clean\m1_check_report.txt`.
Evidence: `docs\evidence\m1_check_report_2026-11-02.txt` (run 2026-11-02 22:36 UTC, `--live`).
Snapshot: `companyfacts_CIK0001045810_20261102T221620Z.json`, sha256 `19ef503a5770f566…` (identical to the 22:13 fetch).

## T — technical (it runs)
- [x] Files in `C:\Users\kyans\OneDrive\Stock Analysis\nvda-stock-analysis`: 30/30 expected files present
- [x] `requirements-lock.txt` generated from the verified venv; the 4 pins match (I-9)
- [x] Offline suite with real pytest on Python 3.14.8 / pandas 3.1.0: `41 passed, 4 deselected` (I-10)
- [x] Live test: `1 passed`
- [x] Snapshot run exits 0: C1–C11 PASS; W1 WARN (outside the window, review only)
- [x] Rerun reproduces byte-identical outputs: all 6 outputs MATCH

## V — data verified
- [x] C1: 27,281 of 27,281 observations kept in `sec_observations.csv`
- [x] C3: every reported row has concept, unit, accession, form, filed date and snapshot hash
- [x] C4/C9: every derived row is labelled `derived_q4`, cites both source accessions and recomputes
- [x] C11: 0 scale anomalies inside FY2017–FY2026; W1's 15 rows (diluted shares FY2010–FY2012) match I-16
- [x] Annual coverage FY2017–FY2026: 11 of 12 line items 10/10; capex 5/10 (FY2017–FY2021 not in companyfacts; I-12, D21)
- [x] Capex concepts reviewed and confirmed (M1-l)
- [x] `gap_report.csv` reviewed: 66 gaps, each with a reason, none filled (I-12, I-14; EPS/shares Q4 by design)
- [x] Restated rows reviewed: rounding (I-18), FY2017 restatement (I-17), splits (I-13), scale errors (I-16)
- [x] 15 reference values from the FY2026 10-K with accession and location (I-11)
- [x] `pytest -m reconciliation` passes: all 15 reference values tie exactly
- [x] Kyan spot-checked at least 3 reference values against the 10-K Inline XBRL viewer

## S — sign-off (Kyan)
- [x] Proposed decisions M1-b to M1-n accepted (decision_log.md, 2026-11-02)
- [x] Open issues reviewed; none blocks M1 sign-off (open items are scheduled for M2 or Phase 3)
- [x] Git identity set; no unexpected files; raw data and outputs ignored
- [x] First commit made
- [ ] Approval to start M2 (peers and market data)

Signed off by: Kyan Soni (by making the M1 commit)  Date: 2026-11-02
