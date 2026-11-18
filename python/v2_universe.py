"""Version 2, V2.1: parse the universe sources and rebuild S&P 500 membership at each rebalance date (V2-D1).

Membership on date t = today's constituents, with every change dated after t undone (added tickers taken out, removed
tickers put back), newest first. Every company gets a CIK with its basis recorded:
  wikipedia      the CIK column of the constituents table (current members)
  sec_ticker     SEC company_tickers.json, by ticker (dots as dashes: BRK.B -> BRK-B)
  sec_name       SEC cik-lookup-data.txt, exact match on the normalised company name, only when exactly one CIK matches
  unmapped       none of the above; logged for V2.2, never guessed
HTML is parsed with the standard library (no lxml), including rowspan and colspan.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd



class _Tables(HTMLParser):
    """Collect every <table> with an id as a grid of cell texts (rowspan/colspan expanded; <sup> footnotes dropped)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: dict[str, list[list[str]]] = {}
        self.stack: list[dict] = []
        self.cell: list[str] | None = None
        self.span = (1, 1)
        self.sup = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.stack.append({"id": a.get("id", ""), "cls": a.get("class", ""), "rows": [], "row": None})
        elif not self.stack:
            return
        elif tag == "tr":
            self.stack[-1]["row"] = []
        elif tag in ("td", "th"):
            self.cell = []
            self.span = (int(re.sub(r"\D", "", a.get("rowspan", "1")) or 1), int(re.sub(r"\D", "", a.get("colspan", "1")) or 1))
        elif tag == "sup":
            self.sup += 1
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ("td", "th") and self.cell is not None and t["row"] is not None:
            t["row"].append(("".join(self.cell), self.span))
            self.cell = None
        elif tag == "tr" and t["row"] is not None:
            t["rows"].append(t["row"])
            t["row"] = None
        elif tag == "sup":
            self.sup = max(0, self.sup - 1)
        elif tag == "table":
            t = self.stack.pop()
            if "navbox" in t["cls"]:
                return
            key = t["id"] or f"table_{len(self.tables) + 1}"
            self.tables[key] = _grid(t["rows"])

    def handle_data(self, data):
        if self.cell is not None and not self.sup:
            self.cell.append(data)


def _grid(rows):
    out, pending = [], {}            # pending[(row, col)] = text carried down by rowspan
    for r, cells in enumerate(rows):
        line, c = [], 0
        it = iter(cells)
        while True:
            while (r, c) in pending:
                line.append(pending.pop((r, c)))
                c += 1
            nxt = next(it, None)
            if nxt is None:
                break
            text, (rs, cs) = nxt
            text = re.sub(r"\s+", " ", text).strip()
            for k in range(cs):
                line.append(text)
                for d in range(1, rs):
                    pending[(r + d, c + k)] = text
            c += cs
        out.append(line)
    return out


def parse_tables(html: str) -> dict[str, list[list[str]]]:
    p = _Tables()
    p.feed(html)
    return p.tables


