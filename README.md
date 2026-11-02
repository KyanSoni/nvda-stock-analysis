# NVIDIA Stock Analysis

Does NVIDIA's competitive position in AI computing justify the future cash flows implied by its current
business performance and long-term growth expectations?

This repository builds the answer in tested stages. **Current stage: M1** — retrieve NVIDIA's SEC
companyfacts, keep every observation with full provenance, select one value per line item and period
under documented rules, report gaps, and validate the result.

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
```

## Layout
| Path | Contents |
|---|---|
| `config/project.yaml` | Company, SEC settings, the 12 line items and their candidate XBRL concepts |
| `python/` | `fetch_sec.py`, `parse_companyfacts.py`, `select_facts.py`, `validate_m1.py`, `run_m1.py`, `m1_check.py` |
| `tests/` | Offline unit, contract and reproducibility tests; live and reconciliation tests on request |
| `data/raw/sec/` | Saved companyfacts snapshots and fetch manifest (not in Git) |
| `data/clean/` | Pipeline outputs (not in Git) |
| `docs/` | Decision log, issue log, M1 acceptance checklist, data dictionary |

## Peers and benchmarks (later milestones)
Peers: AMD, AVGO, MRVL, QCOM, INTC. Benchmarks: SPY, SOXX.
