"""Version 2, V2.3 and V2.5: point-in-time annual facts and the scorecard metrics, for any company at any date.

extract()  keeps only what V2 needs from a companyfacts file: the configured us-gaap concepts as reported in annual reports
           (10-K family and amendments), plus balance-sheet (instant) values from 10-Qs, whose prior-year-end column can carry
           a value the 10-K tagged differently (I-88); one row per observation with its filing date and accession.
pit()      what an investor could have known on a date (V2-D12): only observations filed strictly before the date; for
           each line item and fiscal-year end, the first configured concept with a value, then the latest-filed value
           (the same rules as Version 1's select_line_items, with the date cut added).
metrics()  the Version 1 formulas (sql/views.sql, v_ratios_annual) on the latest fiscal year known at the date, plus the
           trailing P/E on that year (V2-D13). Share counts and EPS are put on the share basis of the date using the
           splits after each value was filed, so a split between filings does not look like a 100% share issue.

Values are floats here (Version 1 used Decimal for exact reconciliation to filings; V2 ranks ratios across 500 companies).
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import NamedTuple

import pandas as pd

OBS_COLUMNS = ["cik", "concept", "unit", "start", "end", "days", "value", "form", "filed", "accn"]
UNITS = {"USD", "shares", "USD/shares"}


def needed_concepts(cfg: dict) -> set:
    return {c for lst in cfg["facts"]["line_items"].values() for c in lst}


def extract(facts_json: dict, cik: str, cfg: dict) -> pd.DataFrame:
    """Rows for the configured concepts reported in annual reports (form in annual_forms or their /A amendments)."""
    want = needed_concepts(cfg)
    forms = set(cfg["sec"]["annual_forms"]) | {f + "/A" for f in cfg["sec"]["annual_forms"]}
    quarterly = {"10-Q", "10-Q/A"}            # balance-sheet values only: a 10-Q's prior-year-end column (I-88)
    rows = []
    for concept, body in facts_json.get("facts", {}).get("us-gaap", {}).items():
        if concept not in want:
            continue
        for unit, obs in body.get("units", {}).items():
            if unit not in UNITS:
                continue
            for o in obs:
                start, end = o.get("start", ""), o["end"]
                if o.get("form") not in forms and not (not start and o.get("form") in quarterly):
                    continue
                days = (date.fromisoformat(end) - date.fromisoformat(start)).days if start else -1
                rows.append((cik, concept, unit, start, end, days, float(o["val"]), o.get("form", ""), o.get("filed", ""), o.get("accn", "")))
    return pd.DataFrame(rows, columns=OBS_COLUMNS)


class Row(NamedTuple):
    end: str
    value: float
    concept: str
    filed: str
    accn: str
    end_ord: int


def prepare(obs: pd.DataFrame, cfg: dict) -> dict:
    """Per line item, the candidate observations sorted for selection (end, concept priority, latest filed first). Built once
    per company; pit() then only applies the date cut, so scoring 500 companies at 23 dates stays fast."""
    fc = cfg["facts"]
    lo, hi = fc["annual_days"]
    inst = set(fc["instant_items"])
    out = {}
    for item, cands in fc["line_items"].items():
        x = obs[obs["concept"].isin(cands)]
        x = x[x["days"] == -1] if item in inst else x[(x["days"] >= lo) & (x["days"] <= hi)]
        pr = {c: i for i, c in enumerate(cands)}
        rows = [(e, pr[c], f, a, float(v), c) for e, c, f, a, v in zip(x["end"], x["concept"], x["filed"], x["accn"], x["value"])]
        rows.sort(key=lambda r: (r[0], r[1], _neg(r[2]), _neg(r[3])))
        out[item] = rows
    return out


def _neg(s: str) -> tuple:
    return tuple(-ord(ch) for ch in s)


def pit(obs, d: str, cfg: dict) -> dict:
    """{line_item: [Row(end, value, concept, filed, accn, end_ord)]} sorted by end, one row per period end, using only
    observations filed before d. obs is the observations frame or the output of prepare()."""
    prep = prepare(obs, cfg) if isinstance(obs, pd.DataFrame) else obs
    out = {}
    for item, rows in prep.items():
        pick, last = [], None
        for e, _, f, a, v, c in rows:
            if f < d and e != last:
                pick.append(Row(e, v, c, f, a, date.fromisoformat(e).toordinal()))
                last = e
        out[item] = pick
    return out


def _shift_years(end: str, k: int) -> date:
    e = date.fromisoformat(end)
    try:
        return e.replace(year=e.year - k)
    except ValueError:                        # 29 February
        return e.replace(year=e.year - k, day=28)


def at(p: dict, item: str, fy0: str, k: int, tol: int):
    """The row of item for fiscal year FY0-k (end within tol days of FY0's end minus k years), or None."""
    rows = p.get(item)
    if not rows:
        return None
    target = _shift_years(fy0, k).toordinal()
    best, gap = None, tol + 1
    for r in rows:
        g = abs(r.end_ord - target)
        if g < gap:
            best, gap = r, g
    return best


def split_factor(splits: list, after: str, upto: str) -> float:
    """Product of split ratios with ex-date in (after, upto]. A 4-for-1 split has ratio 4; a 1-for-10 reverse split 0.1."""
    f = 1.0
    for dt, ratio in splits:
        if after < dt <= upto and ratio and ratio > 0:
            f *= ratio
    return f


def metrics(p: dict, d: str, cfg: dict, price_as_traded: float | None = None, splits: list | None = None, fy0_end: str | None = None) -> dict:
    """Scorecard metrics on the latest fiscal year known at d. Returns metric values (None when not computable), plus
    'fail' (metric -> reason, for a scored fail such as negative earnings) and 'flags' (assumptions applied)."""
    fc = cfg["facts"]
    tol = fc["fy_match_days"]
    splits = splits or []
    m = {"fy0_end": "", "fy0_filed": "", "fy0_accn": "", "stale": False, "fail": {}, "flags": []}
    base = p.get("revenue") or p.get("net_income")
    if not base:
        m["flags"].append("no annual revenue or net income filed before the date")
        return m
    r0 = base[-1] if fy0_end is None else next((x for x in base if x.end == fy0_end), None)
    if r0 is None:
        m["flags"].append(f"no fiscal year ending {fy0_end}")
        return m
    fy0 = r0.end
    m.update(fy0_end=fy0, fy0_filed=r0.filed, fy0_accn=r0.accn)
    if (date.fromisoformat(d) - date.fromisoformat(fy0)).days > fc["stale_after_days"]:
        m["stale"] = True
        m["flags"].append(f"latest fiscal year ends {fy0}, more than {fc['stale_after_days']} days before the date")
        return m

    def v(item, k=0, zero_ok=False):
        r = at(p, item, fy0, k, tol)
        if r is None:
            if zero_ok and item in fc["zero_if_missing"]:
                m["flags"].append(f"{item} FY-{k} not tagged: 0 used")
                return 0.0
            return None
        return r.value

    def filed(item, k=0):
        r = at(p, item, fy0, k, tol)
        return r.filed if r is not None else ""

    def div(a, b):
        return a / b if a is not None and b not in (None, 0) else None

    revenue, rev5 = v("revenue"), v("revenue", 5)
    m["revenue"] = revenue
    m["revenue_cagr_5y"] = (revenue / rev5) ** 0.2 - 1 if revenue and rev5 and revenue > 0 and rev5 > 0 else None

    gp = v("gross_profit")
    if gp is None and revenue is not None and v("cost_of_revenue") is not None:
        gp = revenue - v("cost_of_revenue")
        m["flags"].append("gross profit derived as revenue - cost of revenue")
    m["gross_margin"] = gp / revenue if gp is not None and revenue and revenue > 0 else None

    roes = []
    for k in range(5):
        ni, e0, e1 = v("net_income", k), v("equity", k), v("equity", k + 1)
        avg = (e0 + e1) / 2 if e0 is not None and e1 is not None else None
        roes.append(ni / avg if ni is not None and avg and avg > 0 else None)
    m["roe"] = roes[0]
    m["roe_5y_avg"] = sum(roes) / 5 if all(x is not None for x in roes) else None

    ca, cl, inv = v("current_assets"), v("current_liabilities"), v("inventory", zero_ok=True)
    m["quick_ratio"] = (ca - inv) / cl if ca is not None and cl and cl > 0 else None

    ni, ocf, capex = v("net_income"), v("operating_cash_flow"), v("capex")
    m["net_income"] = ni
    fcf = ocf - capex if ocf is not None and capex is not None else None
    m["fcf_conversion"] = fcf / ni if fcf is not None and ni and ni > 0 else None
    if ni is not None and ni <= 0:
        m["fail"]["fcf_conversion"] = "net income <= 0"

    def debt(k):
        cur, non = v("debt_current", k, zero_ok=True), v("debt_noncurrent", k)
        if non is not None:
            return cur + non
        tot = v("debt_total_fallback", k)
        if tot is not None:
            m["flags"].append(f"debt FY-{k}: LongTermDebt (total) used, no noncurrent split tagged")
            return tot
        m["flags"].append(f"debt FY-{k}: no long-term debt tagged, current debt only")
        return cur

    def net_debt(k):
        c, st = v("cash", k), v("st_investments", k, zero_ok=True)
        return debt(k) - c - st if c is not None else None

    oi = v("operating_income")
    if oi is None and v("pretax_income") is not None and v("interest_expense") is not None:
        oi = v("pretax_income") + v("interest_expense")
        m["flags"].append("operating income derived as pretax income + interest expense (EBIT)")
    da = v("d_and_a")
    if da is None and v("depreciation") is not None:
        am = v("amortization")
        da = v("depreciation") + (am or 0.0)
        m["flags"].append("D&A derived as depreciation + amortization of intangibles" + ("" if am is not None else " (none tagged: 0)"))
    ebitda = oi + da if oi is not None and da is not None else None
    nd0 = net_debt(0)
    m["net_debt_to_ebitda"] = nd0 / ebitda if nd0 is not None and ebitda and ebitda > 0 else None
    if ebitda is not None and ebitda <= 0:
        m["fail"]["net_debt_to_ebitda"] = "EBITDA <= 0"

    tax, pre = v("income_tax"), v("pretax_income")
    t = tax / pre if tax is not None and pre and pre > 0 and 0 <= tax / pre <= 1 else None
    if t is None:
        t = fc["statutory_tax_rate"]
        m["flags"].append("statutory 21% tax rate used")
    e0, e1 = v("equity"), v("equity", 1)
    nd1 = net_debt(1)
    ic0 = nd0 + e0 if nd0 is not None and e0 is not None else None
    ic1 = nd1 + e1 if nd1 is not None and e1 is not None else None
    aic = (ic0 + ic1) / 2 if ic0 is not None and ic1 is not None else None
    m["roic"] = oi * (1 - t) / aic if oi is not None and aic and aic > 0 else None
    m["operating_income"], m["ebitda"] = oi, ebitda

    s0, s5 = v("shares_diluted"), v("shares_diluted", 5)
    if s0 and s5 and s5 > 0:
        a0 = s0 * split_factor(splits, filed("shares_diluted"), d)
        a5 = s5 * split_factor(splits, filed("shares_diluted", 5), d)
        m["shares_change_5y"] = a0 / a5 - 1
    else:
        m["shares_change_5y"] = None

    eps = v("eps_diluted")
    m["pe_fy"] = None
    if eps is not None and eps <= 0:
        m["fail"]["pe_fy"] = "latest FY diluted EPS <= 0"
    elif eps is not None and price_as_traded:
        m["pe_fy"] = price_as_traded / (eps / split_factor(splits, filed("eps_diluted"), d))
    m["flags"] = sorted(set(m["flags"]))
    return m


def score(value, test: dict) -> int:
    """Step 4 rule: pass strict (2 points), near miss inclusive (1)."""
    if test["direction"] == "higher":
        return 2 if value > test["pass"] else (1 if value >= test["near"] else 0)
    return 2 if value < test["pass"] else (1 if value <= test["near"] else 0)


def finite(x) -> bool:
    return x is not None and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def add_days(d: str, n: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()
