"""M1 pipeline: SEC companyfacts -> observations -> selected NVIDIA facts -> gap report -> validation.

Usage (from the project folder, with the venv's python):
  python python/run_m1.py --source live                 # fetch a new snapshot, then process it
  python python/run_m1.py --source snapshot             # reprocess the latest saved snapshot, no network
  python python/run_m1.py --source snapshot --snapshot data/raw/sec/<file>.json
Exit code 0 = all error-level checks passed; 1 = at least one failed (see validation_report.csv).
Warning-level checks (W*) are listed for review but never change the exit code.
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from common import DEFAULT_CONFIG, PROJECT_ROOT, load_config, sha256_file, write_csv
from fetch_sec import fetch_companyfacts, latest_snapshot
from parse_companyfacts import load_snapshot, parse_observations
from select_facts import (SELECTED_KEY, concept_availability, gap_report, select_line_items)
from validate_m1 import find_scale_anomalies, run_checks, scale_checks

OUTPUT_FILES = {
    "observations": "sec_observations.csv",
    "selected": "nvda_facts_selected.csv",
    "gaps": "gap_report.csv",
    "availability": "concept_availability.csv",
    "validation": "validation_report.csv",
    "anomalies": "anomalies.csv",
}


def count_observations(facts_json: dict) -> int:
    """Independent count of observations straight from the JSON, used by check C1."""
    return sum(len(obs) for concepts in facts_json.get("facts", {}).values()
               for body in concepts.values() for obs in body.get("units", {}).values())


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "no commit yet"
    except (OSError, subprocess.SubprocessError):
        return "git unavailable"


def process_snapshot(snapshot: Path, cfg: dict, out_dir: Path) -> tuple[list, dict]:
    """Returns (checks, summary). checks = [(check_id, passed, detail, level)], level 'error' or 'warning'."""
    facts_json, sha = load_snapshot(snapshot)
    obs = parse_observations(facts_json, sha)
    selected = select_line_items(obs, cfg)
    gaps, latest_fy = gap_report(selected, cfg)
    availability = concept_availability(obs, selected, cfg)
    anomalies = find_scale_anomalies(selected, cfg, latest_fy)
    c11, w1 = scale_checks(anomalies)
    errors = run_checks(obs, selected, cfg, count_observations(facts_json)) + [c11]
    checks = [(c, p, d, "error") for c, p, d in errors] + [(*w1, "warning")]
    validation = pd.DataFrame(checks, columns=["check", "passed", "detail", "level"], dtype=object)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(obs, out_dir / OUTPUT_FILES["observations"],
              ["taxonomy", "concept", "unit", "period_end", "period_start", "filed", "accn", "form", "frame", "value"])
    write_csv(selected, out_dir / OUTPUT_FILES["selected"], SELECTED_KEY)
    write_csv(gaps, out_dir / OUTPUT_FILES["gaps"], ["line_item", "fiscal_year", "fiscal_period"])
    write_csv(availability, out_dir / OUTPUT_FILES["availability"], ["line_item", "priority"])
    write_csv(validation, out_dir / OUTPUT_FILES["validation"], ["check"])
    write_csv(anomalies, out_dir / OUTPUT_FILES["anomalies"],
              ["line_item", "value_basis", "period_end", "anomaly_type", "fiscal_period"])

    summary = {
        "snapshot_file": snapshot.name,
        "snapshot_sha256": sha,
        "entity_name": facts_json.get("entityName", ""),
        "cik": facts_json.get("cik", ""),
        "observations": len(obs),
        "selected_rows": len(selected),
        "selected_by_basis": {k: int(v) for k, v in selected["value_basis"].value_counts().sort_index().items()},
        "restated_rows": int((selected["restated"] == True).sum()),  # noqa: E712 (object column)
        "gap_rows": len(gaps),
        "scale_anomalies": len(anomalies),
        "scale_anomalies_in_window": int((anomalies["in_target_window"] == True).sum()),  # noqa: E712
        "latest_fiscal_year": latest_fy,
        "target_window": f"FY{latest_fy - cfg['history']['target_fiscal_years'] + 1}-FY{latest_fy}" if latest_fy else "",
    }
    return checks, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["live", "snapshot"], required=True)
    ap.add_argument("--snapshot", help="path to a saved companyfacts JSON (snapshot mode only)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--out", help="output folder (default: paths.clean_dir from config)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / cfg["paths"]["clean_dir"]

    if args.source == "live":
        if args.snapshot:
            ap.error("--snapshot cannot be combined with --source live")
        snapshot = fetch_companyfacts(cfg)
        print(f"Fetched and saved: {snapshot}")
    else:
        snapshot = Path(args.snapshot) if args.snapshot else latest_snapshot(cfg)
        if not snapshot.is_absolute():
            snapshot = (Path.cwd() / snapshot).resolve()

    checks, summary = process_snapshot(snapshot, cfg, out_dir)

    manifest = {
        **summary,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_mode": args.source,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "git_commit": _git_commit(PROJECT_ROOT),
        "output_sha256": {name: sha256_file(out_dir / f) for name, f in OUTPUT_FILES.items()},
        "checks_passed": all(p for _, p, _, level in checks if level == "error"),
        "warnings": [c for c, p, _, level in checks if level == "warning" and not p],
    }
    with open(out_dir / "run_manifest.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, default=str)

    print(json.dumps(summary, indent=2, default=str))
    print("\nValidation:")
    for check_id, passed, detail, level in checks:
        status = "PASS" if passed else ("WARN" if level == "warning" else "FAIL")
        print(f"  {status}  {check_id}: {detail}")
    print(f"\nOutputs written to: {out_dir}")
    return 0 if manifest["checks_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