def _date(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", s).strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return ""


def constituents(grid: list[list[str]]) -> pd.DataFrame:
    head = [h.lower() for h in grid[0]]
    idx = {k: next(i for i, h in enumerate(head) if h.startswith(k)) for k in ("symbol", "security", "gics sector", "gics sub", "date added", "cik")}
    rows = []
    for line in grid[1:]:
        if len(line) < len(head):
            continue
        cik = re.sub(r"\D", "", line[idx["cik"]])
        rows.append({"ticker": line[idx["symbol"]].strip(), "security": line[idx["security"]], "sector": line[idx["gics sector"]],
                     "sub_industry": line[idx["gics sub"]], "date_added": _date(line[idx["date added"]]),
                     "cik": cik.zfill(10) if cik else ""})
    return pd.DataFrame(rows)


def _header_rows(grid: list[list[str]]) -> int:
    """Number of leading rows that are headers (no date in the first cell)."""
    n = 0
    while n < len(grid) and not _date(grid[n][0] if grid[n] else ""):
        n += 1
    return n


def is_changes_table(grid: list[list[str]]) -> bool:
    n = _header_rows(grid)
    head = " ".join(" ".join(r) for r in grid[:n]).lower()
    return 0 < n <= 3 and "added" in head and "removed" in head and ("date" in head or "effective" in head) and len(grid) > n


def changes(grid: list[list[str]]) -> pd.DataFrame:
    """A table of dated additions and removals. Columns are found from the header text (one or two header rows):
    the date column; under 'Added' the ticker and security; under 'Removed' the ticker and security; the reason."""
    if not is_changes_table(grid):
        head = " ".join(" ".join(r) for r in grid[:2]).lower()
        raise ValueError(f"changes table header not recognised: {head[:120]}")
    n = _header_rows(grid)
    width = max(len(r) for r in grid)
    labels = [" ".join(grid[r][c] if c < len(grid[r]) else "" for r in range(n)).lower() for c in range(width)]

    def col(*need, avoid=()):
        for i, lab in enumerate(labels):
            if all(w in lab for w in need) and not any(w in lab for w in avoid):
                return i
        return None
    def first(*opts):
        return next((c for c in opts if c is not None), None)
    c_date = first(col("date"), col("effective"))
    c_at = first(col("added", "ticker"), col("added", "symbol"))
    c_as = first(col("added", "security"), col("added", "name"), col("added", "company"))
    c_rt = first(col("removed", "ticker"), col("removed", "symbol"))
    c_rs = first(col("removed", "security"), col("removed", "name"), col("removed", "company"))
    c_reason = col("reason")
    if None in (c_date, c_at, c_rt):
        raise ValueError(f"changes table columns not found: {labels}")
    cell = lambda r, c: (r[c] if c is not None and c < len(r) else "")  # noqa: E731
    rows = [{"date": _date(r[c_date]), "added_ticker": cell(r, c_at).strip(), "added_security": cell(r, c_as),
             "removed_ticker": cell(r, c_rt).strip(), "removed_security": cell(r, c_rs), "reason": cell(r, c_reason)}
            for r in grid[n:] if r and _date(cell(r, c_date))]
    df = pd.DataFrame(rows, columns=["date", "added_ticker", "added_security", "removed_ticker", "removed_security", "reason"])
    df = df[(df["added_ticker"] != "") | (df["removed_ticker"] != "")]
    return df.drop_duplicates().reset_index(drop=True)


def all_changes(tables: dict) -> tuple[pd.DataFrame, list[str]]:
    """Every changes table found (some pages split the history by year), combined; returns the table keys used."""
    keys = [k for k, g in tables.items() if is_changes_table(g)]
    if not keys:
        raise ValueError("no table with date / added / removed headers found")
    df = pd.concat([changes(tables[k]) for k in keys], ignore_index=True).drop_duplicates().reset_index(drop=True)
    return df, keys


def rebalance_dates(cfg: dict, today: str) -> list[str]:
    """1 April each year (and 1 July when the robustness section asks for it, V2.7), up to the collection date, plus that date."""
    b = cfg["backtest"]
    days = [b["rebalance_month_day"]] + ([cfg["robustness"]["alt_month_day"]] if cfg.get("robustness", {}).get("alt_month_day") else [])
    out = sorted({f"{y}-{md}" for y in range(b["first_year"], b["last_year"] + 2) for md in days if f"{y}-{md}" < today})
    return out + [today]


def membership(cur: pd.DataFrame, ch: pd.DataFrame, dates: list[str], by_name: dict | None = None) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """Members at each date, by undoing later changes newest first. Returns rows (date, ticker, security), warnings for
    changes that contradict the reconstruction, and the ticker changes found on the way (I-76).

    A company that changed ticker after joining appears under its new ticker, so undoing its addition under the old one
    finds nothing. The old ticker is linked to a current member only on evidence, in this order, and only when exactly one
    member qualifies: (1) the member's Wikipedia 'date added' equals the change date; (2) the member's security name equals
    the added security's name; (3) SEC's name file lists both names under the same CIK."""
    names = dict(zip(cur["ticker"], cur["security"]))
    added_on = dict(zip(cur["ticker"], cur["date_added"]))
    wiki_cik = dict(zip(cur["ticker"], cur["cik"]))
    members = set(cur["ticker"])
    warn, out, renames = [], [], []
    keys = sorted(by_name) if by_name else []
    ch = ch.sort_values("date", ascending=False, kind="stable")
    added_same_day = ch.groupby("date")["added_ticker"].apply(set).to_dict()

    def resolve(c):
        others = added_same_day.get(c.date, set())
        cand = [t for t in members if added_on.get(t) == c.date and t not in others]
        if len(cand) > 1:
            first = (norm_name(c.added_security).split() or [""])[0]
            cand = [t for t in cand if (norm_name(names.get(t, "")).split() or [""])[0] == first]
        if len(cand) == 1:
            return cand[0], "date_added", wiki_cik.get(cand[0], "")
        same = [t for t in members if names.get(t, "").strip().lower() == c.added_security.strip().lower()]
        if len(same) == 1:
            return same[0], "same_name", wiki_cik.get(same[0], "")
        if by_name:
            mine = name_ciks(c.added_security, by_name, keys)
            if mine:
                hits = [(t, mine & (name_ciks(names.get(t, ""), by_name, keys) | ({wiki_cik[t]} if wiki_cik.get(t) else set())))
                        for t in members if names.get(t)]
                hits = [(t, k) for t, k in hits if len(k) == 1]
                if len(hits) == 1:
                    return hits[0][0], "shared_cik", next(iter(hits[0][1]))
        return None, "", ""
    pending = list(ch.itertuples())
    for d in sorted(dates, reverse=True):
        while pending and pending[0].date > d:
            c = pending.pop(0)
            if c.added_ticker:
                t = c.added_ticker
                if t not in members:
                    new, basis, cik = resolve(c)
                    if new:
                        renames.append({"old_ticker": t, "old_security": c.added_security, "ticker": new, "security": names.get(new, ""),
                                        "added_date": c.date, "basis": basis, "cik": cik})
                        t = new
                    else:
                        warn.append(f"{c.date}: added {c.added_ticker} was not a member when undoing")
                members.discard(t)
            if c.removed_ticker:
                if c.removed_ticker in members:
                    warn.append(f"{c.date}: removed {c.removed_ticker} was already a member when undoing")
                members.add(c.removed_ticker)
                names.setdefault(c.removed_ticker, c.removed_security)
        out += [{"date": d, "ticker": t, "security": names.get(t, "")} for t in sorted(members)]
    cols = ["old_ticker", "old_security", "ticker", "security", "added_date", "basis", "cik"]
    return pd.DataFrame(out), warn, pd.DataFrame(renames, columns=cols)


def name_ciks(name: str, by_name: dict, keys: list[str]) -> set:
    """CIKs whose SEC filer name, normalised, equals this name or starts with it as whole words ('CERIDIAN' matches
    'CERIDIAN HCM'). Used only to link two names to one CIK, never to pick a CIK for one name on its own."""
    import bisect
    n = norm_name(name)
    if len(n) < 3:
        return set()
    out = set(by_name.get(n, set()))
    i = bisect.bisect_left(keys, n + " ")
    while i < len(keys) and keys[i].startswith(n + " "):
        out |= by_name[keys[i]]
        i += 1
    return out


_SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LLC|LP|NV|SA|AG|HOLDINGS?|GROUP|THE|CLASS [A-Z])\b")


