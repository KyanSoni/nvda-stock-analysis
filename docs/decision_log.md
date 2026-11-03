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

## Step 2 / M2 decisions (peers and market data)

M2-D1 to M2-D10 were approved as recommended on 2026-11-02. M2-D11 to M2-D15 come from the evidence in the first collection
(`20261102T230040Z`) and were accepted by Kyan on 2026-11-02.

| ID | Decision | Status | Date |
|---|---|---|---|
| M2-D1 | Predecessor registrants fetched and merged per company, rows tagged `entity_cik`/`entity_role`; the latest-filed rule (D4) picks between them. Verified: AVGO = Broadcom Inc. (0001730168) <- Broadcom Pte./Ltd. (0001649338) <- Avago Technologies (0001441634); MRVL = Marvell Technology, Inc. (0001835632) <- Marvell Technology Group (0001058057) | Confirmed | 2026-11-02 |
| M2-D2 | Peers start on NVIDIA's candidate lists; a concept is added only on availability evidence, logged here (see M2-D11) | Confirmed | 2026-11-02 |
| M2-D3 | Q2 = 6M − Q1 and Q3 = 9M − 6M for additive flow items (same fiscal-year start and concept), labelled `derived_quarter` | Confirmed | 2026-11-02 |
| M2-D4 | One combined `facts_selected.csv` with a `ticker` column plus per-ticker reports. Implemented under `data/clean/step2/` (combined files) and `data/clean/step2/<TICKER>/`, so M1's outputs in `data/clean/` stay as signed off; NVIDIA regression test against M1 | Confirmed (location refined) | 2026-11-02 |
| M2-D5 | Fiscal year-end month per company in `config/universe.yaml`, verified against SEC `fiscalYearEnd` (52/53-week ends in the first 7 days of a month belong to the previous month): NVDA 1, AMD 12, AVGO 10, MRVL 1, QCOM 9, INTC 12 | Confirmed | 2026-11-02 |
| M2-D6 | Daily prices from 2016-01-01 to the cutoff via yfinance `history(auto_adjust=False, actions=True)`; raw files saved with hashes | Confirmed | 2026-11-02 |
| M2-D7 | Shares outstanding from SEC cover pages (`dei:EntityCommonStockSharesOutstanding`, all share classes in the latest filing on or before the cutoff); yfinance share count is a cross-check only (W2 warns above 5%) | Confirmed | 2026-11-02 |
| M2-D8 | 10-year yield: FRED DGS10, latest observation on or before the cutoff, at most 5 days old | Confirmed | 2026-11-02 |
| M2-D9 | Peer reference values: at least 3 per peer from the latest 10-K (56 used) | Confirmed | 2026-11-02 |
| M2-D10 | Price reference values: NVDA, AVGO, SPY closes on two dates against Nasdaq historical quotes (6 used) | Confirmed | 2026-11-02 |
| M2-D11 | Guarded fallback concepts (used only for periods where the guard concepts are absent or zero, enforced by C13): AVGO net income `ProfitLoss` (guard: NCI net income) and equity incl. NCI (guard: `MinorityInterest`); QCOM equity incl. NCI (guard: `MinorityInterest`); INTC operating cash flow from continuing operations (guard: discontinued-operations cash flow); INTC cash incl. restricted cash where `CashAndCashEquivalentsAtCarryingValue` is untagged (FY2019–FY2023; confirmed equal to balance-sheet cash for FY2022–FY2023, I-27) | Confirmed | 2026-11-02 |
| M2-D12 | Derived components, labelled `derived_component` and checked by C14: total liabilities = (liabilities + equity) − total equity incl. NCI for AMD and INTC; gross profit = revenue − cost of revenue for QCOM. Inputs are support items flagged `support_item=True` | Confirmed | 2026-11-02 |
| M2-D13 | Prices: yfinance `Close` is split-adjusted, so `close_as_traded` = Close × later split ratios is added; references compared to the cent; market cap = cutoff close rounded to the cent × cover-page shares (I-25, I-26) | Confirmed | 2026-11-02 |
| M2-D14 | If FRED does not respond, `fetch_step2.py --add-rates <collection>` adds FRED or, failing that, the US Treasury daily par yield file (10 Yr) to the same collection; the source used is recorded in `market_inputs.csv` | Confirmed | 2026-11-02 |
| M2-D15 | LTM readiness (C18): every flow item must have all four latest fiscal quarters (reported or derived) for every company | Confirmed | 2026-11-02 |


## Step 3 / M3 decisions (extended facts, PostgreSQL database, ratio views)

S3-D1 to S3-D8 were proposed in the Step 3 build guide on 2026-11-02 and approved by Kyan's reply asking for the
PostgreSQL build ("im using postgressql…"). S3-D4 below records that change from the guide's SQLite plan. S3-D9 to S3-D12
come from the evidence in the signed-off collection `20261102T230040Z` and need Kyan's acceptance at sign-off.
Where the implementation differs from the wording in the guide, the difference is stated in the row.

