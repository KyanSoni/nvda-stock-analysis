"""Step 7: comparable companies for NVIDIA (calendarised NTM and LTM multiples, peer statistics, implied values,
growth vs multiple, football field, DCF / comps blend) and the workbook's Comps tab.

Usage (project folder, project venv; Steps 2-6 outputs present; no network, no database):
  & $vpy python\\run_step7.py                 # data\\clean\\step7\\*.csv and excel\\NVDA_Forecast.xlsx (rebuilt with Comps, CompsData)
  add  --excel-check  to recalculate the workbook in LibreOffice (if installed) and compare its Comps tab with Python
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
import step7_comps as c
from common import PROJECT_ROOT, sha256_file, write_csv

S5 = PROJECT_ROOT / "data" / "clean" / "step5"
OUT = PROJECT_ROOT / "data" / "clean" / "step7"
WORKBOOK = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"
FILES = ["comps_table.csv", "comps_stats.csv", "comps_implied.csv", "comps_regression.csv", "football_field.csv", "comps_blend.csv"]


def fmt(df: pd.DataFrame) -> pd.DataFrame:
    """Floats written with 6 decimals so the CSVs are byte-identical on rerun and readable."""
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(lambda v: "" if v is None or (isinstance(v, float) and v != v)
                                else (f"{v:.6f}" if isinstance(v, float) else str(v)))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--excel-check", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--workbook")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else OUT
    workbook = Path(args.workbook) if args.workbook else WORKBOOK
    missing = c.missing_inputs(with_step6_outputs=False) + d.missing_sources() + \
        [str(S5 / p) for p in ("model_data.csv", "assumptions.csv") if not (S5 / p).exists()]
    if missing:
        print("Step 7 inputs missing (run Steps 2-6 first):\n  " + "\n  ".join(missing))
        return 1
    rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731
    md, at = rd(S5 / "model_data.csv"), rd(S5 / "assumptions.csv")
    p6 = d.payload(md, at)                    # the DCF recomputed now, so the blend never uses stale Step 6 values
    res = c.run(inp=c.read_inputs(p6))
    out.mkdir(parents=True, exist_ok=True)
    write_csv(fmt(res["table"]), out / "comps_table.csv", ["ticker"])
    write_csv(fmt(res["stats"]), out / "comps_stats.csv", ["multiple"])
    write_csv(fmt(res["implied"]), out / "comps_implied.csv", ["multiple"])
    write_csv(fmt(pd.DataFrame([{k: float(v) if not isinstance(v, int) else v for k, v in res["regression"].items()}])), out / "comps_regression.csv", ["n"])
    write_csv(fmt(res["football"].reset_index()), out / "football_field.csv", ["index"])
    write_csv(fmt(pd.DataFrame([{k: float(v) for k, v in res["blend"].items()}])), out / "comps_blend.csv", ["price"])
    import build_model
    e4 = json.loads((PROJECT_ROOT / "data" / "clean" / "step4" / "estimates_manifest.json").read_text(encoding="utf-8"))
    est = rd(PROJECT_ROOT / "data" / "clean" / "step4" / "estimates.csv")
    meta = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "cutoff": e4["cutoff"], "snapshot": e4["snapshot_id"]}
    build_model.build(md, at, est, workbook, meta, p6)
    print(f"Step 7 comps -> {out}, {workbook}")
    checks = [("ALL", *x, "error") for x in c.checks(res)]
    if args.excel_check:
        import step7_check
        for x in step7_check.compare(workbook, res):
            checks.append(("ALL", x[0], x[1] if x[1] is not None else True, x[2], "error" if x[1] is not None else "warning"))
    for scope, check, passed, detail, level in checks:
        print(f"  {'PASS' if passed else ('WARN' if level == 'warning' else 'FAIL')}  {scope:<5} {check}: {detail}")
    b, n = res["blend"], res["table"].set_index("ticker").loc[res["cfg"]["target"]]
    print(f"  NVDA NTM P/E {n['pe_ntm']:.1f}x, NTM EV/EBITDA {n['ev_ebitda_ntm']:.1f}x; comps value {b['comps_value']:.2f}, "
          f"DCF {b['dcf_weighted']:.2f}; blended {b['blended_value']:.2f} vs price {b['price']:.2f} ({b['upside']:+.1%})")
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "output_sha256": {x: sha256_file(out / x) for x in FILES}, "workbook": str(workbook),
                "checks": [{"scope": s, "check": k, "passed": bool(x), "detail": dd, "level": lv} for s, k, x, dd, lv in checks]}
    (out / "manifest_step7.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok = all(x for _, _, x, _, lv in checks if lv == "error")
    print(f"  ... {sum(1 for k in checks if k[2])}/{len(checks)} checks pass")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
