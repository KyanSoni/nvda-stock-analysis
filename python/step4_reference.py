"""Step 4c: independent Python recomputation of the Step 4 views (beta, WACC, PEG, scorecard).

Shares no code with sql/scorecard.sql. Inputs: the Step 3 load files (via step3_reference, itself independent of
the SQL ratio views), the Step 4 load files and config/scorecard.yaml. compare() checks every numeric and text
cell of the exported Step 4 views against this recomputation.
"""
from __future__ import annotations

import statistics
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

import step3_reference as r3

TOL = Decimal("1e-9")
D = r3.D


def latest_annual(ann: dict) -> dict:
    out = {}
    for (t, fy), o in ann.items():
        if o["revenue"] is not None and (t not in out or fy > out[t][0]):
            out[t] = (fy, o)
    return out


def score(value, direction: str, pass_v: Decimal, near_v: Decimal) -> int:
    if value is None:
        return 0
    if direction == "higher":
        return 2 if value > pass_v else 1 if value >= near_v else 0
    return 2 if value < pass_v else 1 if value <= near_v else 0


def betas(prices: pd.DataFrame, cutoff: str, months: int, companies: list[str], benchmarks: list[str]) -> dict:
    first_of_cutoff_month = date.fromisoformat(cutoff).replace(day=1).isoformat()
    p = prices[prices["price_date"] < first_of_cutoff_month].copy()
    p["month"] = p["price_date"].str[:7]
    me = p.sort_values("price_date").groupby(["ticker", "month"]).tail(1)
    last = me["month"].max()
    y, m = int(last[:4]), int(last[5:])
    keep = set()
    for k in range(months):
        mm = m - k
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        keep.add(f"{yy:04d}-{mm:02d}")
    rets = {}
    for t, g in me.groupby("ticker"):
        g = g.sort_values("month")
        vals = [Decimal(v) for v in g["adj_close"]]
        rets[t] = {mo: vals[i] / vals[i - 1] - 1 for i, mo in enumerate(g["month"]) if i > 0 and mo in keep}
    out = {}
    for t in companies:
        for b in benchmarks:
            common = sorted(set(rets[t]) & set(rets[b]))
            xs = [float(rets[b][k]) for k in common]
            ys = [float(rets[t][k]) for k in common]
            n = len(common)
            mx, my = sum(xs) / n, sum(ys) / n
            cov = sum((x - mx) * (y_ - my) for x, y_ in zip(xs, ys)) / n
            vx = sum((x - mx) ** 2 for x in xs) / n
            vy = sum((y_ - my) ** 2 for y_ in ys) / n
            out[(t, b)] = {"beta": Decimal(repr(cov / vx)), "correlation": Decimal(repr(cov / (vx * vy) ** 0.5)), "months": n,
                           "first_month": common[0] + "-01", "last_month": common[-1] + "-01"}
    return out


