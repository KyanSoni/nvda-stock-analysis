"""Version 2, V2.5: score and rank the S&P 500 at every rebalance date and today, offline.

Reads cik_by_date.csv (V2.2), the facts file (V2.3) and the price panel (V2.4). Writes data/clean/v2/scores/:
  scores_by_date.csv   one row per company per date: metrics, test points, score, rank, flags and why a company is not ranked
  screener_today.csv   the latest date only (the live screen)
  v1_reconcile.csv     V2 engine vs Version 1 ratios for the six companies, same fiscal year (check C2)
  manifest_v2_scores.json
Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml

import v2_facts as vf
import v2_prices as vp
import v2_score as vs
import v2_universe as u
from common import PROJECT_ROOT, sha256_file, write_csv
from run_v2_facts import load_facts
from run_v2_prices import load_panel

CFG = PROJECT_ROOT / "config" / "v2.yaml"
OUT = PROJECT_ROOT / "data" / "clean" / "v2" / "scores"
SIX = ["NVDA", "AMD", "AVGO", "MRVL", "QCOM", "INTC"]


def reconcile_v1(today: pd.DataFrame, obs_by_cik: dict, P, cfg: dict) -> pd.DataFrame:
    """V2's engine on Version 1's own latest fiscal year for each of the six companies (a later 10-K, such as Qualcomm's
    filed after Version 1 was built, would otherwise compare different years), against Version 1's ratios."""
    path = PROJECT_ROOT / "data" / "clean" / "step3" / "exports" / "v_ratios_annual.csv"
    if not path.exists():
        return pd.DataFrame()
    v1 = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = []
    for t in SIX:
        a = today[today["ticker"] == t]
        b = v1[(v1["ticker"] == t) & (v1["period_end"] != "")]
        if a.empty or b.empty:
            continue
        b = b.sort_values("period_end").iloc[-1]
        d = a.iloc[0]["date"]
        m = vf.metrics(vf.pit(obs_by_cik[a.iloc[0]["cik"]], d, cfg), d, cfg, splits=P.splits(t), fy0_end=b["period_end"])
        for mt in cfg["scores"]["v1_reconcile"]["metrics"]:
            v2v, v1v = m.get(mt), (float(b[mt]) if b[mt] not in ("", None) else None)
            v1v = None if v1v is not None and v1v != v1v else v1v
            both = v1v is not None and v2v is not None
            ok = (both and abs(v1v - v2v) <= cfg["scores"]["v1_reconcile"]["abs_tol"]) or (v1v is None and v2v is None)
            rows.append({"ticker": t, "fy_end": b["period_end"], "metric": mt, "v1": v1v, "v2": v2v, "diff": (v2v - v1v) if both else None,
                         "agree": bool(ok), "note": "; ".join(m["flags"]) if not ok else ""})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    res = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "v2" / "sec" / "cik_by_date.csv", dtype=str, keep_default_na=False)
    res = res[(res["cik_pit"] != "") & (res["excluded_sector"] != "True") & res["pit_basis"].isin(["v21_cik_annual_report", "edgar_name_annual_report"])]
    print("Loading facts and prices ...", flush=True)
    obs = load_facts(cfg)
    obs_by_cik = {c: vf.prepare(g, cfg) for c, g in obs.groupby("cik")}
    P = vp.Prices(load_panel(cfg))
    from fetch_v2_sec import latest_universe_raw
    raw = latest_universe_raw(cfg)
    by_ticker, _ = u.sec_maps((raw / "company_tickers.json").read_text(encoding="utf-8"), (raw / "cik-lookup-data.txt").read_text(encoding="latin-1"))
    cik_names = u.sec_maps.cik_names
    frames = []
    for d, g in res.groupby("date"):
        df = vs.score_date(d, g, obs_by_cik, P, by_ticker, cik_names, cfg)
        frames.append(df)
        top = df[pd.to_numeric(df["rank"]) <= 5]["ticker"].tolist()
        print(f"  {d}: {len(df)} companies, {int(df['ranked'].sum())} ranked; top 5 {top}", flush=True)
    allr = pd.concat(frames, ignore_index=True)
    latest = allr["date"].max()
    today = allr[allr["date"] == latest]
    rec = reconcile_v1(today, obs_by_cik, P, cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(allr, OUT / "scores_by_date.csv", ["date", "rank", "ticker"])
    write_csv(today, OUT / "screener_today.csv", ["rank", "ticker"])
    if len(rec):
        write_csv(rec, OUT / "v1_reconcile.csv", ["ticker", "metric"])

    md = cfg["backtest"]["rebalance_month_day"]
    april = allr[allr["date"].str[5:] == md].groupby("date")["ranked"].sum()
    look = allr[(allr["fy0_filed"] != "") & (allr["fy0_filed"] >= allr["date"])]
    share = rec["agree"].mean() if len(rec) else 0.0
    nv = today[today["ticker"] == "NVDA"]
    hold = cfg["backtest"]["holdings"]
    cks = [("C1_ranked_each_april", april.min() >= 150 if len(april) else False,
            "ranked companies " + ", ".join(f"{d[:4]} {int(n)}" for d, n in april.items()), "error"),
           ("C2_matches_version1", len(rec) > 0 and share >= cfg["scores"]["v1_reconcile"]["min_share_agreeing"],
            f"{int(rec['agree'].sum()) if len(rec) else 0}/{len(rec)} metric values for the six companies within "
            f"{cfg['scores']['v1_reconcile']['abs_tol']} of Version 1 ({share:.0%}); every difference is in v1_reconcile.csv", "error"),
           ("C3_no_lookahead", look.empty, f"{len(look)} rows use a filing dated on or after the rebalance date", "error"),
           ("C4_enough_for_portfolio", bool(len(april)) and april.min() >= max(cfg["robustness"]["holdings"]),
            f"at least {max(cfg['robustness']['holdings'])} ranked at every April date (needed for N=50)", "error"),
           ("C5_nvidia_scored_today", len(nv) == 1 and bool(nv.iloc[0]["ranked"]),
            (f"NVDA {nv.iloc[0]['score_total']:.1f}/18 points ({int(nv.iloc[0]['tests_scored'])} tests scored), rank {int(nv.iloc[0]['rank'])} of {int(today['ranked'].sum())} on {latest}"
             if len(nv) and nv.iloc[0]["ranked"] else "NVDA not ranked today"), "warning")]
    print(f"V2.5 scores -> {OUT}")
    for c, ok, d, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl != 'error' else 'FAIL')}  {c}: {d}")
    print(f"  Today's top {hold} ({latest}): " + ", ".join(today[pd.to_numeric(today["rank"]) <= hold]["ticker"]))
    why = allr[~allr["ranked"]]["why_not_ranked"].str.replace(r"only \d+ tests scored", "too few tests scored", regex=True).value_counts()
    print("  Not ranked (company-dates): " + ", ".join(f"{k} {v}" for k, v in why.items()))
    m = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dates": sorted(allr["date"].unique().tolist()),
         "output_sha256": {f: sha256_file(OUT / f) for f in ("scores_by_date.csv", "screener_today.csv")},
         "checks": [{"check": c, "passed": bool(ok), "detail": d, "level": lvl} for c, ok, d, lvl in cks]}
    (OUT / "manifest_v2_scores.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
