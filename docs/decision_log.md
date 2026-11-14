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
| D13 | Source for NTM estimates, or LTM-only comps | Confirmed — yfinance (Yahoo Finance) consensus snapshot with provenance, cross-checked against a second public source (S4-D1, S4-D2); Kyan's choice | 2026-11-03 |
| D14 | Exact scorecard formulas (ROIC, net debt incl. leases?, PEG growth) | Confirmed — ROIC and net debt as Step 3 (leases excluded, I-41); forward PEG per S4-D3; scoring rules S4-D7 | 2026-11-03 |
| D15 | Revenue modelled at total or segment level | Confirmed — two segments for NVIDIA (Data Center, Edge Computing), single line for peers (S5-D2); Kyan's choice | 2026-11-03 |
| D16 | Scenario drivers, WACC inputs, scenario weights, DCF/comps blend | Confirmed — scenario drivers: consensus-anchored base (S5-D3); WACC with Blume-adjusted beta (S6-D1, S6-D2), perpetuity terminal value with exit-multiple check (S6-D3), scenario weights 25/50/25 (S6-D4), all Kyan's choices, confirmed 2026-11-04; DCF/comps blend 50/50 (S7-D6) | 2026-11-04 |
| D17 | Merged into D2 | Closed | 2026-10-26 |
| D18 | Python 3.14.8 (python.org), fresh venv at `%LOCALAPPDATA%\venvs\nvda-stock-analysis`, exact pins; old venv not reused | Confirmed | 2026-10-26 |
| D19 | GitHub repository name and visibility | Open (blocks first push, not M1) | |
| D20 | Split-adjusted per-share and share-count layer, derived from reported values with split dates and factors sourced from NVIDIA's filings; reported values never overwritten (issue I-13) | Confirmed — implemented as S3-D2 (filing-date split factors, separate adjusted columns; C19/C20 pass) | 2026-11-03 |
| D21 | FY2013–FY2021 annual capex: accept as a logged gap, or enter from the 10-Ks as clearly labelled manual values (issue I-12) | Confirmed — option 1: accept as a logged gap. NVIDIA FCF analysis uses FY2022–FY2026 (5 complete years), which is all the Step 5 Historicals tab needs; revisit only if a 10-year FCF exhibit is wanted in Steps 8–9, by entering FY2017–FY2021 capex as `manual_from_filing` rows | 2026-11-03 |

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
come from the evidence in the signed-off collection `20261102T230040Z`. On 2026-11-03 Kyan asked Claude to take the open Step 3 decisions as a senior equity research analyst would; they are recorded below with reasons and become confirmed by Kyan's Step 3 commit.
Where the implementation differs from the wording in the guide, the difference is stated in the row.

