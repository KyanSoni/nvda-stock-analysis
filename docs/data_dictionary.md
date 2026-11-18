# Data dictionary — M1 outputs (`data/clean/`)

All files are UTF-8 CSV with LF line endings, rows sorted on fixed keys, so identical input gives identical bytes.
Numbers are written exactly as SEC published them (no float rounding).

## sec_observations.csv — every SEC observation, unchanged
| Column | Meaning |
|---|---|
| snapshot_sha256 | SHA-256 of the raw companyfacts file this row came from |
| cik, entity_name | As stated in the snapshot |
| taxonomy, concept, unit | XBRL taxonomy (us-gaap, dei, …), concept name and unit as published |
| period_type | `duration` (has a start date) or `instant` |
| period_start, period_end | Dates as published (start blank for instants) |
| duration_days | period_end − period_start in days (blank for instants) |
| value | Value exactly as published, in the stated unit |
| accn, form, filed | Accession number, form type and filing date of the filing that reported it |
| sec_fy, sec_fp, frame | SEC's tags, kept as provenance. `sec_fy`/`sec_fp` describe the filing, not the period |

## nvda_facts_selected.csv — one value per line item, period and basis
| Column | Meaning |
|---|---|
| line_item, statement | Model line item (config) and IS / BS / CF |
| fiscal_year, fiscal_period | NVIDIA fiscal labels from dates: FY, Q1–Q4, 6M, 9M (FY2026 = Feb 2025–Jan 2026) |
| value_basis | `reported_annual`, `reported_quarter`, `reported_ytd`, `reported_instant`, or `derived_q4` |
| period_start, period_end, value, unit | The selected value and its period, as published (or as derived) |
| display_value, display_unit | USD and shares in millions (exact); per-share values unchanged |
| concept, accn, form, filed, sec_fy, sec_fp, frame | Provenance of the selected observation (blank for derived rows) |
| n_observations, n_distinct_values | How many observations exist for that concept and period, and how many distinct values |
| restated | True when the latest-filed value differs from the first-filed value |
| original_value, original_accn, original_filed | The first-filed observation, kept for audit |
| other_candidate_concepts | Lower-priority candidate concepts that also had a value for the period (not used) |
| derived_from_accns | For `derived_q4`: accessions of the annual and 9M inputs |
| transformation | What was done to the value (scaling, derivation) |

## gap_report.csv — expected values that do not exist
Window: the latest fiscal year with reported annual revenue, and the 9 years before it.
| Reason | Meaning |
|---|---|
| no_observation | Nothing reported for that period |
| only_ytd_reported | Only a year-to-date figure exists (typical for cash-flow items in 10-Qs) |
| not_derivable_by_subtraction | Q4 per-share and share-count values cannot be found by subtraction |
| derived_q4_inputs_missing: … | The annual or 9M value needed to derive Q4 is missing |

## anomalies.csv — suspected XBRL scale errors (check C11 / W1), reported only
| Column | Meaning |
|---|---|
| line_item, fiscal_year, fiscal_period, value_basis, period_end, value | The flagged selected row (value unchanged) |
| anomaly_type | `vs_first_filed` (latest vs first-filed value) or `vs_previous_period` (vs previous period, same basis) |
| compared_with, comparison_value, ratio | What it was compared with and the absolute ratio; flagged when outside 0.01–100 |
| in_target_window | True inside the 10-year window: C11 then fails the run. False: warning W1 only |
| accn, filed | Filing of the flagged value |

## Other files
- `concept_availability.csv`: for each candidate concept, observation count, units, date range and rows used.
- `validation_report.csv`: checks C1–C11 (level `error`, decide the exit code) and W1 (level `warning`, review only).
- `m1_check_report.txt`: the full M1 status report written by `python/m1_check.py`.
- `run_manifest.json`: snapshot file and hash, run time, Python/pandas versions, git commit, output hashes.
- `data/raw/sec/manifest.csv`: one row per live fetch (time, URL, status, bytes, hash, file).

# Step 2 outputs (`data/clean/step2/`)

Built only from one saved collection in `data/raw/collections/<id>/` (never edited). Same CSV conventions as M1.

