# NVIDIA Stock Analysis

Does NVIDIA's competitive position in AI computing justify the future cash flows implied by its current
business performance and long-term growth expectations?

This repository builds the answer in tested stages.
- **M1 (signed off):** NVIDIA's SEC companyfacts with full provenance, documented selection rules, gaps and validation.
- **Step 2 / M2:** the same for peers AMD, AVGO, MRVL, QCOM and INTC (including predecessor registrants), plus daily
  prices, corporate actions, shares outstanding and the 10-year Treasury yield at one cutoff date.

## Setup (Windows, PowerShell)
Python 3.14.8 with a project venv outside OneDrive:
```powershell
$vpy = "$env:LOCALAPPDATA\venvs\nvda-stock-analysis\Scripts\python.exe"
& $vpy -m pip install -r requirements.txt
```

## Run
From the project folder:
```powershell
& $vpy -m pytest                                  # offline tests (synthetic snapshot, no network)
$env:SEC_USER_AGENT = "Your Name your-email@example.com"
& $vpy python\run_m1.py --source live             # fetch a new snapshot and process it
& $vpy python\run_m1.py --source snapshot         # reprocess the latest saved snapshot, offline
& $vpy -m pytest -m live                          # live SEC retrieval test
& $vpy -m pytest -m reconciliation                # compare output with tests\fixtures\reference_values.csv
& $vpy python\m1_check.py                         # every M1 check in one go -> data\clean\m1_check_report.txt

# Step 2
& $vpy python\fetch_step2.py                      # download everything into data\raw\collections\<id> (needs SEC_USER_AGENT)
& $vpy python\fetch_step2.py --add-rates <id>     # add the 10-year yield if FRED timed out
& $vpy python\run_step2.py                        # process the latest collection offline -> data\clean\step2
& $vpy python\m2_check.py                         # every Step 2 check in one go -> data\clean\step2\m2_check_report.txt

# Step 3 (PostgreSQL 13+; password only in the session, never in a file)
$env:PGPASSWORD = "<postgres password>"
& $vpy python\run_step3.py all                    # facts + database + exports -> data\clean\step3
& $vpy -m pytest -m db                            # database tests (rebuild the analytics schema)
& $vpy python\m3_check.py                         # every Step 3 check in one go -> data\clean\step3\m3_check_report.txt

# Step 4 (needs Step 3 built in the same database)
& $vpy python\fetch_step4.py                      # snapshot consensus estimates -> data\raw\estimates\<id> (network)
& $vpy python\run_step4.py all                    # estimates + beta, WACC, PEG and scorecard views -> data\clean\step4
& $vpy python\m4_check.py                         # every Step 4 check -> data\clean\step4\m4_check_report.txt

# Step 5 (offline; reads the Step 3 and Step 4 outputs)
& $vpy python\run_step5.py all                    # model line items, assumptions, forecast -> excel\NVDA_Forecast.xlsx
& $vpy python\m5_check.py                         # every Step 5 check -> data\clean\step5\m5_check_report.txt

# Step 6 (offline; reads the Step 3, 4 and 5 outputs)
& $vpy python\run_step6.py                        # DCF, sensitivities, reverse DCF -> data\clean\step6, WACC/DCF tabs in the workbook
& $vpy python\m6_check.py                         # every Step 6 check -> data\clean\step6\m6_check_report.txt

# Step 7 (offline; reads the Step 2-6 outputs)
& $vpy python\run_step7.py                        # comps, football field, DCF/comps blend -> data\clean\step7, Comps tab in the workbook
& $vpy python\m7_check.py                         # every Step 7 check -> data\clean\step7\m7_check_report.txt
```
Change a forecast assumption in `config\model.yaml`, then `run_step5.py model`; edits made in the workbook itself are overwritten.

## Layout
| Path | Contents |
|---|---|
| `config/project.yaml` | Company, SEC settings, the 12 line items and their candidate XBRL concepts |
| `config/universe.yaml` | Step 2 companies, predecessors, fallbacks, derivations, market settings |
| `config/step5.yaml`, `config/manual_facts_step5.csv`, `config/model.yaml` | Step 5 model line items, NVIDIA Data Center revenue (manual from 10-K), forecast assumptions with reasons |
| `config/dcf.yaml` | Step 6 DCF settings: Blume beta, ERP, terminal growth, scenario weights, NVIDIA's listed equity stakes, sensitivity grids |
| `config/comps.yaml` | Step 7 comps settings: headline multiples, NTM calendarisation, exclusion rules, DCF/comps blend |
| `config/scorecard.yaml` | Step 4 tests and thresholds, estimates source, WACC assumptions |
| `config/step3.yaml`, `config/manual_facts.csv`, `config/database.yaml` | Step 3 line items and derivations, manual facts (empty), PostgreSQL connection (no password) |
| `sql/` | `schema.sql`, `views.sql`, `checks.sql`, `queries/` |
| `python/` | M1: `fetch_sec.py`, `parse_companyfacts.py`, `select_facts.py`, `validate_m1.py`, `run_m1.py`, `m1_check.py`; Step 2: `fetch_step2.py`, `step2_sec.py`, `step2_market.py`, `run_step2.py`, `m2_check.py`; Step 3: `step3_facts.py`, `run_step3.py`, `step3_db.py`, `step3_reference.py`, `m3_check.py`; Step 4: `fetch_step4.py`, `step4_estimates.py`, `step4_db.py`, `step4_reference.py`, `run_step4.py`, `m4_check.py`; Step 5: `step5_facts.py`, `step5_model.py`, `build_model.py`, `step5_check.py`, `run_step5.py`, `m5_check.py`; Step 6: `step6_dcf.py`, `build_dcf.py`, `step6_check.py`, `run_step6.py`, `m6_check.py`; Step 7: `step7_comps.py`, `build_comps.py`, `step7_check.py`, `run_step7.py`, `m7_check.py` |
| `tests/` | Offline unit, contract and reproducibility tests; live and reconciliation tests on request |
| `data/raw/sec/` | M1 companyfacts snapshots and fetch manifest (not in Git) |
| `data/raw/collections/` | Step 2 collections, one dated folder per download run (not in Git) |
| `data/clean/` | Pipeline outputs (not in Git) |
| `excel/` | `NVDA_Model.xlsx` (Scorecard, Power Query), `NVDA_Forecast.xlsx` (3-statement model, DCF and comps, generated) |
| `docs/` | Decision log, issue log, M1–M7 acceptance checklists, data dictionary, evidence |

## Universe
Target NVDA. Peers AMD, AVGO, MRVL, QCOM, INTC. Benchmarks SPY, SOXX.