def norm_name(s: str) -> str:
    s = s.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def sec_maps(tickers_json: str, names_txt: str) -> tuple[dict, dict]:
    """by_ticker: ticker -> CIK (today's holders of each ticker); by_name: normalised filer name -> CIKs (all names a
    CIK has filed under, so former names too). sec_maps.cik_names (CIK -> names) is kept for name checks."""
    t = json.loads(tickers_json)
    by_ticker = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in t.values()}
    by_name: dict[str, set] = {}
    cik_names: dict[str, set] = {}
    for line in names_txt.splitlines():
        m = re.match(r"^(.*):(\d{10}):\s*$", line)
        if m:
            n = norm_name(m.group(1))
            by_name.setdefault(n, set()).add(m.group(2))
            cik_names.setdefault(m.group(2), set()).add(n)
    sec_maps.cik_names = cik_names
    return by_ticker, by_name


def names_agree(security: str, sec_names: set) -> bool:
    """True when one of a CIK's SEC filer names starts like the security's name (spaces ignored; up to 6 letters).
    Guards against tickers that SEC's file now assigns to a different company (APC, STI, SE, TE were reused, I-77)."""
    a = norm_name(security).replace(" ", "")
    if not a:
        return False
    k = min(len(a), 6)
    return any(n.replace(" ", "")[:k] == a[:k] for n in sec_names)


