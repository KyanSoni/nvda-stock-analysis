"""Step 4a: parse a saved estimates snapshot (data/raw/estimates/<id>/) into tidy, provenance-carrying rows.

One row per company, kind (eps / revenue) and Yahoo period (0q, +1q, 0y, +1y). Values are kept as the text
yfinance wrote (no float rounding); the raw file and its SHA-256 travel with every row.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from common import PROJECT_ROOT, sha256_file

SCORECARD = PROJECT_ROOT / "config" / "scorecard.yaml"
COLUMNS = ["ticker", "kind", "period", "avg", "low", "high", "analysts", "year_ago", "growth_reported",
           "fetched_at_utc", "snapshot_id", "raw_file", "raw_sha256"]
SOURCE_COLS = {"avg": "avg", "low": "low", "high": "high", "analysts": "numberOfAnalysts",
               "year_ago": ("yearAgoEps", "yearAgoRevenue"), "growth_reported": "growth"}


def load_scorecard(path: Path = SCORECARD) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def latest_snapshot(sc: dict, root: Path = PROJECT_ROOT) -> Path:
    base = root / sc["estimates"]["raw_dir"]
    snaps = sorted(p for p in base.glob("*T*Z") if (p / "estimates_manifest.csv").exists()) if base.exists() else []
    if not snaps:
        raise FileNotFoundError(f"No estimates snapshot in {base}: run  python python/fetch_step4.py  first.")
    return snaps[-1]


def _clean(v: str) -> str:
    v = (v or "").strip()
    if v.lower() in ("", "nan", "none"):
        return ""
    try:
        Decimal(v)
    except InvalidOperation:
        return ""
    return v


def parse_snapshot(snap: Path, tickers: list[str]) -> tuple[list[dict], list[str]]:
    """Returns (rows, problems). A problem is anything that would make an estimate unusable."""
    rows, problems = [], []
    with open(snap / "estimates_manifest.csv", encoding="utf-8", newline="") as fh:
        manifest = list(csv.DictReader(fh))
    for m in manifest:
        if m["ok"] != "True":
            if m["required"] == "True":
                problems.append(f"{m['ticker']} {m['kind']}: not collected ({m['note']})")
            continue
        path = snap / m["file"]
        if sha256_file(path) != m["sha256"]:
            problems.append(f"{m['file']}: hash differs from the manifest")
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            data = list(csv.DictReader(fh))
        for r in data:
            period = r.get("period") or r.get("") or ""
            row = {"ticker": m["ticker"], "kind": m["kind"], "period": period, "fetched_at_utc": m["retrieved_at_utc"],
                   "snapshot_id": snap.name, "raw_file": f"{snap.name}/{m['file']}", "raw_sha256": m["sha256"]}
            for out, src in SOURCE_COLS.items():
                srcs = src if isinstance(src, tuple) else (src,)
                row[out] = next((_clean(r[s]) for s in srcs if s in r), "")
            rows.append(row)
    for t in tickers:
        have = {r["period"] for r in rows if r["ticker"] == t and r["kind"] == "eps" and r["avg"]}
        for p in ("0y", "+1y"):
            if p not in have:
                problems.append(f"{t}: no consensus EPS for period {p}")
    return rows, problems


def snapshot_age_ok(rows: list[dict], cutoff: str, max_days: int) -> tuple[bool, str]:
    days = sorted({(datetime.fromisoformat(r["fetched_at_utc"]).date() - date.fromisoformat(cutoff)).days for r in rows})
    ok = bool(days) and days[0] >= 0 and days[-1] <= max_days
    return ok, f"fetched {days[0] if days else '-'} to {days[-1] if days else '-'} days after the cutoff {cutoff} (limit {max_days})"


def write_rows(rows: list[dict], path: Path) -> None:
    from common import write_csv
    import pandas as pd
    write_csv(pd.DataFrame(rows, columns=COLUMNS), path, ["ticker", "kind", "period"])


def snapshot_info(snap: Path) -> dict:
    p = snap / "estimates_info.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
