"""Version 2, V2.2: which SEC filer (CIK) was each S&P 500 member at each rebalance date, and its sector.

V2.1 gave each ticker one CIK, mostly from today's files. That is wrong when a company was replaced by a successor under the
same name or ticker (I-78: in April 2016 'AA' was Alcoa Inc, CIK 4281, not today's Alcoa Corp) and missing for 47 companies
that have left the index (I-79). Here each (date, ticker) gets the CIK that actually filed annual reports then:

  1. the V2.1 CIK, if it filed an annual report (10-K family) in the window before the date (V2-D9);
  2. otherwise the filers whose EDGAR name matches the security's name (or a documented alias, V2-D10), kept only if they
     filed an annual report in the window; one survivor wins; several are broken by an exact name match, then by the ticker
     in EDGAR's own record; still several -> left unresolved and listed, never guessed;
  3. no qualifying filer -> the V2.1 CIK is kept with basis 'no_annual_report_in_window' (the company is then scored only if
     its facts are current, which they will not be).

Sector: today's GICS sector from Wikipedia when the CIK is a current member, else from the SIC code EDGAR holds for that CIK
(approximate, V2-D11, labelled 'sic').
"""
from __future__ import annotations

import gzip
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

import v2_universe as u

FILING_COLUMNS = ["cik", "form", "filing_date", "report_date", "accn"]


# ---------- storage ----------

def bulk_root(cfg: dict) -> Path:
    """Bulk data folder outside OneDrive (V2-D7): $env:NVDA_V2_DATA, else %LOCALAPPDATA%\\nvda-data\\v2."""
    import os
    env = os.environ.get(cfg["storage"]["bulk_root_env"], "").strip()
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(base) / "nvda-data" / "v2"


def sub_path(root: Path, cik: str, page: str = "") -> Path:
    return root / "sec" / "submissions" / (f"{page}.gz" if page else f"CIK{cik}.json.gz")


def facts_path(root: Path, cik: str) -> Path:
    return root / "sec" / "companyfacts" / f"CIK{cik}.json.gz"


def read_gz_json(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


# ---------- submissions ----------

def filings_from(block: dict, cik: str) -> pd.DataFrame:
    """The columnar filing arrays EDGAR uses in 'filings.recent' and in each older page."""
    n = len(block.get("accessionNumber", []))
    df = pd.DataFrame({"cik": [cik] * n, "form": block.get("form", [""] * n), "filing_date": block.get("filingDate", [""] * n),
                       "report_date": block.get("reportDate", [""] * n), "accn": block.get("accessionNumber", [""] * n)},
                      columns=FILING_COLUMNS)
    return df.fillna("").astype(str)        # always text: a filer with no filings must not give a numeric (empty) column


def needs_older_pages(sub: dict, history_from: str) -> list[str]:
    """Names of older submissions pages to fetch: only when 'recent' does not reach back to history_from."""
    recent = sub.get("filings", {}).get("recent", {})
    dates = recent.get("filingDate", [])
    if dates and min(dates) <= history_from:
        return []
    return [f["name"] for f in sub.get("filings", {}).get("files", []) if f.get("filingTo", "9999") >= history_from]


def load_submissions(root: Path, cik: str) -> tuple[dict, pd.DataFrame] | None:
    p = sub_path(root, cik)
    if not p.exists():
        return None
    sub = read_gz_json(p)
    frames = [filings_from(sub.get("filings", {}).get("recent", {}), cik)]
    for f in sub.get("filings", {}).get("files", []):
        q = sub_path(root, cik, f["name"])
        if q.exists():
            frames.append(filings_from(read_gz_json(q), cik))
    former = [(str(f.get("from") or "")[:10], str(f.get("to") or "")[:10] or "9999-12-31", edgar_norm(f.get("name", "")))
              for f in sub.get("formerNames", []) or []]
    since = max((t for _, t, _ in former), default="")
    meta = {"cik": cik, "name": sub.get("name", ""), "sic": str(sub.get("sic") or ""), "sic_description": sub.get("sicDescription", ""),
            "tickers": [t.upper() for t in sub.get("tickers", []) or []],
            "former_names": [n for _, _, n in former],
            "name_history": former + [(since, "9999-12-31", edgar_norm(sub.get("name", "")))]}
    return meta, pd.concat(frames, ignore_index=True).fillna("").astype(str).drop_duplicates("accn")


def months_before(d: str, months: int) -> str:
    y, m, day = (int(x) for x in d.split("-"))
    m -= months
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, min(day, 28)).isoformat()


