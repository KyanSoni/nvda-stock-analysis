"""Version 2, V2.1: process the latest universe collection offline into data/clean/v2/universe.

Usage (project folder, project venv; after fetch_v2_universe.py):
  & $vpy python\\run_v2_universe.py              # latest collection
  & $vpy python\\run_v2_universe.py <collection_id>
Outputs: constituents_current.csv, changes.csv, ticker_changes.csv, membership.csv (members at each rebalance date and the collection date,
with CIK and its basis), ciks.csv, coverage.csv, warnings.txt, manifest_v2_universe.json. Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import v2_universe as u
from common import PROJECT_ROOT, sha256_file, write_csv

CFG = PROJECT_ROOT / "config" / "v2.yaml"
FILES = ["constituents_current.csv", "changes.csv", "ticker_changes.csv", "membership.csv", "ciks.csv", "coverage.csv"]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    raw_root = PROJECT_ROOT / cfg["universe"]["raw_dir"]
    colls = sorted(p for p in raw_root.glob("*T*Z") if (p / "collection_manifest.csv").exists()) if raw_root.exists() else []
    if argv:
        colls = [raw_root / argv[0]]
    if not colls or not colls[-1].exists():
        print(f"No universe collection in {raw_root}: run python\\fetch_v2_universe.py first")
        return 1
    raw = colls[-1]
    stamp = raw.name
    today = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"
    res = u.build(raw, cfg, today)
    out = PROJECT_ROOT / cfg["universe"]["clean_dir"]
    out.mkdir(parents=True, exist_ok=True)
    write_csv(res["current"], out / "constituents_current.csv", ["ticker"])
    write_csv(res["changes"], out / "changes.csv", ["date", "added_ticker", "removed_ticker"])
    write_csv(res["renames"], out / "ticker_changes.csv", ["added_date", "old_ticker"])
    write_csv(res["membership"], out / "membership.csv", ["date", "ticker"])
    write_csv(res["ciks"], out / "ciks.csv", ["ticker"])
    write_csv(res["coverage"], out / "coverage.csv", ["date"])
    (out / "warnings.txt").write_text("\n".join(res["warnings"]) + "\n", encoding="utf-8")
    cks = u.checks(res, cfg)
    print(f"V2.1 universe from collection {stamp} -> {out}")
    for c, ok, d, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl == 'warning' else 'FAIL')}  {c}: {d}")
    for r in res["renames"].itertuples():
        print(f"  ticker change: {r.old_ticker} ({r.old_security}) -> {r.ticker} ({r.security}), basis {r.basis}")
    b = res["ciks"]["cik_basis"].value_counts()
    print("  CIK basis (every company ever in the universe since " + str(cfg["backtest"]["first_year"]) + "): "
          + ", ".join(f"{k} {v}" for k, v in b.items()))
    m = res["membership"]
    for t in ("NVDA", "AMD", "AVGO", "INTC", "QCOM", "MRVL"):
        ds = m[m["ticker"] == t]["date"]
        print(f"  {t:<5} member at {len(ds)}/{len(res['dates'])} dates" + (f" (first {ds.min()})" if len(ds) else ""))
    unm = res["ciks"][res["ciks"]["cik_basis"] == "unmapped"]
    print(f"  Unmapped companies: {len(unm)} (listed in ciks.csv; V2.2 resolves them from EDGAR, never by guessing)")
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "collection": stamp,
                "output_sha256": {f: sha256_file(out / f) for f in FILES},
                "checks": [{"check": c, "passed": bool(ok), "detail": d, "level": lvl} for c, ok, d, lvl in cks]}
    (out / "manifest_v2_universe.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
