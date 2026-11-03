"""Step 3 pipeline.

  & $vpy python\\run_step3.py facts        # 3a: extended facts + split adjustment -> data\\clean\\step3 (no network, no database)
  & $vpy python\\run_step3.py db           # 3b: build the PostgreSQL schema, load, create views, export CSVs
  & $vpy python\\run_step3.py all          # both
Exit code 0 = every error-level check passed.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step2_sec as s2
import step3_facts as s3f
from common import PROJECT_ROOT, load_config, sha256_file, write_csv
from run_step2 import latest_collection, load_universe

FACT_OUTPUTS = ["facts_extended.csv", "split_factors.csv", "gap_report_step3.csv", "validation_step3.csv"]


def build_facts(coll: Path, out: Path, uni: dict, base: dict, s3: dict, step2_out: Path) -> tuple[list, dict]:
    out.mkdir(parents=True, exist_ok=True)
    step2_facts = pd.read_csv(step2_out / "facts_selected.csv", dtype=str, keep_default_na=False)
    actions = pd.read_csv(step2_out / "market" / "corporate_actions.csv", dtype=str, keep_default_na=False)
    splits = s3f.split_table(actions, list(uni["companies"]))
    manual_path = PROJECT_ROOT / s3["manual_facts_file"]
    checks, summary, frames, gaps_all = [], {}, [], []
    for ticker in uni["companies"]:
        obs, files = s2.load_company(coll, uni, ticker)
        cfg, guards, derived2, derived3 = s3f.company_config(base, uni, s3, ticker)
        sel = s2.select_company(obs, cfg, guards, ticker)
        dq = s2.derive_quarters(sel, cfg)
        sel = pd.concat([sel, dq], ignore_index=True)
        dc = s2.derive_components(sel, cfg, uni, derived2)
        sel = pd.concat([sel, dc], ignore_index=True)
        for col in s3f.EXTRA_COLUMNS:
            sel[col] = ""
        sums = s3f.derive_sums(sel, cfg, s3, ticker, derived3)
        sel = pd.concat([sel, sums], ignore_index=True)
        zeros = s3f.declared_zeros(sel, cfg, s3, ticker)
        manual, problems = s3f.manual_facts(manual_path, cfg, ticker, cfg["company"]["fiscal_year_end_month"])
        sel = pd.concat([sel, zeros, manual], ignore_index=True)[s3f.OUT_COLUMNS]
        sel = s3f.apply_split_adjustment(sel, splits, s3["split_adjusted_items"])
        gaps, latest = s2.gap_report(sel[~sel["value_basis"].isin(s3f.STEP3_BASES)], cfg, ticker)
        # a gap is closed by a Step 3 value for the same item and period label
        filled = {(r.line_item, str(r.fiscal_year), r.fiscal_period) for r in sel[sel["value_basis"].isin(s3f.STEP3_BASES)].itertuples()}
        gaps = gaps[[(r.line_item, str(r.fiscal_year), r.fiscal_period) not in filled for r in gaps.itertuples()]]
        m2 = sel[sel["value_basis"].isin(s2.ALL_BASES)]
        c2, _ = s2.company_checks(obs, m2[s2.OUT_COLUMNS], files, cfg, guards, uni, derived2, latest)
        c2 = [c for c in c2 if c[0] not in ("C18_ltm_quarters_complete",)]
        c3 = s3f.step3_checks(sel, step2_facts[step2_facts["ticker"] == ticker], cfg, s3, ticker, problems)
        flows = [i for i, sp in cfg["line_items"].items() if sp["period_type"] == "duration" and sp.get("derive_q4") and not sp.get("support")]
        old = [i for i in flows if i in base["line_items"]]
        new = [i for i in flows if i not in base["line_items"]]
        c18 = [s3f.ltm_check(sel, cfg, old), s3f.ltm_check(sel, cfg, new, "W4_ltm_quarters_new_items", "warning")]
        cov = s3f.coverage_checks(sel[sel["support_item"] != True], cfg, s3, latest)  # noqa: E712
        checks += [(ticker, *c) for c in c2 + c18 + c3 + cov]
        frames.append(sel)
        gaps_all.append(gaps)
        summary[ticker] = {"rows": len(sel), "latest_fiscal_year": latest,
                           "by_basis": {k: int(v) for k, v in sel["value_basis"].value_counts().sort_index().items()},
                           "gaps": len(gaps)}
    facts = pd.concat(frames, ignore_index=True)
    write_csv(facts, out / "facts_extended.csv", s2.KEY)
    write_csv(splits, out / "split_factors.csv", ["ticker", "date"])
    write_csv(pd.concat(gaps_all, ignore_index=True), out / "gap_report_step3.csv", ["ticker", "line_item", "fiscal_year", "fiscal_period"])
    write_csv(pd.DataFrame(checks, columns=["scope", "check", "passed", "detail", "level"], dtype=object),
              out / "validation_step3.csv", ["scope", "check"])
    return checks, summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["facts", "db", "all"])
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    uni, base, s3 = load_universe(), load_config(), s3f.load_step3()
    out = Path(args.out) if args.out else PROJECT_ROOT / s3["paths"]["step3_out"]
    step2_out = PROJECT_ROOT / uni["paths"]["step2_out"]
    ok = True
    if args.stage in ("facts", "all"):
        s2man = json.loads((step2_out / "run_manifest.json").read_text(encoding="utf-8"))
        coll = PROJECT_ROOT / uni["paths"]["collections_dir"] / s2man["collection_id"]
        checks, summary = build_facts(coll, out, uni, base, s3, step2_out)
        ok = all(p for _, _, p, _, lvl in checks if lvl == "error")
        manifest = {"stage": "facts", "collection_id": s2man["collection_id"], "step2_outputs_sha256": s2man["output_sha256"],
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "python": platform.python_version(), "pandas": pd.__version__, "companies": summary,
                    "output_sha256": {f: sha256_file(out / f) for f in FACT_OUTPUTS}, "checks_passed": ok}
        (out / "facts_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        print(f"Step 3a facts from collection {s2man['collection_id']} -> {out}")
        for t, s in summary.items():
            print(f"  {t:<5} rows {s['rows']:>5}  gaps {s['gaps']:>3}  {s['by_basis']}")
        for scope, check, passed, detail, level in checks:
            if not passed:
                print(f"  {'WARN' if level == 'warning' else 'FAIL'}  {scope:<5} {check}: {detail}")
        print(f"  ... {sum(1 for c in checks if c[2])}/{len(checks)} checks pass")
    if args.stage in ("db", "all"):
        import step3_db
        ok = step3_db.build(out) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
