"""Step 3c: independent recomputation of the SQL views in Python (Decimal arithmetic), from the load files.

This file deliberately shares no code with sql/views.sql: it re-implements the S3-D3 definitions so that
an error in either implementation shows up as a mismatch. compare() checks every numeric cell of the
exported views v_ratios_annual, v_ratios_ltm and v_valuation_cutoff against this recomputation.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, getcontext
from pathlib import Path

import pandas as pd

getcontext().prec = 40
SPLIT_ITEMS = {"eps_diluted", "shares_diluted"}
TOL = Decimal("1e-9")


def D(x):
    return None if x is None or x == "" else Decimal(str(x))


def _div(a, b):
    return None if a is None or b is None or b == 0 else a / b


def _sub(*xs):
    return None if any(x is None for x in xs) else xs[0] - sum(xs[1:], Decimal(0))


def _add(*xs):
    return None if any(x is None for x in xs) else sum(xs, Decimal(0))


def _root(x, n):
    return x ** (Decimal(1) / Decimal(n))


class Facts:
    def __init__(self, load: Path):
        f = pd.read_csv(load / "facts.csv", dtype=str, keep_default_na=False)
        li = pd.read_csv(load / "line_items.csv", dtype=str, keep_default_na=False)
        self.ptype = dict(zip(li["line_item"], li["period_type"]))
        f = f[(f["support_item"] != "True") & (f["value_basis"] != "reported_ytd")].copy()
        f["amount"] = [D(r.display_split_adjusted) if r.line_item in SPLIT_ITEMS else D(r.display_value) for r in f.itertuples()]
        self.f = f
        self.annual = self._annual()
        self.quarterly = self._quarterly()

    def _annual(self) -> dict:
        best = {}
        for r in self.f.itertuples():
            ok = (self.ptype[r.line_item] == "duration" and r.fiscal_period == "FY") or \
                 (self.ptype[r.line_item] == "instant" and r.fiscal_period == "Q4")
            if not ok:
                continue
            key = (r.ticker, r.line_item, int(r.fiscal_year))
            rank = (r.period_end, r.period_start or "")
            if key not in best or rank > best[key][0]:
                best[key] = (rank, r.amount, r.period_end if r.line_item == "revenue" else None)
        out = defaultdict(dict)
        for (t, item, fy), (_, amt, pe) in best.items():
            out[(t, fy)][item] = amt
            if pe:
                out[(t, fy)]["period_end"] = pe
        return out

    def _quarterly(self) -> dict:
        best = {}
        for r in self.f.itertuples():
            if r.fiscal_period not in ("Q1", "Q2", "Q3", "Q4") or r.value_basis == "reported_annual":
                continue
            key = (r.ticker, r.line_item, r.period_end)
            if key not in best or (r.period_start or "") > best[key][0]:
                best[key] = (r.period_start or "", r.amount)
        out = defaultdict(dict)
        for (t, item, pe), (_, amt) in best.items():
            out[(t, pe)][item] = amt
        return out


def ratios_annual(F: Facts) -> dict:
    res = {}
    by_t = defaultdict(list)
    for (t, fy), v in F.annual.items():
        by_t[t].append((fy, v))
    for t, rows in by_t.items():
        rows.sort()
        roes = []
        for i, (fy, v) in enumerate(rows):
            g = v.get
            prev = rows[i - 1] if i >= 1 else None
            r5 = rows[i - 5] if i >= 5 else None
            r3 = rows[i - 3] if i >= 3 else None
            consecutive = prev is not None and prev[0] == fy - 1
            pv = prev[1].get if prev else (lambda k: None)
            rev = g("revenue")
            o = {}
            o["revenue_growth"] = _div(rev, pv("revenue")) - 1 if consecutive and pv("revenue") and pv("revenue") > 0 and rev is not None else None
            o["revenue_cagr_5y"] = (_root(rev / r5[1]["revenue"], 5) - 1) if r5 and r5[0] == fy - 5 and r5[1].get("revenue") and r5[1]["revenue"] > 0 and rev and rev > 0 else None
            for name, num in (("gross_margin", "gross_profit"), ("operating_margin", "operating_income"), ("net_margin", "net_income")):
                o[name] = _div(g(num), rev) if rev is not None and rev > 0 else None
            avg_eq = (g("stockholders_equity") + pv("stockholders_equity")) / 2 if consecutive and g("stockholders_equity") is not None and pv("stockholders_equity") is not None else None
            o["roe"] = _div(g("net_income"), avg_eq) if avg_eq is not None and avg_eq > 0 else None
            roes.append(o["roe"])
            last5, last3 = roes[-5:], roes[-3:]
            o["roe_5y_avg"] = sum(last5) / 5 if len(last5) == 5 and None not in last5 else None
            o["roe_3y_avg"] = sum(last3) / 3 if len(last3) == 3 and None not in last3 else None
            cl = g("current_liabilities")
            o["quick_ratio"] = _div(_sub(g("current_assets"), g("inventory")), cl) if cl is not None and cl > 0 else None
            o["fcf"] = _sub(g("operating_cash_flow"), g("capex"))
            ni = g("net_income")
            o["fcf_conversion"] = _div(o["fcf"], ni) if ni is not None and ni > 0 else None
            o["net_debt"] = _sub(g("total_debt"), g("cash_and_equivalents"), g("st_investments"))
            o["ebitda"] = _add(g("operating_income"), g("depreciation_amortization"))
            o["net_debt_to_ebitda"] = _div(o["net_debt"], o["ebitda"]) if o["ebitda"] is not None and o["ebitda"] > 0 else None
            pre, tax = g("pretax_income"), g("income_tax")
            etr = tax / pre if pre is not None and pre > 0 and tax is not None and 0 <= tax / pre <= 1 else None
            o["effective_tax_rate"] = etr
            o["tax_rate_used"] = etr if etr is not None else Decimal("0.21")
            oi = g("operating_income")
            o["nopat"] = oi * (1 - o["tax_rate_used"]) if oi is not None else None
            ic = _sub(_add(g("total_debt"), g("stockholders_equity")), g("cash_and_equivalents"), g("st_investments"))
            pic = _sub(_add(pv("total_debt"), pv("stockholders_equity")), pv("cash_and_equivalents"), pv("st_investments")) if consecutive else None
            o["invested_capital"] = ic
            o["avg_invested_capital"] = (ic + pic) / 2 if ic is not None and pic is not None else None
            o["roic"] = _div(o["nopat"], o["avg_invested_capital"]) if o["avg_invested_capital"] is not None and o["avg_invested_capital"] > 0 else None
            sh = g("shares_diluted")
            o["shares_diluted_adj"] = sh
            o["shares_change_5y"] = (sh / r5[1]["shares_diluted"] - 1) if r5 and r5[0] == fy - 5 and r5[1].get("shares_diluted") and r5[1]["shares_diluted"] > 0 and sh is not None else None
            o["eps_diluted_adj"] = g("eps_diluted")
            ni3 = r3[1].get("net_income") if r3 and r3[0] == fy - 3 else None
            o["net_income_cagr_3y"] = (_root(ni / ni3, 3) - 1) if ni3 and ni3 > 0 and ni and ni > 0 else None
            o["revenue"] = rev
            res[(t, fy)] = o
    return res


LTM_FLOWS = {"ltm_revenue": "revenue", "ltm_gross_profit": "gross_profit", "ltm_operating_income": "operating_income",
             "ltm_net_income": "net_income", "ltm_depreciation_amortization": "depreciation_amortization",
             "ltm_operating_cash_flow": "operating_cash_flow", "ltm_capex": "capex"}


def ltm(F: Facts) -> dict:
    from datetime import date
    res = {}
    by_t = defaultdict(list)
    for (t, pe), v in F.quarterly.items():
        by_t[t].append((pe, v))
    for t, rows in by_t.items():
        rows.sort()
        for i, (pe, v) in enumerate(rows):
            o = {}
            ok = i >= 3 and 250 <= (date.fromisoformat(pe) - date.fromisoformat(rows[i - 3][0])).days <= 300
            win = rows[max(0, i - 3): i + 1]
            for out_name, item in LTM_FLOWS.items():
                vals = [w[1].get(item) for w in win]
                o[out_name] = sum(vals, Decimal(0)) if ok and len(vals) == 4 and None not in vals else None
            for item in ("total_debt", "cash_and_equivalents", "st_investments", "stockholders_equity"):
                o[item] = v.get(item)
            res[(t, pe)] = o
    # ratios on top of LTM
    for t, rows in by_t.items():
        keys = sorted(pe for (tt, pe) in res if tt == t)
        for i, pe in enumerate(keys):
            o = res[(t, pe)]
            rev = o["ltm_revenue"]
            prev = res[(t, keys[i - 4])]["ltm_revenue"] if i >= 4 else None
            o["ltm_revenue_growth"] = rev / prev - 1 if prev is not None and prev > 0 and rev is not None else None
            for name, num in (("ltm_gross_margin", "ltm_gross_profit"), ("ltm_operating_margin", "ltm_operating_income"), ("ltm_net_margin", "ltm_net_income")):
                o[name] = _div(o[num], rev) if rev is not None and rev > 0 else None
            o["ltm_fcf"] = _sub(o["ltm_operating_cash_flow"], o["ltm_capex"])
            o["ltm_ebitda"] = _add(o["ltm_operating_income"], o["ltm_depreciation_amortization"])
            o["net_debt"] = _sub(o["total_debt"], o["cash_and_equivalents"], o["st_investments"])
    return res


def valuation(F: Facts, load: Path, ann: dict, lt: dict) -> dict:
    mi = pd.read_csv(load / "market_inputs.csv", dtype=str, keep_default_na=False).set_index("ticker")
    co = pd.read_csv(load / "companies.csv", dtype=str, keep_default_na=False)
    res = {}
    for t in co.loc[co["role"] != "benchmark", "ticker"]:
        m = mi.loc[t]
        mcap = D(m["market_cap_usd"]) / 1000000 if m["market_cap_usd"] else None
        ltm_keys = sorted(pe for (tt, pe), o in lt.items() if tt == t and o["ltm_revenue"] is not None and o["ltm_net_income"] is not None)
        lo = lt[(t, ltm_keys[-1])] if ltm_keys else {}
        bs_keys = sorted(pe for (tt, pe), q in F.quarterly.items() if tt == t and all(q.get(k) is not None for k in ("total_debt", "cash_and_equivalents", "st_investments")))
        bs = F.quarterly[(t, bs_keys[-1])] if bs_keys else {}
        fy_keys = sorted(fy for (tt, fy), o in ann.items() if tt == t and o["revenue"] is not None)
        fo = ann[(t, fy_keys[-1])]
        ev = _sub(_add(mcap, bs.get("total_debt")), bs.get("cash_and_equivalents"), bs.get("st_investments"))
        ebitda = lo.get("ltm_ebitda") if lo.get("ltm_ebitda") is not None else fo["ebitda"]
        ni, rev = lo.get("ltm_net_income"), lo.get("ltm_revenue")
        pe = mcap / ni if ni is not None and ni > 0 else None
        res[t] = {"market_cap": mcap, "ltm_revenue": rev, "ltm_net_income": ni, "ltm_fcf": lo.get("ltm_fcf"),
                  "ebitda_used": ebitda, "total_debt": bs.get("total_debt"), "enterprise_value": ev, "pe_ltm": pe,
                  "ev_revenue_ltm": _div(ev, rev) if rev is not None and rev > 0 else None,
                  "ev_ebitda": _div(ev, ebitda) if ebitda is not None and ebitda > 0 else None,
                  "peg_historical_3y": pe / (100 * fo["net_income_cagr_3y"]) if pe is not None and fo["net_income_cagr_3y"] is not None and fo["net_income_cagr_3y"] > 0 else None}
    return res


def _close(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= TOL * max(Decimal(1), abs(a), abs(b))


def compare(load: Path, exports: Path) -> list[tuple[str, bool, str]]:
    F = Facts(load)
    ann, lt = ratios_annual(F), ltm(F)
    val = valuation(F, load, ann, lt)
    results = []
    for view, key_cols, ref in (("v_ratios_annual", ["ticker", "fiscal_year"], lambda r: ann.get((r["ticker"], int(r["fiscal_year"])))),
                                ("v_ratios_ltm", ["ticker", "period_end"], lambda r: lt.get((r["ticker"], r["period_end"]))),
                                ("v_valuation_cutoff", ["ticker"], lambda r: val.get(r["ticker"]))):
        sql = pd.read_csv(exports / f"{view}.csv", dtype=str, keep_default_na=False)
        cells, bad, examples = 0, 0, []
        for _, r in sql.iterrows():
            o = ref(r)
            if o is None:
                bad += 1
                examples.append(f"{[r[k] for k in key_cols]} missing in Python")
                continue
            for col, pyval in o.items():
                if col not in sql.columns:
                    continue
                cells += 1
                if not _close(D(r[col]), pyval):
                    bad += 1
                    if len(examples) < 5:
                        examples.append(f"{[r[k] for k in key_cols]} {col}: SQL {r[col] or 'NULL'} vs Python {pyval}")
        rows_py = len([k for k in (ann if view == 'v_ratios_annual' else lt if view == 'v_ratios_ltm' else val)])
        same_rows = rows_py == len(sql)
        results.append((f"V1_{view}_matches_python", bad == 0 and same_rows,
                        f"{cells} cells compared, {bad} differ; rows SQL {len(sql)} / Python {rows_py}; {examples[:5] or ''}"))
    return results
