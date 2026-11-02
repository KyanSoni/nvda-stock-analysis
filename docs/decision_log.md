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

M2-D1 to M2-D10 were approved as recommended on 2026-11-02. M2-D11 onwards come from the evidence in the first collection
(`20261102T230040Z`) and await sign-off.

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
| M2-D11 | Guarded fallback concepts (used only for periods where the guard concepts are absent or zero, enforced by C13): AVGO net income `ProfitLoss` (guard: NCI net income) and equity incl. NCI (guard: `MinorityInterest`); QCOM equity incl. NCI (guard: `MinorityInterest`); INTC operating cash flow from continuing operations (guard: discontinued-operations cash flow); INTC cash incl. restricted cash where `CashAndCashEquivalentsAtCarryingValue` is untagged (FY2019–FY2023; confirmed equal to balance-sheet cash for FY2022–FY2023, I-27) | Proposed | 2026-11-02 |
| M2-D12 | Derived components, labelled `derived_component` and checked by C14: total liabilities = (liabilities + equity) − total equity incl. NCI for AMD and INTC; gross profit = revenue − cost of revenue for QCOM. Inputs are support items flagged `support_item=True` | Proposed | 2026-11-02 |
| M2-D13 | Prices: yfinance `Close` is split-adjusted, so `close_as_traded` = Close × later split ratios is added; references compared to the cent; market cap = cutoff close rounded to the cent × cover-page shares (I-25, I-26) | Proposed | 2026-11-02 |
| M2-D14 | If FRED does not respond, `fetch_step2.py --add-rates <collection>` adds FRED or, failing that, the US Treasury daily par yield file (10 Yr) to the same collection; the source used is recorded in `market_inputs.csv` | Proposed | 2026-11-02 |
| M2-D15 | LTM readiness (C18): every flow item must have all four latest fiscal quarters (reported or derived) for every company | Proposed | 2026-11-02 |