def recompute(load3: Path, load4: Path, sc: dict) -> dict:
    F = r3.Facts(load3)
    ann, lt = r3.ratios_annual(F), r3.ltm(F)
    val = r3.valuation(F, load3, ann, lt)
    lat = latest_annual(ann)
    mi = pd.read_csv(load3 / "market_inputs.csv", dtype=str, keep_default_na=False).set_index("ticker")
    co = pd.read_csv(load3 / "companies.csv", dtype=str, keep_default_na=False)
    comps = sorted(co.loc[co["role"] != "benchmark", "ticker"])
    benches = sorted(co.loc[co["role"] == "benchmark", "ticker"])
    cutoff = mi.loc[comps[0], "cutoff_date"]
    prices = pd.read_csv(load3 / "prices.csv", dtype=str, keep_default_na=False)
    bet = betas(prices, cutoff, int(sc["wacc"]["months"]), comps, benches)
    erp = D(sc["wacc"]["equity_risk_premium"])
    rf = D(mi.loc["RISK_FREE_10Y", "close"]) / 100
    est = pd.read_csv(load4 / "estimates.csv", dtype=str, keep_default_na=False)
    e = {(x.ticker, x.kind, x.period): D(x.avg) for x in est.itertuples()}

    wacc, peg, detail, card = {}, {}, {}, {}
    for t in comps:
        fy, o = lat[t]
        a, prev = F.annual[(t, fy)], F.annual.get((t, fy - 1), {})
        v = val[t]
        beta = bet[(t, sc["wacc"]["benchmark"])]["beta"]
        ke = rf + beta * erp
        debt_avg_base = (a.get("total_debt") or 0) + (prev.get("total_debt") or 0) if a.get("total_debt") is not None and prev.get("total_debt") is not None else None
        kd = a["interest_expense"] / (debt_avg_base / 2) if debt_avg_base and a.get("interest_expense") is not None else None
        dbt, mcap = v["total_debt"], v["market_cap"]
        if dbt == 0:
            w = ke
        elif kd is None:
            w = None
        else:
            w = mcap / (dbt + mcap) * ke + dbt / (dbt + mcap) * kd * (1 - o["tax_rate_used"])
        wacc[t] = {"risk_free": rf, "beta": beta, "cost_of_equity": ke, "cost_of_debt_pretax": kd,
                   "debt_weight": dbt / (dbt + mcap), "wacc": w}
        e0, e1 = e.get((t, "eps", "0y")), e.get((t, "eps", "+1y"))
        g = e1 / e0 - 1 if e0 is not None and e1 is not None and e0 > 0 else None
        pe = v["pe_ltm"]
        p = pe / (100 * g) if pe is not None and pe > 0 and g is not None and g > 0 else None
        peg[t] = {"fwd_eps_growth": g, "peg_forward": p, "available": e0 is not None and e1 is not None}

        others = [lat[x][1]["gross_margin"] for x in comps if x != t and lat[x][1]["gross_margin"] is not None]
        gm = o["gross_margin"]
        ni = a.get("net_income")
        metrics = {
            1: (o["revenue_cagr_5y"], False),
            2: (pe, v["ltm_net_income"] is not None and v["ltm_net_income"] <= 0),
            3: (p, peg[t]["available"]),
            4: (o["roe_5y_avg"], False),
            5: (o["quick_ratio"], False),
            6: (gm - Decimal(repr(float(statistics.median(others)))) if gm is not None and others else None, False),
            7: (o["fcf_conversion"], ni is not None and ni <= 0),
            8: (o["net_debt_to_ebitda"], o["ebitda"] is not None and o["ebitda"] <= 0),
            9: (o["roic"] - w if o["roic"] is not None and w is not None else None, False),
            10: (o["shares_change_5y"], False),
        }
        total, scored = 0, 0
        for n, (value, null_fails) in metrics.items():
            rule = sc["tests"][n]
            pts = score(value, rule["direction"], D(rule["pass"]), D(rule["near"]))
            res = ("not scored" if value is None and not null_fails else "fail" if value is None else
                   {2: "pass", 1: "near miss", 0: "fail"}[pts])
            detail[(t, n)] = {"value": value, "points": pts, "result": res}
            total += pts
            scored += res != "not scored"
        card[t] = {"total": total, "max_possible": 2 * scored, "tests_scored": scored}
    return {"beta": bet, "wacc": wacc, "peg": peg, "detail": detail, "card": card}


def _same(a, b) -> bool:
    if isinstance(b, str) or isinstance(a, str) and not isinstance(b, Decimal):
        return str(a) == str(b)
    return r3._close(a, b)


def compare(load3: Path, load4: Path, exports: Path, sc: dict) -> list[tuple[str, bool, str]]:
    ref = recompute(load3, load4, sc)
    specs = [
        ("v_beta", lambda r: ref["beta"].get((r["ticker"], r["benchmark"])), ["beta", "correlation", "months", "first_month", "last_month"]),
        ("v_wacc", lambda r: ref["wacc"].get(r["ticker"]), ["risk_free", "beta", "cost_of_equity", "cost_of_debt_pretax", "debt_weight", "wacc"]),
        ("v_peg", lambda r: ref["peg"].get(r["ticker"]), ["fwd_eps_growth", "peg_forward"]),
        ("v_scorecard_detail", lambda r: ref["detail"].get((r["ticker"], int(r["test_no"]))), ["value", "points", "result"]),
        ("v_scorecard", lambda r: ref["card"].get(r["ticker"]), ["total", "max_possible", "tests_scored"]),
    ]
    out = []
    for view, get, cols in specs:
        sql = pd.read_csv(exports / f"{view}.csv", dtype=str, keep_default_na=False)
        cells, bad, ex = 0, 0, []
        for _, r in sql.iterrows():
            o = get(r)
            if o is None:
                bad += 1
                ex.append(f"{r.iloc[0]} missing in Python")
                continue
            for c in cols:
                cells += 1
                pv = o[c]
                sv = r[c]
                if isinstance(pv, str):
                    ok = sv == pv
                elif isinstance(pv, int) and not isinstance(pv, bool):
                    ok = sv != "" and Decimal(sv) == pv
                else:
                    ok = r3._close(D(sv), pv)
                if not ok:
                    bad += 1
                    if len(ex) < 5:
                        ex.append(f"{r.iloc[0]} {r.iloc[1] if len(r) > 1 else ''} {c}: SQL {sv or 'NULL'} vs Python {pv}")
        out.append((f"V2_{view}_matches_python", bad == 0 and len(sql) > 0, f"{cells} cells compared, {bad} differ; {ex[:5] or ''}"))
    return out
