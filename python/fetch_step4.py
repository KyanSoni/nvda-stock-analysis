"""Step 4 data collection: snapshot the analyst consensus estimates (S4-D1, decision D13).

For each company in config/universe.yaml it saves, exactly as yfinance returns them, Yahoo Finance's consensus
EPS estimates (Ticker.earnings_estimate) and revenue estimates (Ticker.revenue_estimate) into a new dated folder
data/raw/estimates/<UTC timestamp>/, with a manifest row per file (bytes, SHA-256, ok flag). Nothing is parsed here.

Usage (project folder, project venv):
  & $vpy python\\fetch_step4.py
Exit code 0 = EPS estimates saved for every company; 1 = something is missing (see the summary).
"""
from __future__ import annotations

import csv
import io
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import yaml

from common import PROJECT_ROOT, sha256_bytes

SCORECARD = PROJECT_ROOT / "config" / "scorecard.yaml"
FIELDS = ["retrieved_at_utc", "ticker", "kind", "attribute", "rows", "bytes", "sha256", "file", "required", "ok", "note"]
KINDS = {"eps": ("earnings_estimate", True), "revenue": ("revenue_estimate", False)}


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "not installed"


def main() -> int:
    import yfinance as yf
    from run_step2 import load_universe
    uni = load_universe()
    sc = yaml.safe_load(open(SCORECARD, encoding="utf-8"))
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    out = PROJECT_ROOT / sc["estimates"]["raw_dir"] / stamp
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for ticker in uni["companies"]:
        t = yf.Ticker(ticker)
        for kind, (attr, required) in KINDS.items():
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            rel = f"{kind}_{ticker}.csv"
            try:
                df = getattr(t, attr)
                if df is None or len(df) == 0:
                    raise ValueError("empty result")
                buf = io.StringIO()
                df.to_csv(buf, lineterminator="\n")
                data = buf.getvalue().encode("utf-8")
                (out / rel).write_bytes(data)
                rows.append([now, ticker, kind, attr, len(df), len(data), sha256_bytes(data), rel, required, True, ""])
            except Exception as exc:  # noqa: BLE001 - every failure is recorded, nothing is retried silently
                rows.append([now, ticker, kind, attr, 0, 0, "", "", required, False, f"{type(exc).__name__}: {exc}"])
    with open(out / "estimates_manifest.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(FIELDS)
        w.writerows(rows)
    info = {"started_utc": started.isoformat(timespec="seconds"), "python": platform.python_version(),
            "yfinance": _version("yfinance"), "pandas": _version("pandas"), "source": sc["estimates"]["source"]}
    (out / "estimates_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    missing = [f"{r[1]} {r[2]} ({r[10]})" for r in rows if r[8] and not r[9]]
    print(f"Estimates snapshot {stamp} -> {out}")
    for r in rows:
        print(f"  {'OK  ' if r[9] else 'FAIL'} {r[1]:<5} {r[2]:<8} rows {r[4]}  {r[10]}")
    print("  all required files saved" if not missing else f"  MISSING: {missing}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