| File | Contents |
|---|---|
| `identity_report.csv` | One row per registrant: CIK, role (current/predecessor), SEC name and former names, SEC fiscal year-end and the month it implies, first/last 10-K period, ticker-file CIK |
| `facts_selected.csv` | All companies. M1 columns plus `ticker`, `entity_cik`, `entity_role`, `support_item`. `value_basis` adds `derived_quarter` (Q2/Q3 from YTD) and `derived_component` (from support items) |
| `gap_report_all.csv`, `<TICKER>/gap_report.csv` | Missing values in each company's 10-year window, with reasons |
| `anomalies_all.csv`, `<TICKER>/anomalies.csv` | Scale anomalies (C11/W1) |
| `<TICKER>/sec_observations.csv` | Every SEC observation for the company and its predecessors, unchanged, with `entity_cik` |
| `validation_summary.csv` | Every check: `scope` (ticker, MARKET or ALL), `check`, `passed`, `detail`, `level` (error/warning) |
| `market/prices.csv` | Daily prices to the cutoff: open/high/low/close (split-adjusted), adj_close (split and dividend adjusted), volume, dividend, split_ratio, `close_as_traded`, source file and hash |
| `market/corporate_actions.csv` | Splits and dividends from the price files |
| `market/market_inputs.csv` | Per ticker at the cutoff: close, close_2dp, SEC cover-page shares (as-of date, accession, form), derived market cap, yfinance share cross-check; row `RISK_FREE_10Y` holds the 10-year yield (percent) and its observation date |
| `run_manifest.json` | Collection id, per-company summary, versions, git commit, output hashes |
| `m2_check_report.txt` | Full Step 2 status report from `python/m2_check.py` |

Checks added in Step 2: I1 identities and fiscal calendars; I2 files match the collection manifest; C10 snapshot hashes are collection files; C12 derived quarters recompute; C13 guarded fallbacks respected; C14 derived components recompute; C15/C16 vocabulary and unique keys on all rows; C17 rows come from configured registrants; C18 latest four quarters complete; P1 trading days match SPY; P2 prices consistent; P3 splits match SEC share counts; P4a cutoff bar for every symbol; P4b risk-free at cutoff; P5 shares with provenance; W2 yfinance shares within 5%.


# Step 3 outputs (`data/clean/step3/`)

Built from the signed-off Step 2 collection (id read from `data/clean/step2/run_manifest.json`). Step 2 rows are carried unchanged (C24).

| File | Contents |
|---|---|
| `facts_extended.csv` | Step 2 columns plus `split_factor`, `value_split_adjusted`, `display_split_adjusted` (EPS and diluted shares only), `source_url`, `location_in_filing` (manual facts only). `value_basis` adds `derived_sum`, `declared_zero`, `manual_from_filing` |
| `split_factors.csv` | Splits used for adjustment: ticker, date, ratio |
| `gap_report_step3.csv` | Missing values after the Step 3 derivations |
| `validation_step3.csv` | C1–C18 on the Step 2 rows, C18/W4 LTM, C19–C24, C15b/C16b, W3 coverage; `level` error/warning |
| `facts_manifest.json` | Collection id, Step 2 output hashes, per-company summary, output hashes |
| `load/*.csv` | Exactly what is loaded into PostgreSQL, in table column order |
| `db_checks.csv` | DB1 row counts vs load files; DB2/DB3 duplicate periods agree; DB4 ratios for every company; DB5 one cutoff; DB6 valuation for every company |
| `exports/<view>.csv` | Every view, ordered (see below) |
| `exports/q1…q3.csv` | The guide's three questions |
| `db_manifest.json` | Server version, psql version, load and export hashes, checks result |
| `m3_check_report.txt` | Full Step 3 status report from `python/m3_check.py` |

**Database** (PostgreSQL, schema `analytics`). Tables: `companies`, `line_items`, `facts`, `split_factors`, `prices`, `market_inputs`, `load_manifest`. Amounts in views are in **USD millions** (shares in millions; EPS in USD, split-adjusted); ratios are fractions (0.711 = 71.1%).

