# Issue log — NVIDIA Stock Analysis

Severity: High / Medium / Low. "Blocks" names the sign-off that cannot happen while the issue is open.
Evidence refers to the snapshot `companyfacts_CIK0001045810_20261102T221326Z.json` (sha256 `19ef503a…`) unless stated.

| ID | Issue | Severity | Blocks | Status |
|---|---|---|---|---|
| I-1 | OneDrive syncing Git, venv or live database files can cause conflicts. Mitigated: venv outside OneDrive (D18), data git-ignored (M1-k) | Low | — | Mitigated |
| I-2 | Claude's workspace cannot reach sec.gov, Yahoo or PyPI; all pipeline runs happen on Kyan's machine (D10) | Low | — | Accepted |
| I-3 | SEC requires a User-Agent with contact details and limits requests to 10/second; handled by `SEC_USER_AGENT` and a request delay | Low | — | Handled |
| I-4 | XBRL concepts differ by company and year; handled by explicit candidate lists and per-row `concept`. Peers will need their own lists (M2) | Medium | M2 | Open |
| I-5 | NVIDIA re-cut its segments in FY27; only matters if D15 = segment level | Low | Phase 5 | Open |
| I-6 | The build guide still names TSM and "yfinance first" (conflicts with D1, D3); update after M1 sign-off | Low | — | Open |
| I-7 | Build guide schema lacked provenance columns; M1's observations layer carries them | Medium | — | Resolved 2026-11-02 |
| I-8 | No sourced NTM estimates yet (D13) | Medium | Phases 4, 7a | Open |
| I-9 | Full dependency lock: `requirements-lock.txt` generated 2026-11-02 from the verified venv (17 packages, 4 pins match) | — | — | Closed 2026-11-02 |
| I-10 | Real test run: `35 passed, 4 deselected` on Python 3.14.8 / pandas 3.1.0 / pytest 9.1.1, 2026-11-02 After the C11 update: `41 passed, 4 deselected` (2026-11-02) | — | — | Closed 2026-11-02 |
| I-11 | Reference values from NVIDIA's FY2026 10-K (accession 0001045810-26-000021, pp.51, 53, 55): 15 rows covering all 12 line items for FY2026 plus FY2025 revenue and FY2024 EPS/shares (split-adjusted). Extracted by Claude from the 10-K text supplied by Kyan; spot-checked by Kyan. All 15 tie exactly (`pytest -m reconciliation`, 2026-11-02) | — | — | Closed 2026-11-02 |
| I-12 | Capex coverage. `PaymentsToAcquirePropertyPlantAndEquipment`: annual FY2010–FY2012, 9M to FY2020. `PaymentsToAcquireProductiveAssets`: 9M from FY2021, annual FY2022–FY2026. No standard us-gaap concept has annual capex for FY2013–FY2021 (diagnostics C and G). Likely a company-specific `nvda:` tag not carried by companyfacts — unverified; check in the FY2021 10-K Inline XBRL viewer. FY2023 Q1/Q2 also untagged. FY2022–FY2026 annual is complete | Medium | — | Resolved by M1-l (2026-11-02); history decision D21 |
| I-13 | Stock splits. Inside FY2017–FY2026 diluted shares and EPS sit on three bases: FY2017–FY2019 pre-split (625–649m shares), FY2020–FY2022 after the first split only (2,472–2,535m), FY2023–FY2026 after both (24,514–25,070m). EPS restatement ratios 0.25 and 0.1, share ratios 4 and 10. `restated` cannot tell split adjustments from accounting restatements, and FY2022 shows `restated=False` despite its older basis | High | Phase 3 (D20), not M1 | Open |
| I-14 | Cash-flow items are reported in 10-Qs as year-to-date only, so Q2/Q3 three-month values appear as `only_ytd_reported` gaps (19 each for operating cash flow and capex). Deriving them (6M − Q1, 9M − 6M) is a separate decision for LTM work | Medium | M2 / Phase 3 | Open |
| I-15 | SEC `fy`/`fp` are filing-level tags (a FY2026 10-K tags its FY2025 comparatives fy=2026); labels therefore come from dates (M1-e) | Low | — | Handled |
| I-16 | XBRL scale errors in diluted shares, FY2008–FY2012 only: early filings tagged thousands as units. 7 selected rows were later corrected (ratio 1,000); 3 selected rows carry the erroneous latest-filed value (FY2010 Q2, Q3, 9M; ratio 0.001); FY2008 and FY2009 annual values are wrong but unflagged by `restated` because only the erroneous value exists. All outside the target window. Detected by C11/W1: 15 flagged rows, all diluted shares FY2010–FY2012, 0 inside the window (m1_check 2026-11-02) | Medium | — (High if pre-FY2017 data is ever used) | Open, monitored |
| I-17 | Genuine restatement of FY2017 interim periods (Q1, Q2, 6M): net income +3% to +6%, operating cash flow +3% to +5%, EPS 0.33→0.35, 0.40→0.41, 0.73→0.76; revenue unchanged. Pattern fits retrospective adoption of an accounting standard (hypothesis: ASU 2016-09); cause to be confirmed in the FY2017/FY2018 10-K notes. Latest-filed values (D4) are correct | Low | — | Open (verify before narrative use) |
| I-18 | Rounding and small revisions FY2013–FY2016: most restated non-per-share rows differ by ≤ $0.5m (NVIDIA moved from thousands to millions); four rows differ by $0.7m–$1.4m (< 0.15%): equity FY2013 Q4, FY2014 Q4; gross profit and net income FY2016 Q3 | Low | — | Accepted |
| I-19 | One live run (2026-11-02 22:16 UTC) sent a malformed User-Agent (PowerShell `""` merged two strings). SEC returned the same bytes; no effect on data. `m1_check.py --live` now checks the variable's format | Low | — | Closed 2026-11-02 |
