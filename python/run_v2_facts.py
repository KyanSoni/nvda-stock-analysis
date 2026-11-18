"""Version 2, V2.3: extract the annual-report facts V2 needs from every company-facts file, offline.

Reads <bulk>/sec/companyfacts/*.json.gz (fetch_v2_sec.py companyfacts) and writes:
  <bulk>/facts/facts_v2.csv.gz        one row per observation (cik, concept, unit, start, end, days, value, form, filed, accn)
  data/clean/v2/facts/concept_coverage.csv   per line item: companies with at least one value, by concept
  data/clean/v2/facts/v1_fact_check.csv      V2 extraction vs Version 1's selected facts for the six companies (check F4)
  data/clean/v2/facts/manifest_v2_facts.json
Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml

import v2_facts as vf
import v2_sec as s
from common import PROJECT_ROOT, sha256_file, write_csv

CFG = PROJECT_ROOT / "config" / "v2.yaml"
OUT = PROJECT_ROOT / "data" / "clean" / "v2" / "facts"
V1_NAMES = {"stockholders_equity": "equity", "cash_and_equivalents": "cash"}


def facts_file(cfg: dict):
    return s.bulk_root(cfg) / "facts" / "facts_v2.csv.gz"


def load_facts(cfg: dict) -> pd.DataFrame:
    return pd.read_csv(facts_file(cfg), dtype={"cik": str, "concept": str, "unit": str, "start": str, "end": str, "form": str,
                                               "filed": str, "accn": str}, keep_default_na=False)


def v1_check(obs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """For the six Version 1 companies: each V1 annual or year-end value vs the V2 value for the same concept and period,
    taking the latest V2 observation filed on or before V1's filing date. Differences are listed, never adjusted."""
    path = PROJECT_ROOT / "data" / "clean" / "step2" / "facts_selected.csv"
    if not path.exists():
        return pd.DataFrame()
    v1 = pd.read_csv(path, dtype=str, keep_default_na=False)
    v1 = v1[(v1["entity_role"] == "current") & (v1["value_basis"].isin(["reported_annual", "reported_instant"]))
            & (v1["form"].str.startswith("10-K"))]
    rows = []
    for r in v1.itertuples():
        item = V1_NAMES.get(r.line_item, r.line_item)
        if item not in cfg["facts"]["line_items"] or r.concept not in cfg["facts"]["line_items"][item]:
            continue                            # V1 used a concept V2 does not list for this item: not comparable
        x = obs[(obs["cik"] == r.entity_cik) & (obs["concept"] == r.concept) & (obs["end"] == r.period_end)
                & (obs["start"] == ("" if r.value_basis == "reported_instant" else r.period_start)) & (obs["filed"] <= r.filed)]
        if x.empty:
            rows.append({"ticker": r.ticker, "line_item": item, "concept": r.concept, "period_end": r.period_end, "v1_value": r.value,
                         "v2_value": "", "agree": False, "note": "not in V2 extraction"})
            continue
        y = x.sort_values(["filed", "accn"]).iloc[-1]
        agree = abs(float(r.value) - float(y["value"])) <= 0.5 + 1e-9 * abs(float(r.value))
        rows.append({"ticker": r.ticker, "line_item": item, "concept": r.concept, "period_end": r.period_end, "v1_value": r.value,
                     "v2_value": y["value"], "agree": agree, "note": "" if agree else f"V2 from {y['accn']} filed {y['filed']}, V1 from {r.accn}"})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    root = s.bulk_root(cfg)
    res = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "v2" / "sec" / "cik_by_date.csv", dtype=str, keep_default_na=False)
    need = sorted(set(res[(res["cik_pit"] != "") & (res["excluded_sector"] != "True")]["cik_pit"]))
    frames, missing, empty = [], [], []
    for i, cik in enumerate(need, 1):
        p = s.facts_path(root, cik)
        if not p.exists():
            missing.append(cik)
            continue
        df = vf.extract(s.read_gz_json(p), cik, cfg)
        (frames.append(df) if len(df) else empty.append(cik))
        if i % 100 == 0:
            print(f"  extracted {i}/{len(need)}", flush=True)
    obs = pd.concat(frames, ignore_index=True)
    fpath = facts_file(cfg)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    obs.to_csv(fpath, index=False, compression="gzip")
    obs = load_facts(cfg)                       # re-read: the check runs on exactly what later steps will read

    cov = []
    n = obs["cik"].nunique()
    for item, cands in cfg["facts"]["line_items"].items():
        x = obs[obs["concept"].isin(cands)]
        row = {"line_item": item, "companies_with_any": x["cik"].nunique(), "share": x["cik"].nunique() / n if n else 0}
        for c in cands:
            row[c] = obs[obs["concept"] == c]["cik"].nunique()
        cov.append({"line_item": row["line_item"], "companies_with_any": row["companies_with_any"], "share": round(row["share"], 4),
                    "by_concept": "; ".join(f"{c} {row[c]}" for c in cands)})
    cov = pd.DataFrame(cov)
    chk = v1_check(obs, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(cov, OUT / "concept_coverage.csv", ["line_item"])
    if len(chk):
        write_csv(chk, OUT / "v1_fact_check.csv", ["ticker", "line_item", "period_end"])
    have = len(need) - len(missing)
    core = cov.set_index("line_item")["share"]
    agree = chk["agree"].mean() if len(chk) else 0.0
    cks = [("F1_companyfacts_on_disk", have >= 0.97 * len(need), f"{have}/{len(need)} resolved CIKs have company facts; "
            f"missing {missing[:8] or 'none'} (SEC has no XBRL facts for some filers)", "error"),
           ("F2_extraction_nonempty", len(empty) <= 0.03 * max(have, 1), f"{have - len(empty)}/{have} files gave annual-report facts; empty: {empty[:8] or 'none'}", "error"),
           ("F3_core_items_covered", all(core.get(k, 0) >= 0.95 for k in ("revenue", "net_income", "equity", "operating_cash_flow")),
            "companies with any value: " + ", ".join(f"{k} {core.get(k, 0):.0%}" for k in cfg["facts"]["line_items"]), "warning"),
           ("F4_matches_version1", len(chk) > 0 and agree >= 0.99, f"{int(chk['agree'].sum()) if len(chk) else 0}/{len(chk)} Version 1 annual values "
            f"for the six companies equal V2's for the same concept and period ({agree:.1%}); differences in v1_fact_check.csv", "error")]
    print(f"V2.3 facts: {len(obs):,} observations for {obs['cik'].nunique()} companies -> {fpath}")
    for c, ok, d, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl != 'error' else 'FAIL')}  {c}: {d}")
    m = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "facts_file": str(fpath),
         "facts_sha256": sha256_file(fpath), "companies": int(obs["cik"].nunique()), "observations": len(obs), "missing": missing, "empty": empty,
         "checks": [{"check": c, "passed": bool(ok), "detail": d, "level": lvl} for c, ok, d, lvl in cks]}
    (OUT / "manifest_v2_facts.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