| View | One row per | Contents |
|---|---|---|
| `v_facts_used` | fact | Facts used in analysis (no support items, no YTD), with `amount` |
| `v_annual` | ticker, fiscal_year | Every line item: FY flows, Q4 balance-sheet values |
| `v_quarterly` | ticker, period_end | Every line item for fiscal quarters |
| `v_ltm` | ticker, period_end | Sums of the last 4 quarters (NULL unless 4 consecutive quarters spanning 250–300 days) and the balance sheet at that date |
| `v_ratios_annual` | ticker, fiscal_year | Growth, 5-year revenue CAGR, margins, ROE (+3/5-year averages), quick ratio, FCF, FCF conversion, net debt, EBITDA, net debt/EBITDA, effective and used tax rate, NOPAT, invested capital, ROIC, 5-year share change, 3-year NI CAGR |
| `v_ratios_ltm` | ticker, period_end | LTM revenue, growth, margins, net income, FCF, EBITDA, net debt |
| `v_valuation_cutoff` | company | Market cap, latest complete LTM, latest balance sheet, EV, P/E, EV/revenue, EV/EBITDA (`ebitda_basis`), historical PEG, risk-free rate |
| `v_peer_summary` | company | Latest-year headline ratios and valuation |

Checks added in Step 3: C19 split-adjusted EPS × shares ≈ net income; C20 adjusted shares smooth; C21 derived sums recompute; C22 declared zeros only where configured; C23 manual facts valid; C24 Step 2 rows unchanged; W3 coverage; W4 LTM for new flows; DB1–DB6; V1 SQL equals Python recomputation.

# Step 4 outputs (`data/clean/step4/`)

Built from the Step 3 schema plus one consensus snapshot in `data/raw/estimates/<UTC id>/` (never edited; not in Git).

| File | Contents |
|---|---|
| `estimates.csv` | One row per company, kind (`eps`, `revenue`) and Yahoo period (`0q`, `+1q`, `0y`, `+1y`): avg, low, high, analysts, year-ago value, Yahoo's growth, fetch time, snapshot id, raw file and its SHA-256. Values as text, blank when Yahoo gives none |
| `estimates_manifest.json` | Snapshot id and info, cutoff, output hash, checks E1 (files valid, `0y` and `+1y` EPS for every company) and E2 (fetched within 7 days of the cutoff) |
| `load/*.csv` | `scorecard_rules`, `scorecard_params`, `estimates` exactly as loaded |
| `db_checks_step4.csv` | SC1 ten tests per company; SC2 points 0–2 and totals add up; SC3 full 60-month beta window; SC4 consensus EPS for every company; SC5 WACC for every company |
| `exports/v_beta.csv` | Per company and benchmark (SPY, SOXX): beta, correlation, months, first and last month |
| `exports/v_wacc.csv` | Risk-free, beta (SPY), ERP, cost of equity, interest, debt, pre-tax cost of debt, tax rate, market cap, debt weight, provisional WACC |
| `exports/v_peg.csv` | Trailing P/E, consensus EPS `0y` and `+1y`, analysts, forward EPS growth, forward PEG |
| `exports/v_scorecard_detail.csv` | One row per company and test: metric value, thresholds, points, result (pass / near miss / fail / not scored), reason |
| `exports/v_scorecard.csv` | One row per company: points per test (blank = not scored), total, maximum possible, tests scored |
| `db_manifest_step4.json` | Load and export hashes, checks result |
| `m4_check_report.txt` | Full Step 4 status report from `python/m4_check.py` |

Database additions (schema `analytics`): tables `scorecard_rules`, `scorecard_params`, `estimates`; views `v_latest_annual`, `v_beta`, `v_wacc`, `v_peg`, `v_scorecard_metrics`, `v_scorecard_detail`, `v_scorecard`. Rebuilding Step 3 (`run_step3.py db`) drops them; rerun `run_step4.py db` afterwards.

# Step 5 outputs (`data/clean/step5/`, `excel/NVDA_Forecast.xlsx`)

| File | Contents |
|---|---|
| `facts_model.csv` | Every selected value for the Step 5 line items (M1 columns + provenance; NVIDIA Data Center rows are `manual_from_filing`) |
| `model_data.csv` | One row per company, line item and fiscal year (latest 5): `value_m` in USD millions (EPS USD, shares millions) and `source` (Step 3 view, concept + accession, manual accession, or derived) |
| `validation_step5.csv` | F1 manual facts valid; F2 model history complete (NVIDIA error, peers warning); F3 gross-profit identity (NVIDIA) |
| `assumptions.csv` | One row per company, driver and scenario: Y1–Y5, reason, source (`config/model.yaml` for NVIDIA, generated for peers) |
| `forecast.csv` | The Python model's output: every forecast row, Y1–Y5, for each company and scenario (what the workbook is checked against) |
| `manifest_<stage>.json` | Output hashes and check results |
| `m5_check_report.txt` | Full Step 5 status report from `python/m5_check.py` |

