"""Version 2, V2.1: download the S&P 500 universe sources, saved exactly as received with a manifest.

  - Wikipedia "List of S&P 500 companies" (rendered HTML): current constituents with GICS sector and CIK
  - Wikipedia "Historical components of the S&P 500" (rendered HTML): dated additions and removals, used to rebuild past
    membership (V2-D1); the history moved off the main page in 2026 (I-75)
  - SEC company_tickers.json: current ticker -> CIK
  - SEC cik-lookup-data.txt: every EDGAR filer name -> CIK, to find CIKs of companies that have left the index

Usage (project folder, project venv; needs the network):
  $env:SEC_USER_AGENT = "Your Name your-email@example.com"
  & $vpy python\\fetch_v2_universe.py
Writes data\\raw\\v2\\universe\\<collection_id>\\ (git-ignored). Nothing is parsed here; run_v2_universe.py does that.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

from common import PROJECT_ROOT, sha256_bytes

CFG = PROJECT_ROOT / "config" / "v2.yaml"
FIELDS = ["source", "url", "http_status", "bytes", "sha256", "file", "ok", "note", "retrieved_at_utc"]


def load_cfg(path: Path = CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get(url: str, headers: dict, tries: int = 4) -> requests.Response | None:
    last = None
    for attempt in range(1, tries + 1):
        time.sleep(0.25)                                        # well inside SEC's 10 requests a second
        try:
            r = requests.get(url, headers=headers, timeout=60)
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


def main(argv=None) -> int:
    cfg = load_cfg()["universe"]
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        print('Set SEC_USER_AGENT first, e.g. $env:SEC_USER_AGENT = "Your Name your-email@example.com"')
        return 1
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    out = PROJECT_ROOT / cfg["raw_dir"] / stamp
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    items = [("wikipedia_sp500", cfg["wikipedia_url"], "sp500_wikipedia.html", {"User-Agent": cfg["wikipedia_user_agent"]}),
             ("wikipedia_history", cfg["history_url"], "sp500_history_wikipedia.html", {"User-Agent": cfg["wikipedia_user_agent"]}),
             ("sec_tickers", cfg["sec_ticker_url"], "company_tickers.json", {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}),
             ("sec_cik_names", cfg["sec_name_url"], "cik-lookup-data.txt", {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"})]
    for source, url, name, headers in items:
        r = get(url, headers)
        row = {k: "" for k in FIELDS}
        row.update(source=source, url=url, retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        if r is None or r.status_code != 200:
            row.update(http_status="no response" if r is None else r.status_code, ok="false", note="download failed")
        else:
            body = r.content
            (out / name).write_bytes(body)
            ok, note = "true", ""
            if name.endswith(".json"):
                try:
                    json.loads(body)
                except ValueError:
                    ok, note = "false", "saved, but not valid JSON"
            if name == "sp500_wikipedia.html" and b'id="constituents"' not in body:
                ok, note = "false", "saved, but no table with id=constituents"
            row.update(http_status=200, bytes=len(body), sha256=sha256_bytes(body),
                       file=(out / name).relative_to(PROJECT_ROOT).as_posix(), ok=ok, note=note)
        rows.append(row)
        print(f"  {'OK  ' if row['ok'] == 'true' else 'FAIL'} {source:<16} {row['bytes'] or ''} bytes {row['note']}")
    with open(out / "collection_manifest.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    info = {"collection_id": stamp, "started_utc": started.isoformat(timespec="seconds"),
            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "python": platform.python_version(),
            "files": sum(r["ok"] == "true" for r in rows)}
    (out / "collection_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    failed = [r for r in rows if r["ok"] != "true"]
    print(f"\nCollection {stamp}: {info['files']}/{len(rows)} files saved in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
