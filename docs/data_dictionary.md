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