**Workbook** (`excel/NVDA_Forecast.xlsx`, rebuilt by `run_step5.py model`): Cover (Ticker `C5`, Scenario `C6` 1 Bear / 2 Base / 3 Bull, key outputs, consensus, balance check) · Assumptions (per driver: Bear, Base, Bull, Selected = CHOOSE(Scenario,…), reason) · Historicals (latest 5 fiscal years, derived lines, history drivers) · IS · BS (balance check row) · CF · Schedules (working capital, PP&E, debt, equity, shares, cash) · Data and AssumptionsData (inputs, blue; regenerated). Units USD millions; rates as fractions shown as %.

Forecast equations (each year t; "opening" = year t−1): segment A/B = opening × (1 + growth); revenue = A + B; cost of revenue = revenue × (1 − gross margin); R&D, SG&A, other opex = revenue × %; EBIT = gross profit − opex; interest income = yield × opening cash and investments; interest expense = rate × opening debt; tax = pre-tax × rate; receivables = revenue × DSO/365; inventory and payables = cost of revenue × DIO or DPO/365; PP&E = opening + capex − D&A; equity = opening + net income + SBC − buybacks − dividends; buybacks = max(FCF, 0) × %; dividends = max(net income, 0) × payout; cash = opening + FCF − buybacks − dividends + net debt issuance. Checks added in Step 5: F1–F3, X1 (workbook = Python model), X2 (balance in every year).

# Step 6 outputs (`data/clean/step6/`, DCF tabs in `excel/NVDA_Forecast.xlsx`)

Written by `python/run_step6.py` from the Step 5 outputs, Step 3 `v_valuation_cutoff.csv` and `facts_extended.csv`,
Step 4 `exports/v_beta.csv` and `config/dcf.yaml`. Rates are fractions, amounts USD millions, per-share values USD.

| File | Contents |
|---|---|
| `dcf_inputs.csv` | One row per company: valuation date, price, market cap, balance-sheet date, cash, short-term investments, debt, listed stakes (+ source), diluted shares (+ period end), latest fiscal year-end, approximate end of year 1, `t_first` (years from valuation date to end of year 1), year-1 revenue already reported, `stub_fraction` (share of year 1 still to come), raw and adjusted beta, Blume weights, rf, ERP, cost of equity, cost of debt, tax rate, debt weight, WACC, terminal growth, exit multiple, scenario weights |
| `dcf_values.csv` | One row per company: for Bear / Base / Bull: EV, equity value, value per share, upside, terminal-value share of EV, implied exit EV/EBITDA, value per share at the peer multiple; weighted value per share and upside; `quality_flag` (S6-D7) |
| `dcf_detail.csv` | Per company × scenario × row (nopat, ufcf, fraction, counted, t, df, pv): the five forecast years |
| `sensitivity_wacc_g.csv` | NVIDIA Base value per share: WACC (rows) × terminal growth (columns) |
| `sensitivity_growth_margin.csv` | NVIDIA Base value per share: FY2028 Data Center growth (rows) × gross-margin shift in every year (columns) |
| `reverse_dcf.csv` | NVIDIA Base: lever, model value, implied value at which value per share = price, status, note |
| `manifest_step6.json` | Run time, output hashes, checks D1–D5 (and X3 with `--excel-check`) |
| `m6_check_report.txt` | Full Step 6 status report from `python/m6_check.py` |

**Workbook tabs** (added by `python/build_dcf.py`): WACC (beta, Blume adjustment, CAPM, cost of debt, weights; selected ticker) ·
DCF (rows H–L: EBIT, tax rate, NOPAT, D&A, capex, working-capital increase, unlevered FCF, share counted, t, discount factor, PV;
column C: valuation summary, equity bridge, value per share, exit-multiple check, Python scenario values and the OK check, live
WACC × g grid; static growth × margin grid and reverse DCF for NVIDIA Base) · DcfData (inputs, blue; written by the script).

# Step 7 outputs (`data/clean/step7/`, Comps tabs in `excel/NVDA_Forecast.xlsx`)

Written by `python/run_step7.py` from Step 3 `v_valuation_cutoff.csv` and `v_ratios_ltm.csv`, Step 4 `estimates.csv`,
the Step 6 DCF (recomputed in the same run), Step 2 `prices.csv` and `config/comps.yaml`. Floats with 6 decimals; multiples
are plain ratios (14.036 = 14.0×); "n/m" in the workbook = blank here.

