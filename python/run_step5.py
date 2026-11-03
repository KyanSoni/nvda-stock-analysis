"""Step 5: model line items, assumptions and the 3-statement forecast workbook.

Usage (project folder, project venv; Steps 3 and 4 outputs present; no network, no database):
  & $vpy python\\run_step5.py facts     # 5a: model line items -> data\\clean\\step5\\facts_model.csv, model_data.csv
  & $vpy python\\run_step5.py model     # 5b: assumptions.csv, forecast.csv, excel\\NVDA_Forecast.xlsx
  & $vpy python\\run_step5.py all       # both
  add  --excel-check  to recalculate the workbook in LibreOffice (if installed) and compare it with the Python model
Exit code 0 = every error-level check passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step5_facts as f5
import step5_model as m
from common import PROJECT_ROOT, load_config, sha256_file, write_csv

OUT = PROJECT_ROOT / "data" / "clean" / "step5"
WORKBOOK = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"


def facts_stage(out: Path) -> list[tuple]:
    from run_step2 import load_universe
    uni = load_universe()
    s2man = json.loads((PROJECT_ROOT / uni["paths"]["step2_out"] / "run_manifest.json").read_text(encoding="utf-8"))
    coll = PROJECT_ROOT / uni["paths"]["collections_dir"] / s2man["collection_id"]
    res = f5.build(coll, out, uni, load_config(), f5.load_step5(), PROJECT_ROOT / "data" / "clean" / "step3" / "exports")
    print(f"Step 5a model line items from collection {s2man['collection_id']} -> {out}")
    return res


def model_stage(out: Path, workbook: Path, excel_check: bool) -> list[tuple]:
    import build_model
    import step5_check
    md = pd.read_csv(out / "model_data.csv", dtype=str, keep_default_na=False)
    est = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "step4" / "estimates.csv", dtype=str, keep_default_na=False)
    rat = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "step3" / "exports" / "v_ratios_annual.csv", dtype=str, keep_default_na=False)
    e4 = json.loads((PROJECT_ROOT / "data" / "clean" / "step4" / "estimates_manifest.json").read_text(encoding="utf-8"))
    at = m.assumption_table(md, m.load_model_cfg(), est, rat)
    write_csv(at, out / "assumptions.csv", ["ticker", "driver", "scenario"])
    rows = []
    for t in sorted(md["ticker"].unique()):
        years, h = m.history(md, t)
        for s in ("Bear", "Base", "Bull"):
            fc = m.forecast(h, m.scenario(at, t, s))
            for k, vals in fc.items():
                rows.append([t, s, k] + [f"{float(v):.6f}" for v in vals])
    write_csv(pd.DataFrame(rows, columns=["ticker", "scenario", "row", "y1", "y2", "y3", "y4", "y5"]), out / "forecast.csv", ["ticker", "scenario", "row"])
    meta = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "cutoff": e4["cutoff"], "snapshot": e4["snapshot_id"]}
    build_model.build(md, at, est, workbook, meta)
    print(f"Step 5b assumptions, forecast and workbook -> {out}, {workbook}")
    res = [("ALL", *c, "error") for c in step5_check.engine_checks(md, at)]
    if excel_check:
        for c in step5_check.compare(workbook, md, at):
            res.append(("ALL", c[0], c[1] if c[1] is not None else True, c[2], "error" if c[1] is not None else "warning"))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["facts", "model", "all"])
    ap.add_argument("--excel-check", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--workbook")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else OUT
    workbook = Path(args.workbook) if args.workbook else WORKBOOK
    checks = []
    if args.stage in ("facts", "all"):
        checks += facts_stage(out)
    if args.stage in ("model", "all"):
        checks += model_stage(out, workbook, args.excel_check)
    for scope, check, passed, detail, level in checks:
        print(f"  {'PASS' if passed else ('WARN' if level == 'warning' else 'FAIL')}  {scope:<5} {check}: {detail}")
    files = [p for p in ("facts_model.csv", "model_data.csv", "validation_step5.csv", "assumptions.csv", "forecast.csv") if (out / p).exists()]
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stage": args.stage,
                "output_sha256": {p: sha256_file(out / p) for p in files},
                "checks": [{"scope": s, "check": c, "passed": bool(p), "detail": d, "level": lv} for s, c, p, d, lv in checks]}
    if args.stage in ("model", "all"):
        manifest["workbook"] = str(workbook)
    (out / f"manifest_{args.stage}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok = all(p for _, _, p, _, lv in checks if lv == "error")
    print(f"  ... {sum(1 for c in checks if c[2])}/{len(checks)} checks pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
