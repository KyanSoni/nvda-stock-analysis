"""Step 4: consensus estimates, provisional WACC and the 20-point scorecard.

Usage (project folder, project venv, $env:PGPASSWORD set; Step 3 built):
  & $vpy python\\fetch_step4.py             # once: snapshot the consensus estimates (network)
  & $vpy python\\run_step4.py all           # estimates (offline) + database views + exports
  & $vpy python\\run_step4.py estimates     # only parse the latest snapshot into data\\clean\\step4\\estimates.csv
  & $vpy python\\run_step4.py db            # only (re)build the Step 4 tables and views
Exit code 0 = every error-level check passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step4_estimates as est
from common import PROJECT_ROOT, sha256_file

OUT = PROJECT_ROOT / "data" / "clean" / "step4"


def estimates_stage(out: Path, sc: dict, snapshot: str | None = None) -> bool:
    from run_step2 import load_universe
    uni = load_universe()
    snap = (PROJECT_ROOT / sc["estimates"]["raw_dir"] / snapshot) if snapshot else est.latest_snapshot(sc)
    rows, problems = est.parse_snapshot(snap, list(uni["companies"]))
    mi = pd.read_csv(PROJECT_ROOT / uni["paths"]["step2_out"] / "market" / "market_inputs.csv", dtype=str, keep_default_na=False)
    cutoff = mi["cutoff_date"].iloc[0]
    age_ok, age = est.snapshot_age_ok(rows, cutoff, sc["estimates"]["max_days_after_cutoff"])
    out.mkdir(parents=True, exist_ok=True)
    est.write_rows(rows, out / "estimates.csv")
    checks = [("E1_estimates_files_valid_and_complete", not problems, "; ".join(problems) or "0y and +1y consensus EPS for every company"),
              ("E2_estimates_fetched_near_cutoff", age_ok, age)]
    (out / "estimates_manifest.json").write_text(json.dumps({
        "snapshot_id": snap.name, "snapshot_info": est.snapshot_info(snap), "cutoff": cutoff,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "output_sha256": {"estimates.csv": sha256_file(out / "estimates.csv")},
        "checks": [{"check": c, "passed": p, "detail": d} for c, p, d in checks]}, indent=2), encoding="utf-8")
    print(f"Step 4a estimates from snapshot {snap.name} -> {out / 'estimates.csv'} ({len(rows)} rows)")
    for c, p, d in checks:
        print(f"  {'PASS' if p else 'FAIL'}  {c}: {d}")
    return all(p for _, p, _ in checks)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["estimates", "db", "all"])
    ap.add_argument("--snapshot", help="estimates snapshot id (default: the latest)")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    sc = est.load_scorecard()
    out = Path(args.out) if args.out else OUT
    ok = True
    if args.stage in ("estimates", "all"):
        ok = estimates_stage(out, sc, args.snapshot) and ok
    if args.stage in ("db", "all"):
        import step4_db
        print("Step 4b scorecard database")
        ok = step4_db.build(out, sc) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