| File | Contents |
|---|---|
| `comps_table.csv` | One row per company: price, diluted shares, market cap, debt, cash, short-term investments, stakes, net debt, EV; current fiscal year-end and NTM weight `w_fy0`; revenue FY0 / FY1 / NTM / LTM, NTM and LTM growth, LTM gross margin; LTM EBITDA, margin, NTM EBITDA; EPS FY0 / FY1 / NTM (consensus) and LTM (GAAP); 52-week low and high; the six multiples and `use_<multiple>` (1 = in the peer statistics) |
| `comps_stats.csv` | Per multiple: peers used, n, min, p25, p50, p75, max |
| `comps_implied.csv` | Per multiple: NVIDIA's metric and own multiple; NVIDIA value per share at each peer statistic |
| `comps_regression.csv` | Peers' NTM EV/revenue on NTM growth: slope, intercept, R², NVIDIA's growth, actual and fitted multiple, value per share on the line |
| `football_field.csv` | Method, low, high, marker, note |
| `comps_blend.csv` | DCF weighted value, comps value, weights, blended value, price, upside |
| `manifest_step7.json` | Run time, output hashes, checks C1–C6 (and X4 with `--excel-check`) |
| `m7_check_report.txt` | Full Step 7 status report from `python/m7_check.py` |

**Workbook tabs** (`python/build_comps.py`): Comps (company table with live multiples, in-statistics flags and statistic helper
columns; peer statistics; NVIDIA implied values; growth regression; blend; football-field table and chart; growth-vs-multiple
scatter) · CompsData (inputs, blue; written by the script).

# Step 9 outputs (investment memo)

Written by `python/run_step9.py` from `docs/memo/memo_template.md`, `config/memo.yaml`, `config/comps.yaml` and the Step 4–7 outputs.

| File | Contents |
|---|---|
| `docs/memo/NVDA_investment_memo.md` | The memo (page 1 text, page 2 exhibits), rendered; committed |
| `docs/memo/exhibits/football_field.svg` | Exhibit 1: range bars per method, markers, price (dashed red) and target (blue) lines; committed |
| `docs/memo/NVDA_investment_memo.pdf` | Two-page A4 render of the memo (I-68); committed |
| `data/clean/step9/memo_numbers.csv` | name, value, source: every number the memo quotes (6 decimals) and the file and column it came from |
| `data/clean/step9/manifest_step9.json` | Run time, output hashes, checks M1–M6 |
| `data/clean/step9/m9_check_report.txt` | Full Step 9 status report from `python/m9_check.py` |
| `excel/NVDA_Simple_DCF.xlsx` | Base-case workbook in a simple template layout (Company Comparison, Statements Model, DCF), from `python/build_simple_dcf.py` (S9-D7) |

# Version 2, V2.1 outputs (`data/clean/v2/universe/`)

Written by `python/run_v2_universe.py` from a `fetch_v2_universe.py` collection in `data/raw/v2/universe/<id>/` (Wikipedia
pages "List of S&P 500 companies" and "Historical components of the S&P 500" as HTML, SEC `company_tickers.json`, SEC
`cik-lookup-data.txt`, with `collection_manifest.csv` and `collection_info.json`).