def annual_in_window(filings: pd.DataFrame, d: str, cfg: dict) -> bool:
    lo = months_before(d, cfg["sec"]["ten_k_window_months"])
    f = filings[filings["form"].isin(cfg["sec"]["annual_forms"])]
    return bool(((f["filing_date"] >= lo) & (f["filing_date"] < d)).any())


# ---------- names, deregistration, candidates ----------

_STATE_TAG = re.compile(r"\s*/\s*[A-Z]{0,4}\s*/?\s*$")


def edgar_norm(name: str) -> str:
    """EDGAR filer name normalised for matching: the state or 'NEW' tag EDGAR appends to tell filers apart is dropped
    ('AETNA INC /PA/' -> 'AETNA', 'CELGENE CORP /DE/' -> 'CELGENE', 'RAYTHEON CO/' -> 'RAYTHEON')."""
    return u.norm_name(_STATE_TAG.sub("", (name or "").upper()).replace(".", ""))      # 'MYLAN N.V.' -> 'MYLAN'




def names_at(meta: dict, d: str) -> set:
    """The filer's EDGAR name(s) in effect on d, from EDGAR's dated former names; the current name if none covers d."""
    hist = meta.get("name_history") or [("", "9999-12-31", edgar_norm(meta.get("name", "")))]
    hit = {n for f, t, n in hist if f <= d < t}
    return hit or {hist[-1][2]}


def agree(queries: list[str], names: set) -> bool:
    """A query name and a filer name start alike (spaces ignored; the first 6 letters, or the shorter name's length).
    A short query (under 6 letters: 'FOX', 'DOW', 'AMCOR') must equal the filer's name exactly, so 'Fox Corporation' does not
    match Fox Factory and 'Amcor' does not match Amcor Flexibles North America (the former Bemis)."""
    for q in queries:
        a = edgar_norm(q).replace(" ", "")
        for n in names:
            b = n.replace(" ", "")
            if len(a) < 6:
                if a and a == b:
                    return True
                continue
            k = min(len(a), len(b), 6)
            if k >= 3 and a[:k] == b[:k]:
                return True
    return False


def queries(security: str, aliases: dict, ticker: str = "") -> list[str]:
    """The security's name plus any EDGAR names it is also searched under (V2-D10), keyed by security name or by ticker
    (for two tickers that share a Wikipedia name, DD and DWDP); an alias adds, never replaces."""
    out = [security]
    for key in (security, ticker):
        a = aliases.get(key, []) if key else []
        out += [a] if isinstance(a, str) else list(a)
    return out


PERIODIC = ("10-Q", "10-K", "10-KT", "20-F", "40-F", "6-K", "8-K")


def deregistered(filings: pd.DataFrame, d: str, cfg: dict) -> bool:
    """True when the filer had stopped reporting before d: a Form 15 filed after its last annual report before d, and no
    periodic report (10-Q, 10-K, 8-K and the like) ever filed after that Form 15 (the old Broadcom Corp, Allergan Inc,
    Bemis after their takeovers). Large companies also file Form 15 to deregister one bond issue and keep reporting; their
    next 10-Q may fall after d, so EDGAR's whole filing history is read here. This decides only who the filer was; no figure
    filed after d is used anywhere."""
    lo = months_before(d, cfg["sec"]["ten_k_window_months"])
    f = filings[(filings["filing_date"] >= lo) & (filings["filing_date"] < d)]
    ann = f[f["form"].isin(cfg["sec"]["annual_forms"])]["filing_date"]
    if ann.empty:
        return False
    f15 = f[f["form"].str.startswith("15-") & (f["filing_date"] >= ann.max())]["filing_date"]
    if f15.empty:
        return False
    later = filings[filings["form"].isin(PERIODIC) & (filings["filing_date"] > f15.max())]
    return later.empty