| ID | Decision | Status | Date |
|---|---|---|---|
| S3-D1 | New line items (`config/step3.yaml`): current assets, current liabilities, inventory, short-term investments, total debt, D&A, income tax, pre-tax income, interest expense, SBC. Support items (not used directly): debt current, debt non-current, depreciation, amortisation of intangibles, a per-company D&A base, net income to common. Candidate lists come from the availability survey; per-company overrides only where a company does not tag the common concept | Approved | 2026-11-02 |
| S3-D2 (D20) | Split adjustment: a reported EPS or share count is on the share basis of its **filing date**; factor = product of split ratios with split date after the filed date (split table from Step 2 corporate actions, confirmed by P3). Shares × factor, EPS ÷ factor, in separate columns `split_factor`, `value_split_adjusted`, `display_split_adjusted`; reported values untouched. Checks C19 (adj. EPS × adj. shares ≈ net income to common, else net income, within EPS rounding + 3%, 10-year window) and C20 (no jump over **2×** in the adjusted annual share series inside the window; the guide said 3×, 2× is stricter) | Approved (C20 tightened) | 2026-11-02 |
| S3-D3 (D14) | Ratio definitions as in the guide's table, implemented in `sql/views.sql` and independently in `python/step3_reference.py`. Growth/CAGR need the exact earlier fiscal year; margins need revenue > 0; ROE needs average equity > 0; FCF conversion needs NI > 0; net debt/EBITDA and EV/EBITDA need EBITDA > 0; effective tax rate only when pre-tax > 0 and the rate is 0–100%, else 21% statutory with `tax_rate_note`. Any other case gives NULL, never 0 | Approved | 2026-11-02 |
| S3-D4 | **Database: PostgreSQL** (Kyan's choice) instead of the guide's SQLite. Exact `numeric` types; schema `analytics` rebuilt from scratch by `python/step3_db.py` through `psql` (`\copy`, `ON_ERROR_STOP`), so no Python driver is needed. Connection in `config/database.yaml`; password only from `$env:PGPASSWORD` or pgpass, never stored. Minimum server version 13 | Approved (replaces SQLite) | 2026-11-02 |
| S3-D5 | PEG: historical only (P/E ÷ 100 × 3-year net income CAGR, NULL if CAGR ≤ 0). Forward PEG waits for D13 in Step 4 | Approved | 2026-11-02 |
| S3-D6 | Net debt = total debt − cash − short-term investments; invested capital = total debt + `stockholders_equity` − cash − short-term investments, averaged over the year for ROIC. **Difference from the guide:** the guide said equity *including* minority interests; the implementation uses the Step 2 `stockholders_equity` line item, which is parent equity except where M2-D11's NCI-inclusive fallback applies (AVGO, QCOM). NCI is immaterial for these companies; see I-40. Lease liabilities excluded; not yet stored (I-41) | Approved, deviation to accept | 2026-11-02 |
| S3-D7 | Excel and Power BI read the CSV exports in `data/clean/step3/exports/` (one per view and query, ordered, hashed in `db_manifest.json`); Power BI can also connect to PostgreSQL directly | Approved | 2026-11-02 |
| S3-D8 | Annual ratios per company fiscal year (own labels); LTM at each quarter end = sum of 4 consecutive quarters spanning 250–300 days; no calendar alignment in Step 3 | Approved | 2026-11-02 |
| S3-D9 | Derivations (labelled `derived_sum`, checked by C21): total debt = debt current + debt non-current for every company; D&A = depreciation + amortisation of intangibles (AVGO, INTC); D&A = D&A base + amortisation of intangibles (AMD, MRVL). AMD's amortisation term is taken as 0 through FY2021 only (no acquisition intangibles amortised before Xilinx), recorded in each row's transformation | Proposed — accept at sign-off | 2026-11-03 |
| S3-D10 | Declared zeros (`declared_zero`, C22): AVGO (from FY2016) and MRVL (from FY2019) have no short-term investments line on the balance sheet; value 0 at each balance-sheet date with no reported value. Confirmed on the latest 10-Ks (current assets are cash, receivables, inventory and other only). Manual facts (`manual_from_filing`, C23) are supported but `config/manual_facts.csv` is empty | Proposed — accept at sign-off | 2026-11-03 |
| S3-D11 | LTM completeness: C18 stays an error for the Step 2 flow items; the new flow items are warning W4. Where LTM D&A is incomplete, valuation uses the latest fiscal year's EBITDA and says so in `ebitda_basis` (AMD at the cutoff) | Proposed — accept at sign-off | 2026-11-03 |
| S3-D12 | **Open — Kyan to decide.** NVIDIA short-term investments from the FY2026 10-K onwards: the balance-sheet line "Marketable securities" (51,951 at FY2026 Q4) now includes publicly-held equity securities (12,886); NVIDIA tags only the debt part as `DebtSecuritiesCurrent` (39,065), which the pipeline uses, consistent with its earlier `MarketableSecuritiesCurrent` history (debt securities). Options: (a) keep debt securities only — consistent over time; equity stakes are not cash-like (recommended); (b) use the balance-sheet line via `manual_from_filing` rows for FY2026 Q4 onwards. Effect of (b): NVIDIA EV lower by about 13bn of 4,846bn (0.3%) | Open | 2026-11-03 |