| File | Contents |
|---|---|
| `constituents_current.csv` | ticker, security, sector (GICS), sub_industry, date_added, cik (10 digits), as on the collection date |
| `changes.csv` | date (effective), added_ticker, added_security, removed_ticker, removed_security, reason; combined from every table on either page whose headings say date / added / removed (I-75) |
| `ticker_changes.csv` | old_ticker, old_security, ticker (the member's ticker now), security, added_date, basis (date_added, same_name, shared_cik), cik: tickers changed after joining, linked on evidence (I-76) |
| `membership.csv` | date (each 1 April and 1 July 2016–2026 that has passed, plus the collection date; July dates for the V2.7 robustness test), ticker, security, cik (V2.1 mapping), cik_basis, sector (today's members only; V2.2 adds the rest), excluded_sector |
| `ciks.csv` | every company ever in the universe since 2016: ticker, security, cik, cik_basis (wikipedia; sec_ticker, only where SEC's names agree; sec_name; sec_name_shared, a renamed company's CIK listed under both names; unmapped), in_current |
| `coverage.csv` | per date: members, with_cik, from_current (members with a known sector), cik_coverage |
| `warnings.txt` | contradictions met while undoing changes (U7) |
| `manifest_v2_universe.json` | collection used, output hashes, checks U1–U8 |

# Version 2, V2.2–V2.8 outputs

Bulk downloads live outside OneDrive in the folder named by `NVDA_V2_DATA`, else `%LOCALAPPDATA%\nvda-data\v2` (V2-D7):
`sec\submissions\CIK##########.json.gz` (and older pages), `sec\companyfacts\CIK##########.json.gz`, `sec\manifest.csv`
(every request: URL, status, bytes, SHA-256 of the bytes received), `sec\candidates.json` (name-matched filers tried per
ticker), `facts\facts_v2.csv.gz`, `prices\<collection>\prices_<TICKER>.csv` with `collection_manifest.csv`, and
`prices\prices_v2.csv.gz`. Files are stored gzip-compressed exactly as received.

| File (`data/clean/v2/…`) | Contents |
|---|---|
| `sec/cik_by_date.csv` | date, ticker, security, cik_pit (the filer at that date), pit_basis (v21_cik_annual_report; edgar_name_annual_report; no_annual_report_in_window; ambiguous; unresolved), edgar_name, sic, sector, sector_basis (wikipedia_gics or "sic NNNN"), excluded_sector, cik_v21, cik_basis_v21, n_qualifying, note (V2-D9 to V2-D11) |
| `sec/unresolved.csv` | the rows of cik_by_date without a usable filer |
| `sec/sic_check.csv` | current members: GICS sector vs the SIC-mapped sector (check S4) |
| `sec/coverage_sec.csv` | per date: members, resolved, with_sector, resolved_share |
| `facts/concept_coverage.csv` | per line item: companies with any value, share, companies per concept (F3) |
| `facts/v1_fact_check.csv` | ticker, line_item, concept, period_end, v1_value, v2_value, agree, note: Version 1's annual values vs V2's extraction (F4) |
| `prices/price_coverage.csv` | per date: trade_date, members_resolved (outside excluded sectors), with_price, ticker_reused, price_share (P2) |
| `prices/price_flags.csv` | ticker, security, cik_pit, issue (history not used; large daily move), detail |
| `scores/scores_by_date.csv` | one row per company per date: date, trade_date, ticker, security, cik, sector, sector_basis, price_as_traded, price_note, fy0_end, fy0_filed, fy0_accn, stale, revenue, revenue_cagr_5y, gross_margin, sector_gm_median, gross_margin_vs_sector, roe, roe_5y_avg, quick_ratio, net_income, fcf_conversion, net_debt_to_ebitda, roic, operating_income, ebitda, shares_change_5y, pe_fy, fail_reasons, flags, other_classes, t1–t10 (points per test; blank = not scored; no t3, PEG dropped), points (scored tests only), tests_scored, max_points, imputed_points (sector-median points for unscored tests), score_total (points + imputed, of 18), score_pct (score_total / 18), ranked, why_not_ranked, rank (V2-D12 to V2-D14) |
| `scores/screener_today.csv` | the same columns for the latest date (the live screen) |
| `scores/v1_reconcile.csv` | ticker, fy_end, metric, v1, v2, diff, agree, note: the six companies, V2 engine vs Version 1 ratios (C2) |
| `backtest/nav_daily.csv` | date, strategy (top 30, net of costs), universe_ew, spy: value of $1 |
| `backtest/periods.csv` | start, end, holdings, turnover, cost, return (net), ended_early, universe_ew, spy, excess_vs_spy, excess_vs_universe |
| `backtest/holdings.csv` | trade_date, period_end, rank, ticker, security, sector, score_total, tests_scored, roic, return over the period, prices_end_early |
| `backtest/stats.csv` | per series: start, end, years, total_return, cagr, volatility, sharpe (rf 0), max_drawdown, tracking_error and information_ratio vs SPY |
| `backtest/robustness.csv` | variant, cagr, volatility, sharpe, max_drawdown, information_ratio, vs_spy_cagr, note (V2.7) |
| `backtest/random_cagrs.csv` | CAGR of each random 30-stock portfolio |
| `manifest_v2_*.json` | per phase: inputs, output hashes, checks with level |

Deliverables (committed): `excel/SP500_Screener.xlsx` (Read me, Screener, Backtest, Holdings, Robustness, Data quality),
`docs/v2/v2_results.md`, `docs/v2/exhibits/v2_growth.svg`, all written by `python/run_v2_report.py` (checks R1–R4).