def name_candidates(security: str, by_name: dict, keys: list[str], cik_names: dict, aliases: dict, cap: int, ticker: str = "") -> list[str]:
    """Filers whose EDGAR name (any name they ever filed under) equals or starts with the security's name or an alias,
    exact matches first, then the shortest names; at most cap. Names only: the tests in resolve() decide."""
    qs = queries(security, aliases, ticker)
    found = set().union(*(u.name_ciks(q, by_name, keys) for q in qs))
    targets = {edgar_norm(q) for q in qs}

    def rank(c):
        names = cik_names.get(c, set())
        return (0 if targets & names else 1, min((len(n) for n in names), default=99), c)
    return sorted(found, key=rank)[:cap]


def v1_chains(path) -> dict:
    """Version 1's verified registrant chains (config/universe.yaml, M2-D1): ticker -> [current CIK, predecessors...]."""
    import yaml
    if not Path(path).exists():
        return {}
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {t: [c["cik"]] + [p["cik"] for p in c.get("predecessors", []) or []] for t, c in cfg.get("companies", {}).items() if c.get("predecessors")}


def resolve(mem: pd.DataFrame, subs: dict, cands: dict, cik_names: dict, cfg: dict, chains: dict | None = None) -> pd.DataFrame:
    """One row per (date, ticker): cik_pit, pit_basis, name_at_date, name_agrees, n_qualifying, note (V2-D9).
    subs: cik -> (meta, filings). chains: Version 1's verified registrant chains, used instead of name search."""
    aliases = cfg["sec"].get("name_aliases", {}) or {}
    chains = chains or {}
    rows = []
    for r in mem.itertuples(index=False):
        d, mapped = r.date, (r.cik if isinstance(r.cik, str) else "")
        qs = queries(r.security, aliases, r.ticker)
        qualify = lambda c: c in subs and annual_in_window(subs[c][1], d, cfg) and not deregistered(subs[c][1], d, cfg)  # noqa: E731
        at = lambda c: names_at(subs[c][0], d) if c in subs else set()                                                   # noqa: E731
        cand_ok = lambda c: qualify(c) and agree(qs, at(c))                                                              # noqa: E731
        row = {"date": d, "ticker": r.ticker, "security": r.security, "cik_v21": mapped, "cik_basis_v21": r.cik_basis,
               "cik_pit": "", "pit_basis": "", "name_at_date": "", "name_agrees": False, "n_qualifying": 0, "note": ""}

        def pick(q):
            if len(q) > 1:
                targets = {edgar_norm(x) for x in qs}
                exact = [c for c in q if targets & at(c)]
                q = exact or q
            if len(q) > 1:
                tick = [c for c in q if r.ticker.upper().replace(".", "-") in subs[c][0]["tickers"]]
                q = tick or q
            return q

        if r.ticker in chains:
            q = [c for c in chains[r.ticker] if c in subs and annual_in_window(subs[c][1], d, cfg)]   # verified in V1: no name or Form 15 test
            if q:
                row.update(cik_pit=q[0], pit_basis="v21_cik_annual_report" if q[0] == mapped else "v1_verified_chain", n_qualifying=len(q))
            else:
                row.update(cik_pit=mapped, pit_basis="no_annual_report_in_window", note="no filer in Version 1's chain reported in the window")
        elif mapped and qualify(mapped) and agree(qs, at(mapped)):
            row.update(cik_pit=mapped, pit_basis="v21_cik_annual_report", n_qualifying=1)
        elif mapped and qualify(mapped):
            alt = pick([c for c in cands.get(r.ticker, []) if c != mapped and cand_ok(c)])
            then = " / ".join(sorted(at(mapped)))
            if len(alt) == 1:
                row.update(cik_pit=alt[0], pit_basis="edgar_name_annual_report", n_qualifying=2,
                           note=f"V2.1 CIK {mapped} filed then as {then}, another company")
            else:
                row.update(cik_pit=mapped, pit_basis="v21_cik_annual_report", n_qualifying=1,
                           note=f"filed then as {then} (renamed since)" + (f"; other filers qualify: {' '.join(alt[:4])}" if alt else ""))
        else:
            q = [c for c in cands.get(r.ticker, []) if c != mapped and cand_ok(c)]
            row["n_qualifying"] = len(q)
            q = pick(q)
            if len(q) == 1:
                row.update(cik_pit=q[0], pit_basis="edgar_name_annual_report",
                           note=f"V2.1 CIK {mapped or 'none'} had no annual report in the window")
            elif len(q) > 1:
                row.update(pit_basis="ambiguous", note="several filers qualify: " + " ".join(q[:6]))
            elif mapped:
                row.update(cik_pit=mapped, pit_basis="no_annual_report_in_window",
                           note="kept the V2.1 CIK; no candidate reported in the window under a matching name")
            else:
                row.update(pit_basis="unresolved", note="no EDGAR filer found for this name")
        if row["cik_pit"] in subs:
            row["name_at_date"] = " / ".join(sorted(at(row["cik_pit"])))
            row["name_agrees"] = agree(qs, at(row["cik_pit"]))
        rows.append(row)
    out = pd.DataFrame(rows)
    # a tie is broken only by the same ticker's own filer at its other dates (continuity), never by a guess
    good = out[out["pit_basis"].isin(["v21_cik_annual_report", "edgar_name_annual_report", "v1_verified_chain"])]
    own = good.groupby("ticker")["cik_pit"].apply(set).to_dict()
    for i in out.index[out["pit_basis"] == "ambiguous"]:
        listed = out.at[i, "note"].split(": ", 1)[1].split()
        hit = [c for c in listed if c in own.get(out.at[i, "ticker"], set())]
        if len(hit) == 1:
            out.loc[i, ["cik_pit", "pit_basis"]] = [hit[0], "edgar_name_annual_report"]
            out.at[i, "note"] += f"; tie broken by the filer this ticker has at its other dates ({hit[0]})"
            if hit[0] in subs:
                d = out.at[i, "date"]
                out.at[i, "name_at_date"] = " / ".join(sorted(names_at(subs[hit[0]][0], d)))
                out.at[i, "name_agrees"] = agree(queries(out.at[i, "security"], aliases, out.at[i, "ticker"]), names_at(subs[hit[0]][0], d))
    return out


