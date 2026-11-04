"""Step 6: DCF valuation in Python (the reference for the workbook's DCF and WACC tabs), sensitivities, reverse DCF
and the peer DCF table.

Unlevered FCF = EBIT x (1 - tax) + D&A - capex - (increase in receivables + inventory - payables); SBC is not added
back (it is a real cost, D6). Mid-year discounting from the valuation date; the first forecast year counts only the
part after the latest balance sheet (stub). Equity = EV + cash and short-term investments - debt + listed stakes.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yaml

import step5_model as m
from common import PROJECT_ROOT

DCF_CFG = PROJECT_ROOT / "config" / "dcf.yaml"
D = Decimal
INPUT_COLUMNS = ["ticker", "valuation_date", "price", "market_cap", "bs_date", "cash", "st_investments", "debt", "stakes",
                 "stakes_source", "diluted_shares", "shares_period_end", "latest_fy_end", "y1_end", "t_first", "y1_reported_revenue",
                 "stub_fraction", "beta_raw", "blume_weight", "blume_constant", "beta_adjusted", "risk_free", "erp", "cost_of_equity", "cost_of_debt",
                 "tax_rate", "debt_weight", "wacc", "terminal_growth", "exit_multiple", "w_bear", "w_base", "w_bull"]


STEP3 = PROJECT_ROOT / "data" / "clean" / "step3"
BETA = PROJECT_ROOT / "data" / "clean" / "step4" / "exports" / "v_beta.csv"


def missing_sources() -> list[str]:
    """Missing Step 6 inputs (empty list = all present)."""
    need = [STEP3 / "exports" / "v_valuation_cutoff.csv", STEP3 / "facts_extended.csv", BETA, DCF_CFG]
    return [str(p) for p in need if not p.exists()]


def payload(md: pd.DataFrame, at: pd.DataFrame) -> dict:
    """Everything the workbook and the CSV outputs need, computed from the Step 3-5 outputs and config/dcf.yaml."""
    rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731
    cfg = load_dcf_cfg()
    inp = inputs(md, at, rd(STEP3 / "exports" / "v_valuation_cutoff.csv"), rd(BETA), rd(STEP3 / "facts_extended.csv"), cfg)
    values, detail = value_all(md, at, inp)
    return {"cfg": cfg, "inputs": inp, "values": values, "detail": detail,
            "wacc_g": sensitivity_wacc_g(md, at, inp, cfg), "gm_sensitivity": sensitivity_growth_margin(md, at, inp, cfg),
            "reverse": reverse_dcf(md, at, inp), "wacc_grid": cfg["sensitivity"]["wacc"], "g_grid": cfg["sensitivity"]["growth"]}


def payload_or_none(md: pd.DataFrame, at: pd.DataFrame) -> dict | None:
    return None if missing_sources() else payload(md, at)


def load_dcf_cfg(path: Path = DCF_CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def inputs(md: pd.DataFrame, at: pd.DataFrame, val: pd.DataFrame, beta: pd.DataFrame, facts: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per company: every number the DCF needs, with its source in the data."""
    rows = []
    others_mult = {}
    for t in val["ticker"]:
        e = val[(val["ticker"] != t) & (val["ticker"] != "AMD") & (val["ev_ebitda"] != "")]["ev_ebitda"].astype(float)
        others_mult[t] = D(str(round(float(e.median()), 6)))
    for t in sorted(md["ticker"].unique()):
        v = val[val["ticker"] == t].iloc[0]
        years, h = m.history(md, t)
        g = md[(md["ticker"] == t) & (md["fiscal_year"].astype(int) == years[-1])]
        latest_fy_end = g["period_end"].iloc[0]
        y1_end = date.fromordinal(date.fromisoformat(latest_fy_end).toordinal() + 365)
        vdate = date.fromisoformat(v["cutoff_date"])
        q = facts[(facts["ticker"] == t) & (facts["support_item"] == "False") & facts["fiscal_period"].str.startswith("Q")]
        rev_q = q[(q["line_item"] == "revenue") & (q["fiscal_year"].astype(int) == years[-1] + 1)
                  & (q["period_end"] <= v["bs_date"]) & q["value_basis"].isin({"reported_quarter", "derived_quarter"})]
        rev_q = rev_q.sort_values("period_end").groupby("period_end").tail(1)
        sh = q[(q["line_item"] == "shares_diluted") & (q["value_basis"] == "reported_quarter") & (q["display_split_adjusted"] != "")]
        sh = sh.sort_values("period_end").iloc[-1]
        base = m.scenario(at, t, "Base")
        y1_rev = m.forecast(h, base)["revenue"][0]
        reported = sum((D(x) for x in rev_q["display_value"]), D(0))
        stub = max(D(0), 1 - reported / y1_rev) if y1_rev else D(1)
        b = beta[(beta["ticker"] == t) & (beta["benchmark"] == cfg["beta"]["benchmark"])].iloc[0]
        braw = D(b["beta"])
        badj = D(str(cfg["beta"]["blume_weight"])) * braw + D(str(cfg["beta"]["blume_constant"]))
        rf = D(v["risk_free_10y_pct"]) / 100
        erp = D(str(cfg["equity_risk_premium"]))
        ke = rf + badj * erp
        kd, tax = base["cost_of_debt"][0], base["tax_rate"][0]
        mcap, debt = D(v["market_cap"]), D(v["total_debt"])
        wd = debt / (debt + mcap)
        wacc = (1 - wd) * ke + wd * kd * (1 - tax)
        st = (cfg.get("non_operating_assets") or {}).get(t, {})
        stakes = sum((D(str(x["value"])) for x in st.values()), D(0))
        src = "; ".join(x["source"] for x in st.values())
        w = cfg["scenario_weights"]
        rows.append({"ticker": t, "valuation_date": v["cutoff_date"], "price": v["price"], "market_cap": v["market_cap"],
                     "bs_date": v["bs_date"], "cash": v["cash_and_equivalents"], "st_investments": v["st_investments"],
                     "debt": v["total_debt"], "stakes": str(stakes), "stakes_source": src,
                     "diluted_shares": sh["display_split_adjusted"], "shares_period_end": sh["period_end"],
                     "latest_fy_end": latest_fy_end, "y1_end": y1_end.isoformat(),
                     "t_first": str(round(D((y1_end - vdate).days) / D("365.25"), 6)), "y1_reported_revenue": str(reported),
                     "stub_fraction": str(round(stub, 6)), "beta_raw": str(braw), "blume_weight": str(cfg["beta"]["blume_weight"]),
                     "blume_constant": str(cfg["beta"]["blume_constant"]), "beta_adjusted": str(badj), "risk_free": str(rf),
                     "erp": str(erp), "cost_of_equity": str(ke), "cost_of_debt": str(kd), "tax_rate": str(tax),
                     "debt_weight": str(wd), "wacc": str(wacc), "terminal_growth": str(cfg["terminal"]["growth"]),
                     "exit_multiple": str(others_mult[t]), "w_bear": str(w["Bear"]), "w_base": str(w["Base"]), "w_bull": str(w["Bull"])})
    return pd.DataFrame(rows, columns=INPUT_COLUMNS)


