"""Step 6: DCF valuation (Python reference values, sensitivities, reverse DCF, peer table) and the workbook's
WACC / DCF tabs.

Usage (project folder, project venv; Steps 3, 4 and 5 outputs present; no network, no database):
  & $vpy python\\run_step6.py                 # data\\clean\\step6\\*.csv and excel\\NVDA_Forecast.xlsx (with WACC, DCF, DcfData)
  add  --excel-check  to recalculate the workbook in LibreOffice (if installed) and compare its DCF with Python
Exit code 0 = every error-level check passes.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step6_dcf as d
from common import PROJECT_ROOT, sha256_file, write_csv

S5 = PROJECT_ROOT / "data" / "clean" / "step5"
OUT = PROJECT_ROOT / "data" / "clean" / "step6"
WORKBOOK = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"
FILES = ["dcf_inputs.csv", "dcf_values.csv", "dcf_detail.csv", "sensitivity_wacc_g.csv", "sensitivity_growth_margin.csv", "reverse_dcf.csv"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--excel-check", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--workbook")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else OUT
    workbook = Path(args.workbook) if args.workbook else WORKBOOK
    missing = d.missing_sources() + [str(S5 / p) for p in ("model_data.csv", "assumptions.csv") if not (S5 / p).exists()]
    if missing:
        print("Step 6 inputs missing (run Steps 3-5 first):\n  " + "\n  ".join(missing))
        return 1
    rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731
    md, at = rd(S5 / "model_data.csv"), rd(S5 / "assumptions.csv")
    p = d.payload(md, at)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(p["inputs"], out / "dcf_inputs.csv", ["ticker"])
    write_csv(p["values"], out / "dcf_values.csv", ["ticker"])
    write_csv(p["detail"], out / "dcf_detail.csv", ["ticker", "scenario", "row"])
    write_csv(p["wacc_g"], out / "sensitivity_wacc_g.csv", ["wacc"])
    write_csv(p["gm_sensitivity"], out / "sensitivity_growth_margin.csv", ["fy2_segment_a_growth"])
    write_csv(p["reverse"], out / "reverse_dcf.csv", ["ticker", "scenario", "lever"])
    import build_model
    e4 = json.loads((PROJECT_ROOT / "data" / "clean" / "step4" / "estimates_manifest.json").read_text(encoding="utf-8"))
    est = rd(PROJECT_ROOT / "data" / "clean" / "step4" / "estimates.csv")
    meta = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "cutoff": e4["cutoff"], "snapshot": e4["snapshot_id"]}
    build_model.build(md, at, est, workbook, meta, p)
    print(f"Step 6 DCF -> {out}, {workbook}")
    checks = [("ALL", *c, "error") for c in d.engine_checks(md, at, p["inputs"], p["values"])]
    if args.excel_check:
        import step6_check
        for c in step6_check.compare(workbook, md, at, p["inputs"], p["wacc_g"]):
            checks.append(("ALL", c[0], c[1] if c[1] is not None else True, c[2], "error" if c[1] is not None else "warning"))
    for t, flag in p["values"][["ticker", "quality_flag"]].itertuples(index=False):
        if flag:
            checks.append((t, "D5_peer_quality", False, flag, "warning"))
    for scope, check, passed, detail, level in checks:
        print(f"  {'PASS' if passed else ('WARN' if level == 'warning' else 'FAIL')}  {scope:<5} {check}: {detail}")
    v = p["values"].set_index("ticker").loc["NVDA"]
    print(f"  NVDA value per share: Bear {float(v['bear_per_share']):.2f}, Base {float(v['base_per_share']):.2f}, "
          f"Bull {float(v['bull_per_share']):.2f}; weighted {float(v['weighted_per_share']):.2f} vs price {float(v['price']):.2f} "
          f"({float(v['weighted_upside']):+.1%})")
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "output_sha256": {f: sha256_file(out / f) for f in FILES}, "workbook": str(workbook),
                "checks": [{"scope": s, "check": c, "passed": bool(x), "detail": dd, "level": lv} for s, c, x, dd, lv in checks]}
    (out / "manifest_step6.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok = all(x for _, _, x, _, lv in checks if lv == "error")
    print(f"  ... {sum(1 for c in checks if c[2])}/{len(checks)} checks pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
