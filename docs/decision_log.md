# Decision log — NVIDIA Stock Analysis

Status: **Confirmed** (signed off by Kyan) · **Proposed** (awaiting sign-off) · **Open** (not decided).
A decision changes only through a new dated entry here; definitions are never changed silently.

## Project decisions

| ID | Decision | Status | Date |
|---|---|---|---|
| D1 | Peers: AMD, AVGO, MRVL, QCOM, INTC (TSM removed from the build guide's set) | Confirmed | 2026-10-26 |
| D2 | Benchmarks SPY and SOXX, both for price-performance charts and separate beta comparisons | Confirmed | 2026-10-26 |
| D3 | Statements from SEC companyfacts; yfinance only for prices and market data | Confirmed | 2026-10-26 |
| D4 | Restatements: latest-filed value used; original value and accession kept for audit. Reaffirmed 2026-11-02: suspected XBRL errors are flagged (C11/W1), never corrected by changing this rule | Confirmed | 2026-10-26 |
| D5 | Peer periods: LTM = last 4 reported quarters, each company's own fiscal labels kept | Confirmed | 2026-10-26 |
| D6 | GAAP throughout; stock-based compensation treated as a cost | Confirmed | 2026-10-26 |
| D7 | Project folder: `C:\Users\kyans\OneDrive\Stock Analysis\nvda-stock-analysis` | Confirmed | 2026-10-26 |
| D8 | Version 2 in scope; built only after the upstream data pipeline is validated | Confirmed | 2026-10-26 |
| D9 | Windows 11 Home | Confirmed | 2026-10-26 |
| D10 | Kyan runs all commands locally and pastes results back | Confirmed | 2026-10-26 |
| D11 | Target 10 fiscal years where available, plus quarterly history for LTM; unavailable periods logged, never filled | Confirmed | 2026-10-26 |
| D12 | Valuation cutoff = latest completed trading day before data collection; actual date recorded; same cutoff for all market inputs | Confirmed | 2026-10-26 |
| D13 | Source for NTM estimates, or LTM-only comps | Open (blocks Phases 4, 7a) | |
| D14 | Exact scorecard formulas (ROIC, net debt incl. leases?, PEG growth) | Open (blocks Phase 4) | |
| D15 | Revenue modelled at total or segment level | Open (blocks Phase 5) | |
| D16 | Scenario drivers, WACC inputs, scenario weights, DCF/comps blend | Open (blocks Phases 5–7) | |
| D17 | Merged into D2 | Closed | 2026-10-26 |
| D18 | Python 3.14.8 (python.org), fresh venv at `%LOCALAPPDATA%\venvs\nvda-stock-analysis`, exact pins; old venv not reused | Confirmed | 2026-10-26 |
| D19 | GitHub repository name and visibility | Open (blocks first push, not M1) | |
| D20 | Split-adjusted per-share and share-count layer, derived from reported values with split dates and factors sourced from NVIDIA's filings; reported values never overwritten (issue I-13) | Open (blocks Phase 3) | 2026-11-02 |
| D21 | FY2013–FY2021 annual capex: accept as a logged gap, or enter from the 10-Ks as clearly labelled manual values (issue I-12) | Open (decide in Phase 3) | 2026-11-02 |

## M1 decisions (NVIDIA SEC companyfacts)

| ID | Decision | Status | Date |
|---|---|---|---|
| M1-a | Scope: NVIDIA only; 12 line items as in `config/project.yaml` | Confirmed | 2026-10-26 |
| M1-b | Two layers: `sec_observations` keeps every SEC observation unchanged; `nvda_facts_selected` holds one value per line item, period and basis | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-c | Concept choice: first listed candidate concept with an observation for that period; the concept used is recorded per row | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-d | Restatement rule (D4) applied within the chosen concept; ties broken by higher accession number | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-e | Fiscal labels derived from period dates (NVIDIA: year named after the January it ends in); SEC `fy`/`fp` kept as provenance only, because they describe the filing, not the period | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-f | Q4 for additive flow items = annual minus 9-month YTD with the same start date, labelled `derived_q4`; never derived for EPS or share counts, or when SEC reports a 3-month Q4 | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-g | Forms used for selection: 10-K, 10-K/A, 10-Q, 10-Q/A (others stay in observations only) | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-h | Duration windows (days): quarter 80–100, 6M 170–195, 9M 260–290, annual 355–375; other durations are kept in observations but not selected | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-i | Display values: USD and shares scaled to millions exactly (Decimal arithmetic); per-share values unscaled | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-j | SEC User-Agent read from the `SEC_USER_AGENT` environment variable so no email address is committed | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-k | Raw snapshots and outputs kept locally (OneDrive) and git-ignored; the snapshot hash in each output links them | Confirmed | 2026-10-26 (confirmed 2026-11-02) |
| M1-l | Capex keeps both candidates in this order: `PaymentsToAcquirePropertyPlantAndEquipment` (NVIDIA's concept to FY2020) then `PaymentsToAcquireProductiveAssets` (from FY2021). No third concept added: none covers FY2013–FY2021 annual values (I-12) | Confirmed | 2026-11-02 (confirmed 2026-11-02) |
| M1-m | C11 scale-anomaly check: values whose ratio to the first-filed value, or (for revenue, assets, liabilities, cash, diluted shares) to the previous period, is outside 0.01–100. Inside the target window it is an error; outside it is warning W1. Flagged rows are written to `anomalies.csv`; no value is changed | Confirmed | 2026-11-02 (confirmed 2026-11-02) |
| M1-n | Reconciliation accepts thousands separators ("215,938") and compares units case-insensitively; values must still tie exactly | Confirmed | 2026-11-02 (confirmed 2026-11-02) |
