"""Version 2, V2.4: download daily prices and splits from Yahoo Finance (yfinance) for every company V2.2 resolved, and SPY.

Each ticker is saved exactly as yfinance returns it (Ticker.history(auto_adjust=False, actions=True): Open, High, Low, Close,
Adj Close, Volume, Dividends, Stock Splits) in a dated collection folder in the bulk data folder (V2-D7), with a manifest.
Yahoo no longer serves most companies that were taken over or delisted; those come back empty and are recorded as such
(the survivorship limit, I-80). Resumable: an unfinished collection is continued, tickers already saved are skipped.

Usage (project folder, project venv; needs the network):
  & $vpy python\\fetch_v2_prices.py            # continue the latest unfinished collection, or start a new one
  & $vpy python\\fetch_v2_prices.py --new      # always start a new collection
Then: & $vpy python\\run_v2_prices.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

import v2_sec as s
from common import PROJECT_ROOT, sha256_file

CFG = PROJECT_ROOT / "config" / "v2.yaml"
FIELDS = ["retrieved_at_utc", "ticker", "yahoo_symbol", "rows", "first_date", "last_date", "bytes", "sha256", "file", "ok", "note"]


def yahoo_symbol(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def tickers_needed(cfg: dict) -> list[str]:
    """Every ticker that was ever a member (all sectors), and SPY: independent of the V2.2 matching."""
    mem = pd.read_csv(PROJECT_ROOT / cfg["universe"]["clean_dir"] / "membership.csv", dtype=str, keep_default_na=False)
    return sorted(set(mem["ticker"]) | set(cfg["prices"]["extra_symbols"]))


def collection_dir(cfg: dict, new: bool) -> Path:
    root = s.bulk_root(cfg) / cfg["prices"]["raw_dir_name"]
    root.mkdir(parents=True, exist_ok=True)
    open_ = sorted(p for p in root.glob("*T*Z") if p.is_dir() and not (p / "complete.json").exists())
    if open_ and not new:
        return open_[-1]
    d = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d.mkdir()
    return d


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    try:
        import yfinance as yf
    except ImportError:
        print("yfinance is not installed in this venv: & $vpy -m pip install yfinance")
        return 1
    out = collection_dir(cfg, "--new" in argv)
    man = out / "collection_manifest.csv"
    done = set()
    if man.exists():
        done = {r["ticker"] for r in csv.DictReader(open(man, encoding="utf-8")) if r["ok"] in ("true", "empty")}
    else:
        with open(man, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh, lineterminator="\n").writerow(FIELDS)
    tickers = tickers_needed(cfg)
    todo = [t for t in tickers if t not in done]
    start = cfg["prices"]["start"]
    end_excl = (date.today() + timedelta(days=1)).isoformat()
    print(f"Prices {start} to today for {len(tickers)} tickers ({len(done)} already saved) -> {out}")
    n_ok = n_empty = n_fail = 0
    for i, t in enumerate(todo, 1):
        sym = yahoo_symbol(t)
        row = {k: "" for k in FIELDS}
        row.update(retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), ticker=t, yahoo_symbol=sym)
        df, err = None, ""
        for attempt in range(1, 4):
            time.sleep(cfg["prices"]["seconds_between_requests"])
            try:
                df = yf.Ticker(sym).history(start=start, end=end_excl, interval="1d", auto_adjust=False, actions=True)
                break
            except Exception as exc:  # noqa: BLE001 - yfinance raises many types
                err = f"{type(exc).__name__}: {exc}"[:200]
                time.sleep(3 * attempt)
        if df is None:
            row.update(ok="false", note=err or "no response")
            n_fail += 1
        elif df.empty:
            row.update(ok="empty", rows=0, note="Yahoo returned no rows (delisted, renamed or never listed under this symbol)")
            n_empty += 1
        else:
            path = out / f"prices_{t}.csv"
            df.to_csv(path)
            row.update(ok="true", rows=len(df), first_date=str(df.index.min().date()), last_date=str(df.index.max().date()),
                       bytes=path.stat().st_size, sha256=sha256_file(path), file=path.name)
            n_ok += 1
        with open(man, "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n").writerow(row)
        if i % 50 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}: saved {n_ok}, empty {n_empty}, failed {n_fail}", flush=True)
    rows = list(csv.DictReader(open(man, encoding="utf-8")))
    failed = [r["ticker"] for r in rows if r["ok"] == "false" and r["ticker"] not in {x["ticker"] for x in rows if x["ok"] in ("true", "empty")}]
    if failed:
        print(f"\n{len(failed)} tickers failed (e.g. {failed[:8]}): run the same command again to retry them.")
        return 1
    info = {"collection_id": out.name, "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tickers": len(tickers), "with_rows": sum(r["ok"] == "true" for r in rows), "empty": sum(r["ok"] == "empty" for r in rows),
            "yfinance": getattr(yf, "__version__", "unknown")}
    (out / "complete.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"\nCollection {out.name} complete: {info['with_rows']} tickers with prices, {info['empty']} empty.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
