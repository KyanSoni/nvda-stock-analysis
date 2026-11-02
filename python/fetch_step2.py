"""Step 2 data collection: one run downloads everything Step 2 needs into a new, dated collection folder.

  SEC:    ticker file; submissions and companyfacts for every company and predecessor in config/universe.yaml
  Market: daily prices and corporate actions (yfinance) for the companies and benchmarks; FRED 10-year yield

Every file is saved exactly as received, with a manifest row (URL, status, bytes, SHA-256). Nothing is parsed
or changed here; processing reads only the saved collection, so every later run is reproducible offline.

Usage (project folder, project venv):
  $env:SEC_USER_AGENT = "Your Name your-email@example.com"
  & $vpy python\\fetch_step2.py
  & $vpy python\\fetch_step2.py --add-rates <collection_id>   # add the 10-year yield to an existing collection
Exit code 0 = every required file collected; 1 = something required is missing (see the summary).
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml

from common import PROJECT_ROOT, sha256_bytes, sha256_file

UNIVERSE = PROJECT_ROOT / "config" / "universe.yaml"
NY = ZoneInfo("America/New_York")
MANIFEST_FIELDS = ["retrieved_at_utc", "source", "ticker", "cik", "role", "url", "http_status",
                   "bytes", "sha256", "file", "required", "ok", "note"]


def load_universe(path: Path = UNIVERSE) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return "not installed"


class Collector:
    def __init__(self, uni: dict, root: Path = PROJECT_ROOT, user_agent: str | None = None):
        self.uni = uni
        self.started = datetime.now(timezone.utc)
        self.stamp = self.started.strftime("%Y%m%dT%H%M%SZ")
        self.dir = root / uni["paths"]["collections_dir"] / self.stamp
        if self.dir.exists():
            raise RuntimeError(f"Collection folder already exists: {self.dir}")
        (self.dir / "sec").mkdir(parents=True)
        (self.dir / "market").mkdir(parents=True)
        self.root = root
        self.rows: list[dict] = []
        self.ua = user_agent if user_agent is not None else os.environ.get(uni["sec"]["user_agent_env"], "").strip()

    # ---------- helpers ----------
    def record(self, **kw) -> None:
        row = {k: "" for k in MANIFEST_FIELDS}
        row.update(kw)
        row["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.rows.append(row)
        status = "OK  " if row["ok"] == "true" else ("MISS" if row["required"] != "true" else "FAIL")
        print(f"  {status} {row['source']:<13} {row['ticker']:<5} {row['note'] or row['file']}")

    def _get(self, url: str, headers: dict) -> requests.Response | None:
        sec = self.uni["sec"]
        last = None
        for attempt in range(1, sec["max_retries"] + 1):
            time.sleep(sec["min_seconds_between_requests"])
            try:
                r = requests.get(url, headers=headers, timeout=sec["timeout_seconds"])
            except requests.RequestException as exc:
                last = exc
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(2 ** attempt)
                continue
            return r
        print(f"    request failed after retries: {last}")
        return None

    def download(self, source: str, url: str, rel: str, ticker: str = "", cik: str = "", role: str = "",
                 required: bool = True, headers: dict | None = None, expect_json: bool = True) -> Path | None:
        r = self._get(url, headers or {"User-Agent": self.ua, "Accept-Encoding": "gzip, deflate"})
        base = dict(source=source, ticker=ticker, cik=cik, role=role, url=url, required=str(required).lower())
        if r is None:
            self.record(**base, http_status="no response", ok="false", note="no response")
            return None
        body = r.content
        if r.status_code != 200:
            self.record(**base, http_status=r.status_code, bytes=len(body), ok="false", note=f"HTTP {r.status_code}")
            return None
        path = self.dir / rel
        path.write_bytes(body)
        ok, note = "true", ""
        if expect_json:
            try:
                json.loads(body)
            except ValueError:
                ok, note = "false", "saved, but not valid JSON"
        self.record(**base, http_status=200, bytes=len(body), sha256=sha256_bytes(body),
                    file=path.relative_to(self.root).as_posix(), ok=ok, note=note)
        return path if ok == "true" else None

    # ---------- SEC ----------
    def collect_sec(self) -> None:
        sec = self.uni["sec"]
        print("SEC")
        self.download("ticker_file", sec["ticker_file_url"], "sec/company_tickers.json")
        for ticker, spec in self.uni["companies"].items():
            entities = [(spec["cik"], spec.get("role", "peer"), True)]
            entities += [(p["cik"], "predecessor", False) for p in spec.get("predecessors", [])]
            for cik, role, required in entities:
                for kind, url_key in (("submissions", "submissions_url"), ("companyfacts", "companyfacts_url")):
                    self.download(kind, sec[url_key].format(cik=cik), f"sec/{kind}_CIK{cik}.json",
                                  ticker=ticker, cik=cik, role=role, required=required)

    # ---------- market ----------
    def collect_prices(self) -> None:
        print("Prices (yfinance)")
        try:
            import yfinance as yf
        except ImportError:
            self.record(source="prices", ticker="ALL", required="true", ok="false",
                        note="yfinance is not installed in this venv")
            return
        start = self.uni["market"]["price_start"]
        end_exclusive = (self.started.astimezone(NY).date() + timedelta(days=1)).isoformat()
        symbols = list(self.uni["companies"]) + list(self.uni["benchmarks"])
        for sym in symbols:
            df, err, shares = None, "", ""
            for attempt in range(1, 4):
                try:
                    t = yf.Ticker(sym)
                    df = t.history(start=start, end=end_exclusive, interval="1d", auto_adjust=False, actions=True)
                    if df is not None and len(df):
                        try:
                            shares = str(t.fast_info["shares"])  # cross-check only (M2-D7)
                        except Exception:  # noqa: BLE001 - optional field, never fatal
                            shares = ""
                        break
                    err = "empty response"
                except Exception as exc:  # noqa: BLE001 - yfinance raises many types
                    err = f"{type(exc).__name__}: {exc}"
                time.sleep(3 * attempt)
            url = f"yfinance Ticker('{sym}').history(start={start}, end={end_exclusive}, auto_adjust=False, actions=True)"
            if df is None or not len(df):
                self.record(source="prices", ticker=sym, url=url, required="true", ok="false", note=err or "no data")
                continue
            path = self.dir / "market" / f"prices_{sym}.csv"
            df.to_csv(path, index_label="Date", lineterminator="\n")
            note = f"{len(df)} rows {df.index.min().date()} to {df.index.max().date()}; yfinance shares={shares or 'n/a'}"
            self.record(source="prices", ticker=sym, url=url, http_status="", bytes=path.stat().st_size,
                        sha256=sha256_file(path), file=path.relative_to(self.root).as_posix(),
                        required="true", ok="true", note=note)

    def collect_fred(self) -> None:
        print("FRED")
        series = self.uni["market"]["fred_series"]
        url = self.uni["market"]["fred_url"].format(series=series)
        self.download("fred", url, f"market/fred_{series}.csv", ticker=series,
                      headers={"User-Agent": "nvda-stock-analysis (research)"}, expect_json=False)

    # ---------- finish ----------
    def finish(self) -> int:
        with open(self.dir / "collection_manifest.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(self.rows)
        finished = datetime.now(timezone.utc)
        info = {
            "collection_id": self.stamp,
            "started_utc": self.started.isoformat(timespec="seconds"),
            "finished_utc": finished.isoformat(timespec="seconds"),
            "started_new_york": self.started.astimezone(NY).isoformat(timespec="seconds"),
            "python": platform.python_version(),
            "packages": {p: _version(p) for p in ("requests", "pandas", "yfinance", "PyYAML")},
            "universe_sha256": sha256_file(UNIVERSE) if UNIVERSE.exists() else "",
            "files": len([r for r in self.rows if r["ok"] == "true"]),
        }
        with open(self.dir / "collection_info.json", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(info, fh, indent=2)
        failed_required = [r for r in self.rows if r["required"] == "true" and r["ok"] != "true"]
        missing_optional = [r for r in self.rows if r["required"] != "true" and r["ok"] != "true"]
        print(f"\nCollection {self.stamp}: {info['files']} files saved in {self.dir}")
        print(f"Required items failed: {len(failed_required)}   optional items missing: {len(missing_optional)}")
        for r in failed_required:
            print(f"  REQUIRED FAILED: {r['source']} {r['ticker']} {r['cik']} - {r['note']}")
        return 0 if not failed_required else 1


def add_rates(uni: dict, collection_id: str, root: Path = PROJECT_ROOT) -> int:
    """Add the 10-year yield to an existing collection (used when FRED timed out during the main run).
    Tries FRED DGS10 (longer timeout), then the US Treasury daily par yield file for the collection year."""
    coll = root / uni["paths"]["collections_dir"] / collection_id
    if not (coll / "collection_manifest.csv").exists():
        print(f"No collection {collection_id}")
        return 2
    info = json.loads((coll / "collection_info.json").read_text(encoding="utf-8"))
    c = Collector.__new__(Collector)
    c.uni, c.root, c.dir, c.rows, c.ua = uni, root, coll, [], ""
    c.started = datetime.fromisoformat(info["started_utc"])
    c.uni = json.loads(json.dumps(uni))
    c.uni["sec"]["timeout_seconds"] = 120
    print(f"Adding 10-year yield to collection {collection_id}")
    series = uni["market"]["fred_series"]
    got = c.download("fred", uni["market"]["fred_url"].format(series=series), f"market/fred_{series}.csv",
                     ticker=series, headers={"User-Agent": "nvda-stock-analysis (research)"}, expect_json=False)
    if got is None:
        year = c.started.astimezone(NY).year
        years = [year - 1, year] if c.started.astimezone(NY).month == 1 else [year]
        for y in years:
            c.download("treasury", uni["market"]["treasury_url"].format(year=y), f"market/treasury_par_yield_{y}.csv",
                       ticker="10Y", headers={"User-Agent": "Mozilla/5.0 (research)"}, expect_json=False)
    ok = [r for r in c.rows if r["ok"] == "true"]
    with open(coll / "collection_manifest.csv", "a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        for r in c.rows:
            r["note"] = (r["note"] + " " if r["note"] else "") + "added by --add-rates"
            r["required"] = "true" if r in ok else "false"
            w.writerow(r)
    info.setdefault("additions", []).append({"added_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                             "files": [r["file"] for r in ok]})
    with open(coll / "collection_info.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(info, fh, indent=2)
    print(f"{len(ok)} rate file(s) added" if ok else "No rate source responded: try again later")
    return 0 if ok else 1


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--add-rates":
        return add_rates(load_universe(), sys.argv[2])
    uni = load_universe()
    ua = os.environ.get(uni["sec"]["user_agent_env"], "").strip()
    if "@" not in ua or '"' in ua:
        print(f"Set {uni['sec']['user_agent_env']} first, e.g. $env:SEC_USER_AGENT = \"Your Name your-email@example.com\"")
        return 2
    c = Collector(uni, user_agent=ua)
    print(f"Collection {c.stamp} -> {c.dir}")
    c.collect_sec()
    c.collect_prices()
    c.collect_fred()
    return c.finish()


if __name__ == "__main__":
    sys.exit(main())