def dcf(fc: dict, inp: dict, wacc: Decimal | None = None, g: Decimal | None = None) -> dict:
    """Value one forecast (step5_model.forecast output) with the inputs row inp (strings or Decimals)."""
    x = {k: (D(str(v)) if k not in ("ticker", "valuation_date", "bs_date", "stakes_source", "shares_period_end",
                                     "latest_fy_end", "y1_end") else v) for k, v in inp.items()}
    w = x["wacc"] if wacc is None else wacc
    gg = x["terminal_growth"] if g is None else g
    out = {k: [] for k in ("nopat", "ufcf", "fraction", "counted", "t", "df", "pv")}
    for i in range(5):
        tax = fc["income_tax"][i] / fc["pretax_income"][i] if fc["pretax_income"][i] else D(0)
        nopat = fc["operating_income"][i] * (1 - tax)
        dnwc = fc["change_ar"][i] + fc["change_inventory"][i] - fc["change_ap"][i]
        u = nopat + fc["depreciation_amortization"][i] - fc["capex"][i] - dnwc
        frac = x["stub_fraction"] if i == 0 else D(1)
        t = max(D(0), x["t_first"] - x["stub_fraction"] / 2) if i == 0 else x["t_first"] + i - D("0.5")
        df = 1 / (1 + w) ** t
        for k, val in (("nopat", nopat), ("ufcf", u), ("fraction", frac), ("counted", u * frac), ("t", t), ("df", df), ("pv", u * frac * df)):
            out[k].append(val)
    t_tv = x["t_first"] + 4
    df_tv = 1 / (1 + w) ** t_tv
    tv = out["ufcf"][4] * (1 + gg) / (w - gg)
    ebitda5 = fc["operating_income"][4] + fc["depreciation_amortization"][4]
    tv_exit = ebitda5 * x["exit_multiple"]
    pv_fcf = sum(out["pv"], D(0))
    bridge = x["cash"] + x["st_investments"] - x["debt"] + x["stakes"]
    ev = pv_fcf + tv * df_tv
    ev_exit = pv_fcf + tv_exit * df_tv
    out.update(t_tv=t_tv, df_tv=df_tv, tv=tv, tv_exit=tv_exit, ebitda5=ebitda5, pv_fcf=pv_fcf, pv_tv=tv * df_tv, ev=ev,
               ev_exit=ev_exit, bridge=bridge, equity=ev + bridge, per_share=(ev + bridge) / x["diluted_shares"],
               per_share_exit=(ev_exit + bridge) / x["diluted_shares"], tv_share=tv * df_tv / ev if ev else D(0),
               implied_exit_multiple=tv / ebitda5 if ebitda5 else D(0),
               wacc=w, g=gg, upside=(ev + bridge) / x["diluted_shares"] / x["price"] - 1)
    return out