def map_ciks(mem: pd.DataFrame, cur: pd.DataFrame, by_ticker: dict, by_name: dict, renames: pd.DataFrame | None = None) -> pd.DataFrame:
    wiki = dict(zip(cur["ticker"], cur["cik"]))
    linked = {} if renames is None else {r.ticker: r.cik for r in renames.itertuples() if r.basis == "shared_cik" and r.cik}
    rows = []
    for t, sec in mem.drop_duplicates("ticker")[["ticker", "security"]].itertuples(index=False):
        cik, basis = "", "unmapped"
        if wiki.get(t):
            cik, basis = wiki[t], "wikipedia"
        elif linked.get(t):
            cik, basis = linked[t], "sec_name_shared"
        elif by_ticker.get(t.upper().replace(".", "-")) and names_agree(sec, getattr(sec_maps, "cik_names", {}).get(by_ticker[t.upper().replace(".", "-")], set())):
            cik, basis = by_ticker[t.upper().replace(".", "-")], "sec_ticker"
        else:
            hit = by_name.get(norm_name(sec), set())
            if len(hit) == 1:
                cik, basis = next(iter(hit)), "sec_name"
        rows.append({"ticker": t, "security": sec, "cik": cik, "cik_basis": basis, "in_current": t in wiki})
    return pd.DataFrame(rows)


def build(raw_dir: Path, cfg: dict, today: str) -> dict:
    tabs = parse_tables((raw_dir / "sp500_wikipedia.html").read_text(encoding="utf-8"))
    u = cfg["universe"]
    if u["constituents_table_id"] not in tabs:
        raise ValueError(f"constituents table not found; tables present: {sorted(tabs)}")
    cur = constituents(tabs[u["constituents_table_id"]])
    hist = raw_dir / "sp500_history_wikipedia.html"
    pool = {f"main:{k}": g for k, g in tabs.items() if k != u["constituents_table_id"]}
    if hist.exists():
        pool.update({f"history:{k}": g for k, g in parse_tables(hist.read_text(encoding="utf-8")).items()})
    ch, used = all_changes(pool)
    dates = rebalance_dates(cfg, today)
    by_ticker, by_name = sec_maps((raw_dir / "company_tickers.json").read_text(encoding="utf-8"),
                                  (raw_dir / "cik-lookup-data.txt").read_text(encoding="latin-1"))
    mem, warn, renames = membership(cur, ch, dates, by_name)
    ciks = map_ciks(mem, cur, by_ticker, by_name, renames)
    sector = dict(zip(cur["ticker"], cur["sector"]))
    mem = mem.merge(ciks[["ticker", "cik", "cik_basis"]], on="ticker", how="left")
    mem["sector"] = mem["ticker"].map(sector).fillna("")          # removed companies: sector from SEC SIC codes in V2.2
    mem["excluded_sector"] = mem["sector"].isin(cfg["sectors"]["excluded"])
    cov = (mem.assign(has=mem["cik"] != "").groupby("date")
           .agg(members=("ticker", "size"), with_cik=("has", "sum"), from_current=("sector", lambda s: (s != "").sum()))
           .reset_index())
    cov["cik_coverage"] = cov["with_cik"] / cov["members"]
    return {"current": cur, "changes": ch, "changes_tables": used, "renames": renames, "membership": mem, "ciks": ciks, "coverage": cov, "warnings": warn, "dates": dates,
            "by_ticker": by_ticker}


