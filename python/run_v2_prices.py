"""Version 2, V2.4: combine the latest complete price collection into one panel and check it, offline.

Writes the panel to <bulk>/prices/prices_v2.csv.gz (ticker, date, close, adj_close, split) and to data/clean/v2/prices/:
  price_coverage.csv   per rebalance date: resolved members outside excluded sectors, with a usable price, share
  price_flags.csv      tickers whose Yahoo history is not used (ticker now another company's) or looks wrong
  manifest_v2_prices.json
Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml

import v2_prices as vp
import v2_sec as s
import v2_universe as u
from common import PROJECT_ROOT, sha256_file, write_csv

CFG = PROJECT_ROOT / "config" / "v2.yaml"
OUT = PROJECT_ROOT / "data" / "clean" / "v2" / "prices"


def latest_complete(cfg: dict):
    root = s.bulk_root(cfg) / cfg["prices"]["raw_dir_name"]
    colls = sorted(p for p in root.glob("*T*Z") if (p / "complete.json").exists()) if root.exists() else []
    return colls[-1] if colls else None


def panel_path(cfg: dict):
    return s.bulk_root(cfg) / cfg["prices"]["raw_dir_name"] / "prices_v2.csv.gz"


def load_panel(cfg: dict) -> pd.DataFrame:
    return pd.read_csv(panel_path(cfg), dtype={"ticker": str, "date": str})


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    coll = latest_complete(cfg)
    if coll is None:
        print("No complete price collection: run python\\fetch_v2_prices.py first")
        return 1
    man = pd.read_csv(coll / "collection_manifest.csv", dtype=str, keep_default_na=False)
    man = man.drop_duplicates("ticker", keep="last")
    frames = [vp.read_raw(coll / r.file, r.ticker) for r in man.itertuples() if r.ok == "true"]
    panel = pd.concat(frames, ignore_index=True)
    panel = panel[panel["close"].notna() & (panel["close"] > 0)]
    panel.to_csv(panel_path(cfg), index=False, compression="gzip")
    P = vp.Prices(panel)

    from fetch_v2_sec import latest_universe_raw
    raw = latest_universe_raw(cfg)
    by_ticker, _ = u.sec_maps((raw / "company_tickers.json").read_text(encoding="utf-8"), (raw / "cik-lookup-data.txt").read_text(encoding="latin-1"))
    cik_names = u.sec_maps.cik_names
    res = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "v2" / "sec" / "cik_by_date.csv", dtype=str, keep_default_na=False)
    res = res[(res["cik_pit"] != "") & (res["excluded_sector"] != "True") & res["pit_basis"].isin(["v21_cik_annual_report", "edgar_name_annual_report"])]

    flags, cov = [], []
    seen = set()
    for d, g in res.groupby("date"):
        t0 = P.trading_day_on_or_after(d) or P.trading_day_on_or_before(d)
        n_px = n_owner = 0
        for r in g.itertuples():
            ok, why = vp.owner_ok(r.ticker, r.cik_pit, r.security, by_ticker, cik_names)
            if not ok:
                n_owner += 1
                if (r.ticker, r.cik_pit) not in seen:
                    seen.add((r.ticker, r.cik_pit))
                    flags.append({"ticker": r.ticker, "security": r.security, "cik_pit": r.cik_pit, "issue": "history not used", "detail": why})
                continue
            if P.close_as_traded(r.ticker, t0) is not None:
                n_px += 1
        cov.append({"date": d, "trade_date": t0, "members_resolved": len(g), "with_price": n_px, "ticker_reused": n_owner,
                    "price_share": n_px / len(g) if len(g) else 0.0})
    # sanity: daily total-return jumps above 75% (bad data or a ticker change inside the series)
    for t, x in P.by.items():
        a = pd.Series(x["adj"])
        jumps = (a / a.shift(1) - 1).abs()
        big = int((jumps > 0.75).sum())
        if big:
            i = int(jumps.idxmax())
            flags.append({"ticker": t, "security": "", "cik_pit": "", "issue": "large daily move",
                          "detail": f"{big} days with |return| > 75%, largest on {x['dates'][i]}"})
    cov = pd.DataFrame(cov)
    flags = pd.DataFrame(flags, columns=["ticker", "security", "cik_pit", "issue", "detail"])
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(cov, OUT / "price_coverage.csv", ["date"])
    write_csv(flags, OUT / "price_flags.csv", ["issue", "ticker"])

    spy = P.by.get("SPY")
    first_needed = f"{cfg['backtest']['first_year']}-{cfg['backtest']['rebalance_month_day']}"
    nv = P.splits("NVDA")
    april = cov[cov["date"].str[5:] == cfg["backtest"]["rebalance_month_day"]]
    cks = [("P1_spy_complete", bool(spy) and spy["dates"][0] <= first_needed and len(spy["dates"]) > 2000,
            f"SPY {spy['dates'][0]} to {spy['dates'][-1]}, {len(spy['dates'])} days" if spy else "SPY missing", "error"),
           ("P2_price_share_each_date", bool(len(april)) and april["price_share"].min() >= 0.60,
            "usable prices " + ", ".join(f"{d[:7]} {x:.0%}" for d, x in zip(april["date"], april["price_share"]))
            + ("" if len(april) and april["price_share"].min() >= 0.85 else "; below 85% at some dates: the survivorship limit (I-80), reported in the results"), "error"),
           ("P3_reused_tickers_excluded", True, f"{(flags['issue'] == 'history not used').sum()} member tickers whose Yahoo history belongs to another company today (price_flags.csv)", "info"),
           ("P4_large_moves", (flags["issue"] == "large daily move").sum() <= 15,
            f"{(flags['issue'] == 'large daily move').sum()} tickers with a daily total-return move above 75%", "warning"),
           ("P5_known_split", ("2024-06-10", 10.0) in nv, f"NVDA splits in the panel: {nv}", "error")]
    print(f"V2.4 prices from collection {coll.name}: {panel['ticker'].nunique()} tickers, {len(panel):,} rows -> {panel_path(cfg)}")
    for c, ok, dd, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl != 'error' else 'FAIL')}  {c}: {dd}")
    empty = man[man["ok"] == "empty"]["ticker"].tolist()
    print(f"  No Yahoo data for {len(empty)} tickers (mostly companies taken over or delisted; the survivorship limit, I-80): {empty[:12]}")
    m = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "collection": coll.name,
         "panel": str(panel_path(cfg)), "panel_sha256": sha256_file(panel_path(cfg)), "no_data": empty,
         "checks": [{"check": c, "passed": bool(ok), "detail": dd, "level": lvl} for c, ok, dd, lvl in cks]}
    (OUT / "manifest_v2_prices.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