def quality(inp_row: dict, base: dict) -> str:
    """Flags that make a peer's mechanical DCF unusable as a value (S6-D7); empty = no flag."""
    flags = []
    tax = D(inp_row["tax_rate"])
    if not D(0) <= tax <= D("0.35"):
        flags.append(f"Y1 tax rate {float(tax):.0%} outside 0-35% (history-derived peer default, I-58)")
    if base["per_share"] <= 0:
        flags.append("negative value: forecast unlevered FCF below zero")
    return "; ".join(flags)


def value_all(md: pd.DataFrame, at: pd.DataFrame, inp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per company: Bear / Base / Bull values and the weighted value; plus the year-by-year detail."""
    rows, detail = [], []
    for r in inp.to_dict("records"):
        t = r["ticker"]
        _, h = m.history(md, t)
        res = {s: dcf(m.forecast(h, m.scenario(at, t, s)), r) for s in ("Bear", "Base", "Bull")}
        wts = {s: D(r[f"w_{s.lower()}"]) for s in res}
        weighted = sum(wts[s] * res[s]["per_share"] for s in res)
        row = {"ticker": t, "price": r["price"], "wacc": f"{float(res['Base']['wacc']):.6f}", "terminal_growth": r["terminal_growth"]}
        for s, o in res.items():
            for k in ("ev", "equity", "per_share", "upside", "tv_share", "implied_exit_multiple", "per_share_exit"):
                row[f"{s.lower()}_{k}"] = f"{float(o[k]):.6f}"
            for k in ("nopat", "ufcf", "fraction", "counted", "t", "df", "pv"):
                detail.append([t, s, k] + [f"{float(v):.6f}" for v in o[k]])
        row["weighted_per_share"] = f"{float(weighted):.6f}"
        row["weighted_upside"] = f"{float(weighted / D(r['price']) - 1):.6f}"
        row["quality_flag"] = quality(r, res["Base"])
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(detail, columns=["ticker", "scenario", "row", "y1", "y2", "y3", "y4", "y5"])


def sensitivity_wacc_g(md, at, inp, cfg, ticker="NVDA", scenario="Base") -> pd.DataFrame:
    r = inp[inp["ticker"] == ticker].iloc[0].to_dict()
    _, h = m.history(md, ticker)
    fc = m.forecast(h, m.scenario(at, ticker, scenario))
    rows = []
    for w in cfg["sensitivity"]["wacc"]:
        rows.append([str(w)] + [f"{float(dcf(fc, r, D(str(w)), D(str(g)))['per_share']):.6f}" for g in cfg["sensitivity"]["growth"]])
    return pd.DataFrame(rows, columns=["wacc"] + [f"g_{g}" for g in cfg["sensitivity"]["growth"]])


def _shifted(a: dict, g2: Decimal, gm: Decimal) -> dict:
    b = {k: list(v) for k, v in a.items()}
    b["datacenter_growth"][1] = b["datacenter_growth"][1] + g2
    b["gross_margin"] = [x + gm for x in b["gross_margin"]]
    return b


def sensitivity_growth_margin(md, at, inp, cfg, ticker="NVDA", scenario="Base") -> pd.DataFrame:
    r = inp[inp["ticker"] == ticker].iloc[0].to_dict()
    _, h = m.history(md, ticker)
    a = m.scenario(at, ticker, scenario)
    rows = []
    for s in cfg["sensitivity"]["fy2_growth_shift"]:
        rows.append([str(a["datacenter_growth"][1] + D(str(s)))] +
                    [f"{float(dcf(m.forecast(h, _shifted(a, D(str(s)), D(str(gm)))), r)['per_share']):.6f}" for gm in cfg["sensitivity"]["gross_margin_shift"]])
    return pd.DataFrame(rows, columns=["fy2_segment_a_growth"] + [f"gm_shift_{x}" for x in cfg["sensitivity"]["gross_margin_shift"]])


def _bisect(f, lo: Decimal, hi: Decimal, n: int = 80) -> Decimal | None:
    """Root of a monotone function between lo and hi, or None if it does not change sign."""
    flo, fhi = f(lo), f(hi)
    if (flo > 0) == (fhi > 0):
        return None
    for _ in range(n):
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (flo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def reverse_dcf(md, at, inp, ticker="NVDA", scenario="Base") -> pd.DataFrame:
    """What the price implies, one lever at a time, everything else at the scenario's values:
    segment A growth in forecast year 2, the WACC, and the terminal growth at which value per share = price."""
    r = inp[inp["ticker"] == ticker].iloc[0].to_dict()
    _, h = m.history(md, ticker)
    a = m.scenario(at, ticker, scenario)
    price = D(r["price"])
    fc = m.forecast(h, a)
    w0, g0 = D(r["wacc"]), D(r["terminal_growth"])
    out = []
    s = _bisect(lambda x: dcf(m.forecast(h, _shifted(a, x, D(0))), r)["per_share"] - price, D(-0.95) - a["datacenter_growth"][1], D(3))
    if s is None:
        out.append([ticker, scenario, "fy2_segment_a_growth", str(a["datacenter_growth"][1]), "", "not solvable in range", ""])
    else:
        f2 = m.forecast(h, _shifted(a, s, D(0)))
        out.append([ticker, scenario, "fy2_segment_a_growth", str(a["datacenter_growth"][1]), f"{float(a['datacenter_growth'][1] + s):.6f}",
                    "solved", f"FY2 revenue {float(f2['revenue'][1]):,.0f} vs {float(fc['revenue'][1]):,.0f}; FY5 revenue {float(f2['revenue'][4]):,.0f} vs {float(fc['revenue'][4]):,.0f}"])
    w = _bisect(lambda x: dcf(fc, r, wacc=x)["per_share"] - price, g0 + D("0.005"), D("0.40"))
    out.append([ticker, scenario, "wacc", f"{float(w0):.6f}", "" if w is None else f"{float(w):.6f}", "not solvable in range" if w is None else "solved", ""])
    g = _bisect(lambda x: dcf(fc, r, g=x)["per_share"] - price, D("-0.05"), w0 - D("0.005"))
    out.append([ticker, scenario, "terminal_growth", str(g0), "" if g is None else f"{float(g):.6f}",
                "not solvable in range" if g is None else "solved",
                "" if g is not None else f"value at g = WACC - 0.5% is {float(dcf(fc, r, g=w0 - D('0.005'))['per_share']):.2f}, still below the price"])
    return pd.DataFrame(out, columns=["ticker", "scenario", "lever", "model_value", "implied_value", "status", "note"])


def engine_checks(md, at, inp, values) -> list[tuple]:
    """D1 g below WACC for every company; D2 scenario weights sum to 1; D3 unlevered FCF recomputed from the forecast
    statements (CFO - capex + after-tax interest less SBC and the non-cash add-backs) equals the DCF's; D4 weighted value
    lies between Bear and Bull."""
    res = []
    bad = [r["ticker"] for r in inp.to_dict("records") if not D(r["terminal_growth"]) < D(r["wacc"])]
    res.append(("D1_growth_below_wacc", not bad, f"{len(inp)} companies; failing {bad or 'none'}"))
    w = inp[["w_bear", "w_base", "w_bull"]].iloc[0].map(D).sum()
    res.append(("D2_scenario_weights_sum_to_1", w == 1, f"sum {w}"))
    worst = D(0)
    for r in inp.to_dict("records"):
        _, h = m.history(md, r["ticker"])
        for s in ("Bear", "Base", "Bull"):
            fc = m.forecast(h, m.scenario(at, r["ticker"], s))
            o = dcf(fc, r)
            for i in range(5):
                tax = fc["income_tax"][i] / fc["pretax_income"][i] if fc["pretax_income"][i] else D(0)
                alt = (fc["fcf"][i] - fc["sbc"][i] - (fc["interest_income"][i] - fc["interest_expense"][i]) * (1 - tax))
                worst = max(worst, abs(alt - o["ufcf"][i]))
    res.append(("D3_ufcf_recomputed_from_cash_flow", worst < D("0.001"), f"18 cases x 5 years; largest difference {float(worst):.2e}"))
    bad = [v["ticker"] for v in values.to_dict("records")
           if not min(D(v["bear_per_share"]), D(v["bull_per_share"])) <= D(v["weighted_per_share"]) <= max(D(v["bear_per_share"]), D(v["bull_per_share"]))]
    res.append(("D4_weighted_between_bear_and_bull", not bad, f"failing {bad or 'none'}"))
    return res
