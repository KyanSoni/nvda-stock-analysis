"""Version 2, V2.2 and V2.3: download SEC EDGAR data for every S&P 500 member since 2016, into the bulk data folder.

  submissions   V2.2  filing history (form, filing date) and SIC code for each V2.1 CIK; then, for members whose CIK
                      filed no annual report in the window before a rebalance date (I-78) or that have no CIK (I-79), the
                      same for the EDGAR filers whose names match (v2_sec.name_candidates). Older pages are fetched only
                      when needed. Run run_v2_sec.py afterwards.
  companyfacts  V2.3  XBRL company facts for every filer V2.2 could choose at any date (all sectors). Several
                      hundred files, 1-2 GB unzipped: saved gzip-compressed outside OneDrive (V2-D7).

Files are saved exactly as received (gzip-compressed on disk) with a manifest row (URL, status, bytes, SHA-256 of the bytes
received). Runs are resumable: a file already on disk is skipped unless --refresh is given.

Usage (project folder, project venv; needs the network):
  $env:SEC_USER_AGENT = "Your Name your-email@example.com"
  & $vpy python\\fetch_v2_sec.py submissions
  & $vpy python\\fetch_v2_sec.py companyfacts    (every filer V2.2 could choose; needs only the submissions step)
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

import v2_sec as s
import v2_universe as u
from common import PROJECT_ROOT, sha256_bytes

CFG = PROJECT_ROOT / "config" / "v2.yaml"
FIELDS = ["retrieved_at_utc", "kind", "cik", "url", "http_status", "bytes", "sha256", "file", "ok", "note"]


class Fetcher:
    def __init__(self, cfg: dict, ua: str, refresh: bool = False):
        self.cfg, self.refresh = cfg, refresh
        self.root = s.bulk_root(cfg)
        self.headers = {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}
        self.gap = cfg["sec"]["min_seconds_between_requests"]
        self.last = 0.0
        self.counts = {"fetched": 0, "skipped": 0, "missing": 0, "failed": 0}
        self.man = self.root / "sec" / "manifest.csv"
        self.man.parent.mkdir(parents=True, exist_ok=True)
        if not self.man.exists():
            with open(self.man, "w", encoding="utf-8", newline="") as fh:
                csv.writer(fh, lineterminator="\n").writerow(FIELDS)

    def _get(self, url: str):
        last = None
        for attempt in range(1, 5):
            wait = self.gap - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            try:
                r = requests.get(url, headers=self.headers, timeout=90)
            except requests.RequestException as exc:
                last = str(exc)
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(2 ** attempt * (5 if r.status_code == 429 else 1))
                continue
            return r, ""
        return None, last or "no response"

    def save(self, kind: str, cik: str, url: str, path: Path) -> bool:
        """True when the file is on disk afterwards (fetched now or earlier)."""
        if path.exists() and not self.refresh:
            self.counts["skipped"] += 1
            return True
        r, err = self._get(url)
        row = {k: "" for k in FIELDS}
        row.update(retrieved_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), kind=kind, cik=cik, url=url)
        ok = False
        if r is None:
            row.update(http_status="no response", ok="false", note=err)
            self.counts["failed"] += 1
        elif r.status_code == 404:
            row.update(http_status=404, ok="false", note="not found at SEC (no XBRL facts for this filer)" if kind == "companyfacts" else "not found")
            self.counts["missing"] += 1
        elif r.status_code != 200:
            row.update(http_status=r.status_code, ok="false", note="download failed")
            self.counts["failed"] += 1
        else:
            body = r.content
            try:
                json.loads(body)
            except ValueError:
                row.update(http_status=200, ok="false", note="not valid JSON; not saved")
                self.counts["failed"] += 1
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".part")
                tmp.write_bytes(gzip.compress(body, compresslevel=6))
                tmp.replace(path)
                row.update(http_status=200, bytes=len(body), sha256=sha256_bytes(body), file=path.relative_to(self.root).as_posix(), ok="true")
                self.counts["fetched"] += 1
                ok = True
        with open(self.man, "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n").writerow(row)
        return ok

    def submissions(self, cik: str) -> None:
        p = s.sub_path(self.root, cik)
        if not self.save("submissions", cik, self.cfg["sec"]["submissions_url"].format(cik=cik), p):
            return
        sub = s.read_gz_json(p)
        for name in s.needs_older_pages(sub, self.cfg["sec"]["history_needed_from"]):
            self.save("submissions_page", cik, self.cfg["sec"]["submissions_page_url"].format(name=name), s.sub_path(self.root, cik, name))


def progress(i: int, n: int, f: Fetcher, label: str) -> None:
    if i % 50 == 0 or i == n:
        c = f.counts
        print(f"  {label}: {i}/{n}  fetched {c['fetched']}, already on disk {c['skipped']}, not at SEC {c['missing']}, failed {c['failed']}", flush=True)


def latest_universe_raw(cfg: dict) -> Path:
    raw_root = PROJECT_ROOT / cfg["universe"]["raw_dir"]
    colls = sorted(p for p in raw_root.glob("*T*Z") if (p / "collection_manifest.csv").exists())
    if not colls:
        raise SystemExit(f"No universe collection in {raw_root}: run V2.1 first")
    return colls[-1]


def run_submissions(cfg: dict, f: Fetcher) -> int:
    clean = PROJECT_ROOT / cfg["universe"]["clean_dir"]
    mem = pd.read_csv(clean / "membership.csv", dtype=str, keep_default_na=False)
    chains = s.v1_chains(PROJECT_ROOT / cfg["sec"]["v1_chains"])
    mapped = sorted({c for c in mem["cik"] if c} | {c for v in chains.values() for c in v})
    print(f"Pass 1: submissions for {len(mapped)} V2.1 CIKs and Version 1 predecessors -> {f.root / 'sec' / 'submissions'}")
    for i, cik in enumerate(mapped, 1):
        f.submissions(cik)
        progress(i, len(mapped), f, "pass 1")
    subs = {c: x for c in mapped if (x := s.load_submissions(f.root, c))}
    first = s.resolve(mem, subs, {}, {}, cfg, chains)
    need = first[first["pit_basis"].isin(["no_annual_report_in_window", "unresolved"])
                 | ((first["pit_basis"] == "v21_cik_annual_report") & ~first["name_agrees"])].drop_duplicates("ticker")
    raw = latest_universe_raw(cfg)
    _, by_name = u.sec_maps((raw / "company_tickers.json").read_text(encoding="utf-8"), (raw / "cik-lookup-data.txt").read_text(encoding="latin-1"))
    keys = sorted(by_name)
    cik_names = u.sec_maps.cik_names
    aliases = cfg["sec"].get("name_aliases", {}) or {}
    cands = {r.ticker: s.name_candidates(r.security, by_name, keys, cik_names, aliases, cfg["sec"]["max_name_candidates"], r.ticker) for r in need.itertuples()}
    extra = sorted({c for v in cands.values() for c in v} - set(mapped))
    print(f"Pass 2: {len(need)} companies need a name search at some date (no V2.1 filer then, or it filed under another name); "
          f"submissions for {len(extra)} name-matched candidate filers")
    for i, cik in enumerate(extra, 1):
        f.submissions(cik)
        progress(i, len(extra), f, "pass 2")
    (f.root / "sec" / "candidates.json").write_text(json.dumps(cands, indent=1, sort_keys=True), encoding="utf-8")
    print(f"Candidates saved: {f.root / 'sec' / 'candidates.json'}")
    return 0 if f.counts["failed"] == 0 else 1


def facts_wanted(cfg: dict, root) -> list[str]:
    """Every filer V2.2 could pick at any date: the V2.1 CIKs, Version 1's predecessors and every name-matched candidate,
    kept if it filed an annual report since history_needed_from. Wider than today's matches on purpose, so a later change to
    the matching rules never needs another download."""
    clean = PROJECT_ROOT / cfg["universe"]["clean_dir"]
    mem = pd.read_csv(clean / "membership.csv", dtype=str, keep_default_na=False)
    chains = s.v1_chains(PROJECT_ROOT / cfg["sec"]["v1_chains"])
    cpath = root / "sec" / "candidates.json"
    cands = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    pool = {c for c in mem["cik"] if c} | {c for v in chains.values() for c in v} | {c for v in cands.values() for c in v}
    out = []
    for c in sorted(pool):
        x = s.load_submissions(root, c)
        if x is None:
            continue
        f = x[1]
        if ((f["form"].isin(cfg["sec"]["annual_forms"])) & (f["filing_date"] >= cfg["sec"]["history_needed_from"])).any():
            out.append(c)
    return out


def run_companyfacts(cfg: dict, f: Fetcher) -> int:
    ciks = facts_wanted(cfg, f.root)
    print(f"Company facts for {len(ciks)} filers (every filer V2.2 could choose, all sectors) -> {f.root / 'sec' / 'companyfacts'}")
    for i, cik in enumerate(ciks, 1):
        f.save("companyfacts", cik, cfg["sec"]["companyfacts_url"].format(cik=cik), s.facts_path(f.root, cik))
        progress(i, len(ciks), f, "companyfacts")
    return 0 if f.counts["failed"] == 0 else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("submissions", "companyfacts"):
        print(__doc__)
        return 1
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        print('Set SEC_USER_AGENT first, e.g. $env:SEC_USER_AGENT = "Your Name your-email@example.com"')
        return 1
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    f = Fetcher(cfg, ua, refresh="--refresh" in argv)
    t0 = time.monotonic()
    code = run_submissions(cfg, f) if argv[0] == "submissions" else run_companyfacts(cfg, f)
    c = f.counts
    print(f"\nDone in {time.monotonic() - t0:,.0f}s: fetched {c['fetched']}, already on disk {c['skipped']}, "
          f"not at SEC {c['missing']}, failed {c['failed']}. Manifest: {f.man}")
    if c["failed"]:
        print("Some downloads failed: run the same command again; files already saved are skipped.")
    return code


if __name__ == "__main__":
    sys.exit(main())