# ---------- sectors ----------

def sic_sector(sic: str, table: list) -> str:
    if not re.fullmatch(r"\d{3,4}", str(sic or "")):
        return ""
    n = int(sic)
    for lo, hi, sector in table:
        if lo <= n <= hi:
            return sector
    return ""


def sectors(res: pd.DataFrame, cur: pd.DataFrame, subs: dict, cfg: dict) -> pd.DataFrame:
    """sector and sector_basis for each (date, ticker): Wikipedia GICS when the CIK (or ticker) is a current member,
    otherwise the SIC mapping."""
    by_cik = dict(zip(cur["cik"], cur["sector"]))
    by_tic = dict(zip(cur["ticker"], cur["sector"]))
    sec, basis = [], []
    for r in res.itertuples(index=False):
        s = by_cik.get(r.cik_pit, "")
        if not s and r.cik_pit == r.cik_v21 and r.ticker in by_tic:
            s = by_tic[r.ticker]
        if s:
            sec.append(s)
            basis.append("wikipedia_gics")
            continue
        sic = subs[r.cik_pit][0]["sic"] if r.cik_pit in subs else ""
        s = sic_sector(sic, cfg["sec"]["sic_sectors"])
        sec.append(s)
        basis.append(f"sic {sic}" if s else ("sic missing" if not sic else f"sic {sic} unmapped"))
    out = res.copy()
    out["sector"], out["sector_basis"] = sec, basis
    out["excluded_sector"] = out["sector"].isin(cfg["sectors"]["excluded"])
    return out


def sic_check(cur: pd.DataFrame, subs: dict, cfg: dict) -> tuple[float, pd.DataFrame]:
    """Check S4: how often the SIC mapping gives today's GICS sector for current members (it is used only for others)."""
    rows = []
    for t, c, s in zip(cur["ticker"], cur["cik"], cur["sector"]):
        if c in subs:
            m = sic_sector(subs[c][0]["sic"], cfg["sec"]["sic_sectors"])
            rows.append({"ticker": t, "cik": c, "gics": s, "sic": subs[c][0]["sic"], "sic_sector": m, "agree": m == s})
    df = pd.DataFrame(rows)
    return (float(df["agree"].mean()) if len(df) else 0.0), df