def checks(res: dict, cfg: dict) -> list[tuple]:
    """U1-U7, as (check, passed, detail, level)."""
    u, cur, ch, cov = cfg["universe"], res["current"], res["changes"], res["coverage"]
    lo, hi = u["expected_size"]
    out = [("U1_current_constituents", lo <= len(cur) <= hi and cur["ticker"].is_unique, f"{len(cur)} rows, unique tickers {cur['ticker'].is_unique}", "error")]
    bad = cur[~cur["sector"].isin(cfg["sectors"]["gics"]) | (cur["cik"].str.len() != 10)]
    out.append(("U2_sector_and_cik_present", bad.empty, f"rows without a GICS sector or 10-digit CIK: {bad['ticker'].tolist()[:8] or 'none'}", "error"))
    bt = res["by_ticker"]
    clash = [t for t, c in zip(cur["ticker"], cur["cik"]) if bt.get(t.upper().replace(".", "-")) not in (None, c)]
    out.append(("U3_cik_agrees_with_sec", not clash, f"{len(cur) - len(clash)}/{len(cur)} agree or not listed by ticker at SEC; disagree: {clash[:8] or 'none'}",
                "error" if len(clash) > 5 else "warning"))
    since = ch[ch["date"] >= f"{cfg['backtest']['first_year']}-01-01"]
    ok = len(since) >= 100 and ch["date"].ne("").all() and ((ch["added_ticker"] != "") | (ch["removed_ticker"] != "")).all()
    out.append(("U4_changes_parsed", ok, f"{len(ch)} change rows from {len(res['changes_tables'])} table(s) {res['changes_tables'][:4]}, "
                f"{len(since)} since {cfg['backtest']['first_year']}; earliest {ch['date'].min()}", "error"))
    off = cov[(cov["members"] < lo) | (cov["members"] > hi)]
    out.append(("U5_membership_size_each_date", off.empty, "members per date " + ", ".join(f"{d[:7]} {n}" for d, n in zip(cov["date"], cov["members"])), "error"))
    low = cov[cov["cik_coverage"] < u["cik_coverage_error_below"]]
    tgt = cov[cov["cik_coverage"] < u["cik_coverage_target"]]
    out.append(("U6_cik_coverage", low.empty, "CIK coverage " + ", ".join(f"{d[:7]} {c:.1%}" for d, c in zip(cov["date"], cov["cik_coverage"]))
                + (f"; below the {u['cik_coverage_target']:.0%} target: {len(tgt)} dates" if len(tgt) else ""), "error"))
    out.append(("U7_reconstruction_consistent", len(res["warnings"]) <= 10,
                f"{len(res['warnings'])} contradictions while undoing changes" + (f", e.g. {res['warnings'][:3]}" if res["warnings"] else "")
                + f"; {len(res['renames'])} ticker changes linked on evidence (ticker_changes.csv)", "warning"))
    nv = res["membership"].groupby("date")["ticker"].apply(lambda s: "NVDA" in set(s))
    out.append(("U8_nvidia_member_every_date", bool(nv.all()), f"NVDA a member at {int(nv.sum())}/{len(nv)} dates", "error"))
    return out


def today_iso() -> str:
    return date.today().isoformat()