| ID | Decision | Status | Date |
|---|---|---|---|
| S3-D1 | New line items (`config/step3.yaml`): current assets, current liabilities, inventory, short-term investments, total debt, D&A, income tax, pre-tax income, interest expense, SBC. Support items (not used directly): debt current, debt non-current, depreciation, amortisation of intangibles, a per-company D&A base, net income to common. Candidate lists come from the availability survey; per-company overrides only where a company does not tag the common concept | Approved | 2026-11-02 |
| S3-D2 (D20) | Split adjustment: a reported EPS or share count is on the share basis of its **filing date**; factor = product of split ratios with split date after the filed date (split table from Step 2 corporate actions, confirmed by P3). Shares × factor, EPS ÷ factor, in separate columns `split_factor`, `value_split_adjusted`, `display_split_adjusted`; reported values untouched. Checks C19 (adj. EPS × adj. shares ≈ net income to common, else net income, within EPS rounding + 3%, 10-year window) and C20 (no jump over **2×** in the adjusted annual share series inside the window; the guide said 3×, 2× is stricter) | Confirmed (C20 at 2×, stricter than the guide's 3×, accepted) | 2026-11-03 |
| S3-D3 (D14) | Ratio definitions as in the guide's table, implemented in `sql/views.sql` and independently in `python/step3_reference.py`. Growth/CAGR need the exact earlier fiscal year; margins need revenue > 0; ROE needs average equity > 0; FCF conversion needs NI > 0; net debt/EBITDA and EV/EBITDA need EBITDA > 0; effective tax rate only when pre-tax > 0 and the rate is 0–100%, else 21% statutory with `tax_rate_note`. Any other case gives NULL, never 0 | Approved | 2026-11-02 |
| S3-D4 | **Database: PostgreSQL** (Kyan's choice) instead of the guide's SQLite. Exact `numeric` types; schema `analytics` rebuilt from scratch by `python/step3_db.py` through `psql` (`\copy`, `ON_ERROR_STOP`), so no Python driver is needed. Connection in `config/database.yaml`; password only from `$env:PGPASSWORD` or pgpass, never stored. Minimum server version 13 | Approved (replaces SQLite) | 2026-11-02 |
| S3-D5 | PEG: historical only (P/E ÷ 100 × 3-year net income CAGR, NULL if CAGR ≤ 0). Forward PEG waits for D13 in Step 4 | Approved | 2026-11-02 |
| S3-D6 | Net debt = total debt − cash − short-term investments; invested capital = total debt + `stockholders_equity` − cash − short-term investments, averaged over the year for ROIC. **Difference from the guide:** the guide said equity *including* minority interests; the implementation uses the Step 2 `stockholders_equity` line item, which is parent equity except where M2-D11's NCI-inclusive fallback applies (AVGO, QCOM). NCI is immaterial for these companies; see I-40. Lease liabilities excluded; not yet stored (I-41) | Confirmed — deviation accepted: NCI is immaterial for all six companies, and parent equity matches the net income used for ROE | 2026-11-03 |
| S3-D7 | Excel and Power BI read the CSV exports in `data/clean/step3/exports/` (one per view and query, ordered, hashed in `db_manifest.json`); Power BI can also connect to PostgreSQL directly | Approved | 2026-11-02 |
| S3-D8 | Annual ratios per company fiscal year (own labels); LTM at each quarter end = sum of 4 consecutive quarters spanning 250–300 days; no calendar alignment in Step 3 | Approved | 2026-11-02 |
| S3-D9 | Derivations (labelled `derived_sum`, checked by C21): total debt = debt current + debt non-current for every company; D&A = depreciation + amortisation of intangibles (AVGO, INTC); D&A = D&A base + amortisation of intangibles (AMD, MRVL). AMD's amortisation term is taken as 0 through FY2021 only (no acquisition intangibles amortised before Xilinx), recorded in each row's transformation | Confirmed | 2026-11-03 |
| S3-D10 | Declared zeros (`declared_zero`, C22): AVGO (from FY2016) and MRVL (from FY2019) have no short-term investments line on the balance sheet; value 0 at each balance-sheet date with no reported value. Confirmed on the latest 10-Ks (current assets are cash, receivables, inventory and other only). Manual facts (`manual_from_filing`, C23) are supported but `config/manual_facts.csv` is empty | Confirmed | 2026-11-03 |
| S3-D11 | LTM completeness: C18 stays an error for the Step 2 flow items; the new flow items are warning W4. Where LTM D&A is incomplete, valuation uses the latest fiscal year's EBITDA and says so in `ebitda_basis` (AMD at the cutoff) | Confirmed | 2026-11-03 |
| S3-D12 | NVIDIA short-term investments. The FY2026 10-K shows one line "Marketable securities" (51,951 at FY2026 Q4) that includes publicly-held equity securities (12,886); NVIDIA tags only the debt part as `DebtSecuritiesCurrent` (39,065). Its Q2 FY2027 10-Q (accession 0001045810-26-000075) now presents the two as separate balance-sheet lines: marketable debt securities 34,143 and marketable equity securities 42,783 at 2026-07-26. **Decision: option (a), debt securities only** in net debt, EV and the ratio views, which is exactly NVIDIA's own debt-securities line. Reasons: consistent over NVIDIA's history in the pipeline, so no break in the series; equity stakes are price-volatile strategic holdings, not liquidity. They are not ignored: the Step 6 DCF bridge adds marketable equity securities as a separate, labelled non-operating asset at fair value from the latest filing (I-44). Effect of the alternative at the valuation date 2026-07-26: EV 42.8bn lower of 4,846bn (0.9%); EV/EBITDA 24.1 → 23.9; EV/revenue 16.0 → 15.9; P/E unchanged | Confirmed | 2026-11-03 |

## Step 4 / M4 decisions (scorecard, consensus estimates, provisional WACC)

Kyan chose the estimates source (yfinance consensus) and a provisional WACC now on 2026-11-03; the remaining
definitions follow the recommendations in the Step 4 plan and become confirmed by Kyan's Step 4 commit.

| ID | Decision | Status | Date |
|---|---|---|---|
| S4-D1 (D13) | Forward estimates: Yahoo Finance analyst consensus via yfinance `Ticker.earnings_estimate` and `revenue_estimate`, saved exactly as returned in `data/raw/estimates/<UTC id>/` with a manifest (bytes, SHA-256) by `fetch_step4.py`; parsed offline. Periods `0y` = current fiscal year not yet reported, `+1y` = next. Revenue estimates are stored for Step 7 | Confirmed (Kyan) | 2026-11-03 |
| S4-D2 | Cross-check: at least NVIDIA `0y` and `+1y` consensus EPS against a second public source, recorded in `tests/fixtures/estimates_crosscheck.csv` with URL and date; tolerance 5% (providers' consensus differs by contributor set and date) | Confirmed | 2026-11-03 |
| S4-D3 | Forward PEG = trailing GAAP P/E at the cutoff ÷ (100 × consensus EPS growth, `+1y` over `0y`). Not meaningful (scored fail) when P/E or growth is not positive; not scored when estimates are missing. Consensus EPS is usually on the providers' adjusted basis; only its growth rate is used, never its level (I-47) | Confirmed | 2026-11-03 |
| S4-D4 | Beta: 60 monthly total returns (adj_close at the last trading day of each month) ending the month before the cutoff, regression slope on SPY (D2); raw, not Blume-adjusted. SOXX beta is reported alongside, not used | Confirmed | 2026-11-03 |
| S4-D5 | Equity risk premium 5.0%, a labelled analyst assumption (mid-point of the guide's 4.5–5.5%); risk-free 4.91% from Step 2 (M2-D14) | Confirmed | 2026-11-03 |
| S4-D6 | Provisional WACC = E/(D+E)·Ke + D/(D+E)·Kd·(1 − t). Ke = rf + β·ERP; Kd = latest fiscal-year interest expense ÷ average total debt (that and the prior fiscal year-end); t = `tax_rate_used`; E = market cap at the cutoff; D = book total debt at the valuation balance-sheet date. Step 6 revisits every input (I-48) | Confirmed | 2026-11-03 |
| S4-D7 | Scoring: thresholds from the guide in `config/scorecard.yaml`; pass is strict (`>` or `<`), near miss inclusive (`>=` or `<=`); fundamentals from each company's latest fiscal year, valuation at the cutoff; gross margin compared with the median of the other five companies; a missing input is "not scored" (lowers the maximum) unless the rule says it is a fail: loss-making P/E, net income ≤ 0 for FCF conversion, EBITDA ≤ 0 for net debt/EBITDA, non-positive PEG | Confirmed | 2026-11-03 |
| S4-D8 | Estimates are fetched after the valuation cutoff (consensus cannot be retrieved as of a past date); allowed up to 7 days after it (check E2), with the fetch time on every row. A deviation from D12, accepted for estimates only | Confirmed | 2026-11-03 |

## Step 5 / M5 decisions (3-statement forecast model)

Kyan chose two segments (D15), a consensus-anchored base case (D16) and a Python-generated workbook on 2026-11-03.
The rest follow the Step 5 plan and become confirmed by Kyan's Step 5 commit.

| ID | Decision | Status | Date |
|---|---|---|---|
| S5-D1 | Model line items (`config/step5.yaml`): cost of revenue, R&D, SG&A, interest income, receivables, payables, PP&E, buybacks, dividends; selected with the M1/M2 rules from the signed-off collection. Guarded fallback: INTC PP&E incl. finance-lease ROU where `PropertyPlantAndEquipmentNet` is absent. QCOM receivables from `AccountsAndOtherReceivablesNetCurrent`, the concept on its balance-sheet line (I-52) | Confirmed | 2026-11-03 |
| S5-D2 (D15) | Revenue by segment for NVIDIA: Data Center = the 10-K "Data Center" market platform, entered as `manual_from_filing` for FY2022–FY2026 (`config/manual_facts_step5.csv`, FY2024 and FY2026 10-Ks); Edge Computing = total revenue − Data Center, labelled derived (matches NVIDIA's FY2027 presentation: Q2 FY2026 Data Center 41,096 + Edge 5,647 = 46,743). Peers: one revenue line (segment A = total) | Confirmed (Kyan) | 2026-11-03 |
| S5-D3 (D16) | NVIDIA scenarios in `config/model.yaml`, each driver with a reason and source. Base: FY2027–FY2028 revenue = consensus ($411.7bn, $692.2bn), Data Center growth then fading to 6% by FY2031; Bear: FY2027 = H1 actuals + Q3 guidance low end + flat Q4, then an AI-capex digestion year; Bull: Rubin ramp beats consensus. Margins, opex, tax (16–18% guidance) and capital returns as reasoned per driver | Confirmed (Kyan: consensus anchor; driver values accepted unchanged) | 2026-11-03 |
| S5-D4 | The model is `excel/NVDA_Forecast.xlsx`, written by `python/build_model.py` with live formulas; inputs only on Data and AssumptionsData (blue); assumptions are edited in `config/model.yaml` and the workbook rebuilt (edits in Excel are overwritten). The Power Query Scorecard workbook `excel/NVDA_Model.xlsx` stays separate | Confirmed (Kyan) | 2026-11-03 |
| S5-D5 | Simplifications: interest on opening balances (no circularity); other current / non-current assets and other liabilities held flat; all D&A runs through PP&E; other non-operating income (e.g. NVIDIA's equity-investment gains, 9,022 in FY2026) not forecast; equity = prior + net income + SBC − buybacks − dividends; buybacks = share of positive FCF; debt changes only by assumed issuance; cash and short-term investments are one plug line | Confirmed | 2026-11-03 |
| S5-D6 | Peer assumptions are mechanical, not investment views: years 1–2 revenue growth from consensus, then a linear fade to 5% by year 5 (Bear/Bull ±10pt); gross margin latest year (Bear −2pt, Bull +1pt); every other driver at its latest fiscal-year value. They exist so the ticker switch works and Step 6 can run a simplified peer DCF | Confirmed | 2026-11-03 |
| S5-D7 | A missing history value for a peer (F2 warning) is 0 in the model and counted on the Cover tab, never estimated; NVIDIA's history must be complete (F2 error) | Confirmed | 2026-11-03 |
| S5-D8 | Checks: X2 every company × scenario × year balances in the Python model; X1 the workbook, recalculated by LibreOffice, equals the Python model for 19 rows × 5 years × 18 cases (relative 1e-6). Where LibreOffice is not installed X1 is MANUAL: open the workbook in Excel, check Cover shows OK, flip ticker and scenario | Confirmed | 2026-11-03 |

## Step 6 / M6 decisions (DCF valuation)

Kyan chose on 2026-11-03: Blume-adjusted beta, perpetuity growth 3% as the headline with an exit-multiple cross-check,
scenario weights 25/50/25, and NVIDIA's listed equity stakes added at fair value. Settings in `config/dcf.yaml`.
Review on 2026-11-04: Kyan delegated the remaining calls to Claude acting as senior equity analyst; each was kept as built,
with the reason recorded in the row. Kyan's checks of the m6_check report and the Q2 FY2027 10-Q (all six values tie) are
the evidence.

| ID | Decision | Status | Date |
|---|---|---|---|
| S6-D1 (D16) | Beta = Blume-adjusted 60-month SPY beta from Step 4 (`v_beta`): 0.67 × raw + 0.33. NVIDIA 2.205 raw → 1.807. Resolves I-48: the raw beta is kept and shown; SOXX beta (0.87) is not used for CAPM because CAPM needs the market portfolio, not a sector index | Confirmed (Kyan's choice; analyst review 2026-11-04: Blume is the standard correction for mean-reverting betas; the raw 2.2 reflects 2021–2026 volatility; the price-implied WACC of 12.0% is shown beside it, so the choice is visible, not hidden) | 2026-11-04 |
| S6-D2 (D16) | WACC = CAPM cost of equity (rf = 10-year Treasury at the cutoff 4.91%, ERP 5%, S4-D5) and the Base-case year-1 pre-tax cost of debt and tax rate from the model, weighted by market capitalisation and book debt at the cutoff (Step 3 `v_valuation_cutoff`). One WACC for all three scenarios and all five years. NVIDIA 13.87% | Confirmed (Kyan's choice; review: debt is under 1% of capital, so WACC is in effect the cost of equity; book debt is acceptable at this weight) | 2026-11-04 |
| S6-D3 (D16) | Terminal value = perpetuity growth on year-5 unlevered FCF, g = 3%, valued at the end of year 5. Exit-multiple cross-check: peer median LTM EV/EBITDA at the cutoff, excluding the company itself and AMD (fiscal-year EBITDA basis, S3-D11), on year-5 EBITDA; shown with the EV/EBITDA the perpetuity implies, never blended into the headline | Confirmed (Kyan's choice; review: 3% is close to long-run nominal GDP; the exit multiple stays a cross-check because today's 26× peer multiple embeds growth after year 5 and would double-count it) | 2026-11-04 |
| S6-D4 (D16) | Probability-weighted value = 25% Bear + 50% Base + 25% Bull | Confirmed (Kyan's choice; review: symmetric weights fit a base case anchored to consensus; Bear and Bull are not equally far from Base, so the weighted value sits below Base) | 2026-11-04 |
| S6-D5 | Equity bridge: EV + cash and equivalents + short-term investments (debt securities) − total debt (latest balance sheet in `v_valuation_cutoff`) + listed equity stakes at fair value (NVIDIA: marketable equity securities 42,783 at 26 Jul 2026, Q2 FY2027 10-Q, accession 0001045810-26-000075). Resolves I-44 and I-53; the 4,957 of publicly held equity in other assets and non-marketable investments are excluded (not in the balance-sheet line, not separately valued). Leases are not deducted (I-41) | Confirmed (Kyan's choice; review 2026-11-04: the 4,957 of locked-up listed shares and the 51,157 of non-marketable securities stay out: one cannot be sold before December 2027, the other is carried at adjusted cost, not market value. Including both would add about $2.31 per share, Base 168.42 to 170.73; immaterial to the conclusion, recorded in I-63) | 2026-11-04 |
| S6-D6 | Cash flows: unlevered FCF = EBIT × (1 − model tax rate) + D&A − capex − (increase in receivables + inventory − payables), from the Step 5 forecast; SBC is a cost and not added back (D6). Valuation date = Step 2 cutoff 2026-11-02. Year 1 counts only the part after the latest balance sheet: share = 1 − revenue already reported in year 1 up to that date ÷ year-1 forecast revenue (NVIDIA 56.8%), because cash generated before that date is already in the balance sheet. Mid-year discounting: year-1 cash flow at the middle of its remaining part (not before the valuation date), later years at t₁ + k − 0.5 where t₁ = years from the valuation date to the end of year 1 (end of year 1 approximated as the latest fiscal year-end + 365 days). Diluted shares = latest quarter's weighted-average diluted count | Confirmed (review: stub and mid-year timing avoid counting H1 cash twice; the 53-week FY2027 shifts timing by 6 days, about 0.2% of value, I-62) | 2026-11-04 |
| S6-D7 | Peer DCFs use the mechanical Step 5 cases (S5-D6) and the same method; they are a cross-check, not a view. A peer is flagged when its year-1 tax rate is outside 0–35% or its value is negative (INTC, QCOM, I-58) | Confirmed (review: flagging rather than normalising keeps peer assumptions unchanged; peers are a cross-check, I-58) | 2026-11-04 |
| S6-D8 | Sensitivities: WACC 10–16% × g 2–4% (live formulas in the workbook) and FY2028 Data Center growth ±30pt × gross margin −4pt to +2pt in every year (Python, static in the workbook). Reverse DCF on the Base case, one lever at a time: FY2028 Data Center growth, WACC, terminal growth at which value = price | Confirmed | 2026-11-04 |
| S6-D9 | The workbook gains WACC, DCF and DcfData tabs (`python/build_dcf.py`), rebuilt by both `run_step5.py model` and `run_step6.py` (I-59). Live formulas except the labelled static blocks (scenario values from Python, growth × margin grid, reverse DCF). The DCF tab shows OK when its live value equals Python's for the selected scenario | Confirmed | 2026-11-04 |
| S6-D10 | Checks: D1 g < WACC for every company; D2 weights sum to 1; D3 unlevered FCF recomputed from the cash-flow statement (FCF − SBC − after-tax net interest) equals the DCF's; D4 weighted value within Bear–Bull; X3 the workbook's WACC, DCF rows and valuation cells, recalculated by LibreOffice, equal Python in all 18 cases, and the NVIDIA Base WACC × g grid matches (relative 1e-6); MANUAL in Excel where LibreOffice is not installed | Confirmed (Kyan's run 2026-11-04: D1–D4 pass, outputs reproducible, references tie; X3 is Kyan's Excel check in m6_acceptance) | 2026-11-04 |

## Step 7 / M7 decisions (comparable companies)

Decided 2026-11-04 by Claude acting as senior equity analyst, at Kyan's request ("make the decisions based on your
knowledge in the role"); the reasons are in each row. Settings in `config/comps.yaml`. Confirmed 2026-11-04 after Kyan's
run of `m7_check.py` (all automated items PASS; inputs tie upstream; NTM EPS agrees with the second source).

| ID | Decision | Status | Date |
|---|---|---|---|
| S7-D1 | Headline multiples: NTM P/E and NTM EV/EBITDA; the comps value is the mean of NVIDIA's value at the peer median of the two. Shown but not in the headline: NTM EV/revenue (NVIDIA's 75% gross margin is 6–35 points above every peer, so a revenue multiple understates what each dollar of its revenue earns) and the LTM multiples (with NTM growth near 100%, trailing multiples overstate how expensive the fast growers are) | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D2 | NTM = w × current fiscal year (consensus 0y) + (1 − w) × next fiscal year (+1y), w = share of the current fiscal year still to come at the valuation date (days ÷ 365.25, capped 0–1; fiscal year-end from Step 6). This puts January, September, November and December year-ends on the same twelve months (Nov 2026–Oct 2027). NVIDIA w = 0.23; AVGO and QCOM 0 (their fiscal years end on or before the cutoff). The 53-week FY2027 caveat (I-62) applies | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D3 | A peer's multiple leaves the statistics, but stays visible, when it is above 100× (earnings too small to mean anything), its denominator is zero or negative, or its EBITDA is a fiscal-year stand-in (AMD, S3-D11). NVIDIA is never in its own statistics. Result: AMD out of both EBITDA multiples and of LTM P/E (120×); INTC out of LTM P/E (loss). INTC and QCOM stay in the NTM multiples: those use consensus EPS and revenue, not the model's history-derived tax rates, so the I-58 distortion does not reach them | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D4 | NTM EBITDA = NTM consensus revenue × the company's own LTM EBITDA margin, labelled derived: the consensus snapshot (Step 4) has no EBITDA. The same rule applies to NVIDIA, so it is conservative for NVIDIA if its margin keeps rising | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D5 | Earnings basis: NTM P/E uses consensus (provider-adjusted) EPS for every company; LTM P/E uses GAAP net income ÷ diluted shares for every company. The two bases are never mixed within one multiple. Caveat I-50: providers' adjusted-EPS levels differ by 10–27% for AVGO and QCOM | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D6 (D16) | Blend for the value Step 9 turns into a 12-month target: 50% probability-weighted DCF (Step 6) + 50% comps value. Equal weights because the two methods err in opposite directions: the DCF values every company below its price (I-60), while comps assume the peers' pricing is right. Neither is given precedence over the other | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D7 | Statistics: minimum, 25th, median, 75th, maximum (inclusive percentiles, Excel PERCENTILE = pandas linear). Football field: 52-week closing range (marker = price), DCF Bear–Bull (marker Base), DCF WACC 12–15% × g 2.5–3.5% (Step 6 grid), and peer 25th–75th for NTM P/E, NTM EV/EBITDA, NTM EV/revenue and LTM EV/EBITDA (marker = median) | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D8 | EV = market cap (cover-page shares × cutoff price, Step 3) + debt − cash − short-term investments − listed equity stakes (NVIDIA only, S6-D5). NVIDIA's value per share at an EV multiple goes through the Step 6 bridge (+ cash, short-term investments, stakes − debt, ÷ diluted shares); at a P/E it is multiple × NVIDIA's NTM EPS | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |
| S7-D9 | Workbook: Comps and CompsData tabs (`python/build_comps.py`), always on NVIDIA, live formulas for every multiple, statistic, implied value, the growth regression and the blend; football-field and growth-vs-multiple charts. Built by every workbook build (I-64). Check X4: LibreOffice recalculation equals Python for 147 values (relative 1e-6); MANUAL in Excel without LibreOffice. The growth regression (5 peers) is shown as indicative, not used in the blend | Confirmed (analyst review delegated by Kyan) | 2026-11-04 |

## Step 9 / M9 decisions (investment memo)

Decided 2026-11-09 by Claude acting as senior equity analyst, at Kyan's request; reasons in each row. Confirmed
2026-11-14 after Kyan's run of `m9_check.py` (all automated items PASS; memo current and reproducible). Settings in
`config/memo.yaml`; memo text in `docs/memo/memo_template.md`, numbers from `python/step9_memo.py`.

| ID | Decision | Status | Date |
|---|---|---|---|
| S9-D1 | 12-month target = 50% × DCF + 50% × comps (S7-D6), where the DCF half is the probability-weighted value rolled forward 12 months at the cost of equity less the dividend yield (157.47 × (1 + 13.95% − 0.02%) = 179.39), and the comps half stays as computed because it already uses NTM figures (338.80). Rounded to the nearest $5: 259.10 → **$260**. Rolling the comps half forward as well would need consensus one year further out, which the snapshot does not have | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D2 | Rating from the 12-month expected total return (target ÷ price − 1 + dividend yield): Buy above +15%, Sell below −10%, Hold between. NVIDIA +28.7% → **Buy** | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D3 | The memo states plainly that the rating rests on relative value: the DCF alone is −22% (weighted) and supports the price only at a 12.05% WACC; comps alone are +68%. The variant view is that the market's discount on NVIDIA's earnings durability (14.0× NTM P/E, lowest of six) is too wide, but not wrong by the full gap to peers | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D4 | Every number in the memo is computed by `step9_memo.py` from Step 3–7 outputs and listed with its source in `memo_numbers.csv`; every comparative word ("highest of the six", "lowest of the six", "opposite directions") is checked against the data before rendering (M1), so new data cannot leave a false claim in the text | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D5 | Catalysts list only dates the company has announced (Q3 FY2027 results 17 Nov 2026; Vera Rubin shipments from fall 2026), each with its source URL; later events are marked "expected" | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D6 | Memo dated 9 Nov 2026 but priced at the 2 Nov 2026 cutoff; nothing after the cutoff enters the numbers. The Q3 FY2027 results on 17 Nov are the first update (I-54, I-69) | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
| S9-D7 | `excel/NVDA_Simple_DCF.xlsx` (Kyan's request, 2026-11-04) joins the project with its generator `python/build_simple_dcf.py`: a Base-case-only workbook styled after a free DCF template, built from the same outputs; its implied price equals the Step 6 Base value (168.42) | Confirmed (analyst review delegated by Kyan) | 2026-11-09 |
