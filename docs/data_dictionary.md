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
