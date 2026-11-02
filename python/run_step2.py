"""Step 2 pipeline: process one saved collection (no network) into data/clean/step2/.

Usage (project folder, project venv):
  & $vpy python\\run_step2.py                       # latest collection in data\\raw\\collections
  & $vpy python\\run_step2.py --collection 20261102T230040Z [--out <folder>]
Exit code 0 = every error-level check passed; 1 = at least one failed (see validation_summary.csv).
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from decimal import Decimal

import pandas as pd

from common import PROJECT_ROOT, load_config, sha256_file, write_csv
import step2_market as mk
import step2_sec as sec

UNIVERSE = PROJECT_ROOT / "config" / "universe.yaml"


def load_universe():
    import yaml
    with open(UNIVERSE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def latest_collection(uni: dict) -> Path:
    root = PROJECT_ROOT / uni["paths"]["collections_dir"]
    found = sorted(p for p in root.iterdir() if p.is_dir() and (p / "collection_manifest.csv").exists()) if root.exists() else []
    if not found:
        raise FileNotFoundError("No collection yet: run python\\fetch_step2.py first.")
    return found[-1]


def _git_commit() -> str:
    try:
        r = subprocess.run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "no commit"
    except (OSError, subprocess.SubprocessError):
        return "git unavailable"


def process(coll: Path, out: Path, uni: dict, base: dict) -> tuple[list, dict]:
    manifest = pd.read_csv(coll / "collection_manifest.csv", dtype=str, keep_default_na=False)
    info = json.loads((coll / "collection_info.json").read_text(encoding="utf-8"))
    checks, summary = [], {"collection_id": info["collection_id"], "companies": {}}
    out.mkdir(parents=True, exist_ok=True)

    # ---- identity (M2-D1, M2-D5)
    ident, problems = sec.identity_report(coll, uni)
    write_csv(ident, out / "identity_report.csv", ["ticker", "role", "cik"])
    checks.append(("ALL", "I1_identities_and_fiscal_calendars", not problems, "; ".join(problems) or
                   f"{len(ident)} registrants verified against SEC ticker file and submissions", "error"))

    # ---- SEC facts per company
    all_facts, all_gaps, all_anom, company_obs = [], [], [], {}
    for ticker in uni["companies"]:
        obs, files = sec.load_company(coll, uni, ticker)
        for f in files:  # file hashes must match the collection manifest
            m = manifest[manifest["file"].str.endswith(f"sec/{f['file']}")]
            if f["present"] and (m.empty or m.iloc[0]["sha256"] != f["sha256"]):
                checks.append((ticker, "I2_file_matches_manifest", False, f"{f['file']} hash differs from manifest", "error"))
        cfg, guards, derived = sec.company_config(base, uni, ticker)
        selected = sec.select_company(obs, cfg, guards, ticker)
        dq = sec.derive_quarters(selected, cfg)
        selected = pd.concat([selected, dq], ignore_index=True) if not dq.empty else selected
        dc = sec.derive_components(selected, cfg, uni, derived)
        selected = pd.concat([selected, dc], ignore_index=True) if not dc.empty else selected
        selected = selected[sec.OUT_COLUMNS]
        gaps, latest = sec.gap_report(selected, cfg, ticker)
        cchecks, anomalies = sec.company_checks(obs, selected, files, cfg, guards, uni, derived, latest)
        checks += [(ticker, *c) for c in cchecks]
        anomalies.insert(0, "ticker", ticker)
        tdir = out / ticker
        write_csv(obs, tdir / "sec_observations.csv",
                  ["entity_cik", "taxonomy", "concept", "unit", "period_end", "period_start", "filed", "accn", "form", "frame", "value"])
        write_csv(gaps, tdir / "gap_report.csv", ["line_item", "fiscal_year", "fiscal_period"])
        write_csv(anomalies, tdir / "anomalies.csv", ["line_item", "value_basis", "period_end", "anomaly_type", "fiscal_period"])
        all_facts.append(selected)
        all_gaps.append(gaps)
        all_anom.append(anomalies)
        company_obs[ticker] = obs
        n = cfg["history"]["target_fiscal_years"]
        summary["companies"][ticker] = {
            "registrant_files": [f["file"] for f in files if f["present"]],
            "observations": len(obs), "selected_rows": len(selected),
            "by_basis": {k: int(v) for k, v in selected["value_basis"].value_counts().sort_index().items()},
            "latest_fiscal_year": latest, "window": f"FY{latest - n + 1}-FY{latest}" if latest else "",
            "gap_rows": len(gaps), "scale_anomalies": len(anomalies),
            "fallback_rows": int(sum(selected["concept"].isin({c for (_, c) in guards}))),
        }
    facts = pd.concat(all_facts, ignore_index=True)
    write_csv(facts, out / "facts_selected.csv", sec.KEY)
    write_csv(pd.concat(all_gaps, ignore_index=True), out / "gap_report_all.csv", ["ticker", "line_item", "fiscal_year", "fiscal_period"])
    write_csv(pd.concat(all_anom, ignore_index=True), out / "anomalies_all.csv", ["ticker", "line_item", "value_basis", "period_end", "anomaly_type"])

    # ---- market (M2b)
    symbols = list(uni["companies"]) + list(uni["benchmarks"])
    prices = mk.load_prices(coll, symbols, manifest)
    cutoff, cut_note = mk.cutoff_date(info, prices, "SPY", uni["market"]["market_close_et"])
    prices_out = prices[prices["date"] <= cutoff] if cutoff else prices
    write_csv(prices_out, out / "market" / "prices.csv", ["ticker", "date"])
    actions = mk.corporate_actions(prices_out)
    write_csv(actions, out / "market" / "corporate_actions.csv", ["ticker", "date", "action"])
    for c in mk.price_checks(prices, cutoff, "SPY", symbols):
        checks.append(("MARKET", *c, "error"))
    ok, detail, _ = mk.split_crosscheck(actions, facts)
    checks.append(("MARKET", "P3_splits_match_sec_share_counts", ok, detail, "error"))

    rf = mk.risk_free(coll, uni, cutoff)
    rf_ok = bool(rf["value_pct"]) and rf["lag_days"] != "" and int(rf["lag_days"]) <= uni["market"]["risk_free_max_lag_days"]
    checks.append(("MARKET", "P4b_risk_free_at_cutoff", rf_ok,
                   f"{rf['series']} {rf['value_pct']}% observed {rf['observation_date']} ({rf['lag_days']} days before cutoff)"
                   if rf["value_pct"] else "no 10-year yield in the collection (FRED and Treasury files missing)", "error"))

    rows, share_problems = [], []
    for sym in symbols:
        bar = prices[(prices["ticker"] == sym) & (prices["date"] == cutoff)]
        row = {"ticker": sym, "cutoff_date": cutoff, "cutoff_rule": uni["market"]["cutoff_rule"],
               "close": bar.iloc[0]["close"] if len(bar) else "", "adj_close": bar.iloc[0]["adj_close"] if len(bar) else "",
               "close_2dp": str(Decimal(bar.iloc[0]["close"]).quantize(Decimal("0.01"))) if len(bar) else "",
               "price_source": f"yfinance {info['packages'].get('yfinance', '')}, {bar.iloc[0]['source_file']}" if len(bar) else "",
               "shares_outstanding": "", "shares_as_of": "", "shares_accn": "", "shares_form": "", "shares_filed": "",
               "market_cap_usd": "", "market_cap_basis": "", "yfinance_shares_crosscheck": "", "shares_diff_pct": ""}
        if sym in company_obs:
            so = mk.shares_outstanding(company_obs[sym], cutoff)
            if so:
                row.update(shares_outstanding=so["shares"], shares_as_of=so["as_of"], shares_accn=so["accn"],
                           shares_form=so["form"], shares_filed=so["filed"])
                if row["close_2dp"]:
                    row["market_cap_usd"] = str((Decimal(row["close_2dp"]) * Decimal(so["shares"])).quantize(Decimal("1")))
                    row["market_cap_basis"] = f"derived: cutoff close (to the cent) x SEC cover-page shares as of {so['as_of']}"
                yf_sh = mk.yfinance_shares(manifest, sym)
                if yf_sh:
                    diff = (Decimal(yf_sh) / Decimal(so["shares"]) - 1) * 100
                    row.update(yfinance_shares_crosscheck=yf_sh, shares_diff_pct=str(diff.quantize(Decimal("0.01"))))
            else:
                share_problems.append(sym)
        rows.append(row)
    rows.append({"ticker": "RISK_FREE_10Y", "cutoff_date": cutoff, "cutoff_rule": uni["market"]["cutoff_rule"],
                 "close": rf["value_pct"], "close_2dp": rf["value_pct"], "price_source": f"{rf['series']} {rf['source_file']}",
                 "shares_as_of": rf["observation_date"], "market_cap_basis": "value in percent; shares_as_of = observation date"})
    inputs = pd.DataFrame(rows, dtype=object).fillna("")
    write_csv(inputs, out / "market" / "market_inputs.csv", ["ticker"])
    checks.append(("MARKET", "P5_shares_outstanding_with_provenance", not share_problems,
                   f"missing for {share_problems}" if share_problems else f"{len(uni['companies'])} companies, each with accession and as-of date", "error"))
    big = [f"{r['ticker']} {r['shares_diff_pct']}%" for r in rows if r.get("shares_diff_pct") and abs(float(r["shares_diff_pct"])) > 5]
    checks.append(("MARKET", "W2_yfinance_shares_differ_over_5pct", not big, "; ".join(big) or "all within 5%", "warning"))
    summary["market"] = {"cutoff": cutoff, "cutoff_note": cut_note, "price_rows": len(prices_out),
                         "corporate_actions": len(actions), "risk_free": rf}

    val = pd.DataFrame(checks, columns=["scope", "check", "passed", "detail", "level"], dtype=object)
    write_csv(val, out / "validation_summary.csv", ["scope", "check"])
    return checks, summary


OUTPUTS = ["identity_report.csv", "facts_selected.csv", "gap_report_all.csv", "anomalies_all.csv",
           "validation_summary.csv", "market/prices.csv", "market/corporate_actions.csv", "market/market_inputs.csv"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    uni = load_universe()
    base = load_config()
    coll = (PROJECT_ROOT / uni["paths"]["collections_dir"] / args.collection) if args.collection else latest_collection(uni)
    out = Path(args.out) if args.out else PROJECT_ROOT / uni["paths"]["step2_out"]
    checks, summary = process(coll, out, uni, base)
    errors_ok = all(p for _, _, p, _, level in checks if level == "error")
    manifest = {**summary, "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "collection_dir": coll.relative_to(PROJECT_ROOT).as_posix() if coll.is_relative_to(PROJECT_ROOT) else str(coll),
                "python": platform.python_version(), "pandas": pd.__version__, "git_commit": _git_commit(),
                "output_sha256": {f: sha256_file(out / f) for f in OUTPUTS},
                "checks_passed": errors_ok,
                "warnings": [f"{s}:{c}" for s, c, p, _, level in checks if level == "warning" and not p]}
    with open(out / "run_manifest.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, default=str)
    print(f"Collection {summary['collection_id']}  ->  {out}")
    for t, s in summary["companies"].items():
        print(f"  {t:<5} {s['window']:<14} selected {s['selected_rows']:>5}  gaps {s['gap_rows']:>3}  "
              f"anomalies {s['scale_anomalies']:>2}  fallback rows {s['fallback_rows']:>3}  files {len(s['registrant_files'])}")
    print(f"  market cutoff {summary['market']['cutoff']}  price rows {summary['market']['price_rows']}")
    print("\nChecks:")
    for scope, check, passed, detail, level in checks:
        status = "PASS" if passed else ("WARN" if level == "warning" else "FAIL")
        if status != "PASS" or scope in ("ALL", "MARKET"):
            print(f"  {status}  {scope:<6} {check}: {detail}")
    n_pass = sum(1 for c in checks if c[2])
    print(f"  ... {n_pass}/{len(checks)} checks pass (company-level passes not listed)")
    return 0 if errors_ok else 1


if __name__ == "__main__":
    sys.exit(main())
