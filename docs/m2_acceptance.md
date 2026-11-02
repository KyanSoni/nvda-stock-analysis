# Step 2 (M2) acceptance checklist — peers and market data

Step 2 is complete only when every box below is ticked **and** Kyan signs off. Code running is not enough.
`python\m2_check.py` reruns every automated item and writes `data\clean\step2\m2_check_report.txt`.
Collection: `20261102T230040Z` (started 2026-11-02 18:00 New York time). Cutoff: 2026-11-02.
Evidence: `docs\evidence\m2_check_report_2026-11-02.txt` (run 2026-11-02 23:34 UTC on Kyan's machine).

## T — technical (it runs)
- [x] yfinance 1.7.0 installed from wheels on Python 3.14.8; `pip check` clean; pinned and locked (I-22)
- [x] Collection: 9 registrants' SEC files, 8 price files saved with hashes
- [x] 10-year yield added to the collection (`--add-rates`, Treasury 10 Yr 4.91% on 2026-11-02, I-29)
- [x] Offline suite passes on Kyan's machine: `74 passed, 7 deselected`
- [x] `m2_check.py`: pipeline exits 0; 115/115 error-level checks pass; rerun byte-identical (8/8 outputs)

## V — data verified (checked on the real collection on 2026-11-02)
- [x] I1: every CIK matches SEC's ticker file; predecessor chains verified; fiscal year-ends match SEC (M2-D1, M2-D5)
- [x] C1–C18 pass for all six companies (C10 now: snapshot hashes are collection files)
- [x] NVIDIA's 1,175 reported rows identical to M1 (same snapshot, sha256 `19ef503a…`)
- [x] Annual coverage, each company's 10 years: complete for all 12 line items except NVIDIA capex FY2017–FY2021 (known, I-12)
- [x] C18: the four latest quarters are complete for every flow item and company
- [x] Concept additions and derivations evidenced and logged (M2-D11, M2-D12, I-24)
- [x] 56 SEC reference values from the peers' latest 10-Ks tie exactly, including every fallback and derived value
- [x] 6 price references tie to Nasdaq to the cent (M2-D10)
- [x] P1–P3, P5: trading days match SPY; prices consistent; NVDA (2021, 2024) and AVGO (2024) splits match SEC share counts
- [x] P4b: 10-year yield 4.91% observed on the cutoff day (US Treasury par yield, 10 Yr)
- [x] Kyan spot-checked peer reference values against the 10-Ks (AVGO net income, QCOM total assets, INTC cash FY2023)

## S — sign-off (Kyan)
- [x] M2-D11 to M2-D15 accepted in `decision_log.md` (2026-11-02)
- [x] Open issues reviewed (I-21, I-23, I-28 scheduled for later phases; none blocks Step 2)
- [x] Step 2 commit made
- [ ] Approval to start Step 3 (SQL database and ratio views)

Signed off by: Kyan Soni (by making the Step 2 commit)  Date: 2026-11-02
