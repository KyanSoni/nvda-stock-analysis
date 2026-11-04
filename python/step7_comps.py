"""Step 7: comparable companies analysis for NVIDIA (the reference for the workbook's Comps tab).

Inputs, all already verified upstream: Step 3 v_valuation_cutoff (price, market cap, debt, cash, LTM revenue, EBITDA,
net income, P/E) and v_ratios_ltm (gross margin, LTM growth); Step 4 consensus estimates (0y / +1y revenue and EPS);
Step 6 dcf_inputs (diluted shares, listed stakes, fiscal-year ends) and dcf_values; Step 2 daily prices (52-week range).
NTM figures are calendarised to the twelve months after the valuation date (S7-D2). Nothing here fetches data.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from common import PROJECT_ROOT

CFG = PROJECT_ROOT / "config" / "comps.yaml"
CLEAN = PROJECT_ROOT / "data" / "clean"
MULTIPLES = {  # multiple -> (numerator, denominator, label)
    "ev_revenue_ntm": ("ev", "revenue_ntm", "EV / revenue, NTM"),
    "ev_ebitda_ntm": ("ev", "ebitda_ntm", "EV / EBITDA, NTM"),
    "pe_ntm": ("price", "eps_ntm", "P / E, NTM"),
    "ev_revenue_ltm": ("ev", "revenue_ltm", "EV / revenue, LTM"),
    "ev_ebitda_ltm": ("ev", "ebitda_ltm", "EV / EBITDA, LTM"),
    "pe_ltm": ("price", "eps_ltm", "P / E, LTM"),
}
TABLE_COLUMNS = ["ticker", "role", "price", "diluted_shares", "market_cap", "debt", "cash", "st_investments", "stakes", "net_debt", "ev",
                 "fy0_end", "w_fy0", "revenue_fy0", "revenue_fy1", "revenue_ntm", "revenue_ltm", "growth_ntm", "growth_ltm",
                 "gross_margin_ltm", "ebitda_ltm", "ebitda_margin_ltm", "ebitda_ntm", "eps_fy0", "eps_fy1", "eps_ntm", "eps_ltm",
                 "net_income_ltm", "low_52w", "high_52w", "ebitda_basis"] + list(MULTIPLES) + [f"use_{k}" for k in MULTIPLES]


def load_cfg(path: Path = CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def read_inputs(dcf_payload: dict | None = None) -> dict:
    """dcf_payload: a fresh step6_dcf.payload, used instead of the Step 6 CSVs (so a rebuild never mixes old DCF values)."""
    rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731
    if dcf_payload is not None:
        return {"val": rd(CLEAN / "step3" / "exports" / "v_valuation_cutoff.csv"), "rat": rd(CLEAN / "step3" / "exports" / "v_ratios_ltm.csv"),
                "est": rd(CLEAN / "step4" / "estimates.csv"), "dcf_in": dcf_payload["inputs"], "dcf_val": dcf_payload["values"],
                "wacc_g": dcf_payload["wacc_g"], "prices": rd(CLEAN / "step2" / "market" / "prices.csv")}
    return {"val": rd(CLEAN / "step3" / "exports" / "v_valuation_cutoff.csv"),
            "rat": rd(CLEAN / "step3" / "exports" / "v_ratios_ltm.csv"),
            "est": rd(CLEAN / "step4" / "estimates.csv"),
            "dcf_in": rd(CLEAN / "step6" / "dcf_inputs.csv"),
            "dcf_val": rd(CLEAN / "step6" / "dcf_values.csv"),
            "wacc_g": rd(CLEAN / "step6" / "sensitivity_wacc_g.csv"),
            "prices": rd(CLEAN / "step2" / "market" / "prices.csv")}


def missing_inputs(with_step6_outputs: bool = True) -> list[str]:
    need = [CLEAN / "step3" / "exports" / "v_valuation_cutoff.csv", CLEAN / "step3" / "exports" / "v_ratios_ltm.csv",
            CLEAN / "step4" / "estimates.csv", CLEAN / "step6" / "dcf_inputs.csv", CLEAN / "step6" / "dcf_values.csv",
            CLEAN / "step6" / "sensitivity_wacc_g.csv", CLEAN / "step2" / "market" / "prices.csv", CFG]
    if not with_step6_outputs:
        need = [p for p in need if "step6" not in p.parts]
    return [str(p) for p in need if not p.exists()]


def payload_or_none(dcf_payload: dict | None) -> dict | None:
    """The Comps-tab payload when Step 6 ran in this build and the Step 2-4 inputs exist; otherwise None."""
    if dcf_payload is None or missing_inputs(with_step6_outputs=False):
        return None
    inp = read_inputs(dcf_payload)
    if set(inp["dcf_in"]["ticker"]) != set(inp["val"]["ticker"]):     # a DCF for other companies (e.g. a test): no Comps tab
        return None
    return run(inp=inp)


def f(x) -> float | None:
    return None if x in ("", None) else float(x)


def table(inp: dict, cfg: dict) -> pd.DataFrame:
    """One row per company: inputs, calendarised NTM figures, multiples and whether each multiple enters the statistics."""
    val, est, din = inp["val"], inp["est"], inp["dcf_in"].set_index("ticker")
    rat = inp["rat"]
    px = inp["prices"]
    rows = []
    for v in val.to_dict("records"):
        t = v["ticker"]
        d = din.loc[t]
        vdate = date.fromisoformat(v["cutoff_date"])
        fy0_end = date.fromisoformat(d["y1_end"])
        w = min(1.0, max(0.0, (fy0_end - vdate).days / cfg["ntm"]["year_days"]))
        e = est[est["ticker"] == t].set_index(["kind", "period"])["avg"]
        rev0, rev1 = float(e[("revenue", "0y")]) / 1e6, float(e[("revenue", "+1y")]) / 1e6
        eps0, eps1 = float(e[("eps", "0y")]), float(e[("eps", "+1y")])
        r = rat[(rat["ticker"] == t) & (rat["period_end"] == v["ltm_period_end"])].iloc[0]
        price, mcap = float(v["price"]), float(v["market_cap"])
        debt, cash, sti, stakes = float(v["total_debt"]), float(v["cash_and_equivalents"]), float(v["st_investments"] or 0), float(d["stakes"])
        ev = mcap + debt - cash - sti - stakes
        rev_ltm = float(v["ltm_revenue"])
        fy_basis = t in cfg["exclusions"]["ebitda_fy_basis"]
        ebitda_ltm = float(v["ebitda_used"])
        margin = None if fy_basis else ebitda_ltm / rev_ltm
        rev_ntm = w * rev0 + (1 - w) * rev1
        shares = float(d["diluted_shares"])
        ni = float(v["ltm_net_income"])
        p = px[(px["ticker"] == t) & (px["date"] > (vdate.replace(year=vdate.year - 1)).isoformat()) & (px["date"] <= vdate.isoformat())]
        row = {"ticker": t, "role": v["role"], "price": price, "diluted_shares": shares, "market_cap": mcap, "debt": debt,
               "cash": cash, "st_investments": sti, "stakes": stakes, "net_debt": debt - cash - sti, "ev": ev,
               "fy0_end": fy0_end.isoformat(), "w_fy0": w, "revenue_fy0": rev0, "revenue_fy1": rev1, "revenue_ntm": rev_ntm,
               "revenue_ltm": rev_ltm, "growth_ntm": rev_ntm / rev_ltm - 1, "growth_ltm": f(r["ltm_revenue_growth"]),
               "gross_margin_ltm": f(r["ltm_gross_margin"]), "ebitda_ltm": None if fy_basis else ebitda_ltm,
               "ebitda_margin_ltm": margin, "ebitda_ntm": None if margin is None else rev_ntm * margin,
               "eps_fy0": eps0, "eps_fy1": eps1, "eps_ntm": w * eps0 + (1 - w) * eps1, "eps_ltm": ni / shares, "net_income_ltm": ni,
               "low_52w": p["close"].astype(float).min(), "high_52w": p["close"].astype(float).max(), "ebitda_basis": v["ebitda_basis"]}
        for k, (num, den, _) in MULTIPLES.items():
            dv = row[den]
            row[k] = None if dv is None or dv <= 0 else row[num] / dv
            ok = row[k] is not None and row[k] <= cfg["exclusions"]["max_multiple"] and v["role"] != "target"
            row[f"use_{k}"] = int(ok)
        rows.append(row)
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def stats(tb: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Peer statistics per multiple (target excluded; excluded multiples left out)."""
    out = []
    for k in MULTIPLES:
        s = tb.loc[tb[f"use_{k}"] == 1, k].astype(float)
        row = {"multiple": k, "label": MULTIPLES[k][2], "n": len(s), "peers": " ".join(tb.loc[tb[f"use_{k}"] == 1, "ticker"]),
               "min": s.min(), "max": s.max()}
        for q in cfg["percentiles"]:
            row[f"p{q}"] = s.quantile(q / 100) if len(s) else None
        out.append(row)
    return pd.DataFrame(out)


def implied(tb: pd.DataFrame, st: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """NVIDIA value per share at each peer statistic: EV multiples go through the Step 6 bridge; P/E applies directly."""
    n = tb[tb["ticker"] == cfg["target"]].iloc[0]
    bridge = n["cash"] + n["st_investments"] + n["stakes"] - n["debt"]
    out = []
    for s in st.to_dict("records"):
        k = s["multiple"]
        num, den, _ = MULTIPLES[k]
        metric = n[den]
        row = {"multiple": k, "label": s["label"], "nvda_metric": metric, "nvda_multiple": n[k]}
        for c in ("min", "p25", "p50", "p75", "max"):
            m = s[c]
            if m is None or pd.isna(m) or metric is None:
                row[c] = None
            elif num == "price":
                row[c] = m * metric
            else:
                row[c] = (m * metric + bridge) / n["diluted_shares"]
        out.append(row)
    return pd.DataFrame(out)


def regression(tb: pd.DataFrame, cfg: dict) -> dict:
    """Peers' NTM EV/revenue on NTM revenue growth (ordinary least squares, target excluded); NVIDIA's multiple on the line."""
    p = tb[(tb["role"] != "target") & tb["ev_revenue_ntm"].notna()]
    x, y = p["growth_ntm"].astype(float), p["ev_revenue_ntm"].astype(float)
    xm, ym = x.mean(), y.mean()
    slope = ((x - xm) * (y - ym)).sum() / ((x - xm) ** 2).sum()
    icpt = ym - slope * xm
    r2 = 1 - ((y - (icpt + slope * x)) ** 2).sum() / ((y - ym) ** 2).sum()
    n = tb[tb["ticker"] == cfg["target"]].iloc[0]
    fit = icpt + slope * n["growth_ntm"]
    bridge = n["cash"] + n["st_investments"] + n["stakes"] - n["debt"]
    return {"slope": slope, "intercept": icpt, "r2": r2, "n": len(p), "nvda_growth_ntm": n["growth_ntm"],
            "nvda_ev_revenue_ntm": n["ev_revenue_ntm"], "fitted_ev_revenue_ntm": fit,
            "implied_price": (fit * n["revenue_ntm"] + bridge) / n["diluted_shares"]}


def football(tb: pd.DataFrame, imp: pd.DataFrame, inp: dict, cfg: dict) -> pd.DataFrame:
    n = tb[tb["ticker"] == cfg["target"]].iloc[0]
    v = inp["dcf_val"].set_index("ticker").loc[cfg["target"]]
    g = inp["wacc_g"].copy()
    s = cfg["football_field"]["dcf_sensitivity"]
    g["w"] = g["wacc"].astype(float)
    cols = [c for c in g.columns if c.startswith("g_") and s["growth"][0] - 1e-9 <= float(c[2:]) <= s["growth"][1] + 1e-9]
    sub = g[(g["w"] >= s["wacc"][0] - 1e-9) & (g["w"] <= s["wacc"][1] + 1e-9)][cols].astype(float)
    i = imp.set_index("multiple")
    rows = [("52-week range", n["low_52w"], n["high_52w"], n["price"], "Step 2 daily closes, 12 months to the cutoff; marker = price"),
            ("DCF Bear to Bull", float(v["bear_per_share"]), float(v["bull_per_share"]), float(v["base_per_share"]),
             "Step 6; marker = Base; probability-weighted " + f"{float(v['weighted_per_share']):.2f}"),
            ("DCF, WACC 12-15%, g 2.5-3.5%", float(sub.min().min()), float(sub.max().max()), float(v["base_per_share"]), "Step 6 Base grid; marker = Base")]
    for k in ("pe_ntm", "ev_ebitda_ntm", "ev_revenue_ntm", "ev_ebitda_ltm"):
        rows.append((f"Comps {MULTIPLES[k][2]}", i.loc[k, "p25"], i.loc[k, "p75"], i.loc[k, "p50"],
                     "peer 25th-75th percentile applied to NVIDIA; marker = median"))
    return pd.DataFrame(rows, columns=["method", "low", "high", "point", "note"])


def blend(tb: pd.DataFrame, imp: pd.DataFrame, inp: dict, cfg: dict) -> dict:
    i = imp.set_index("multiple")
    comps = sum(i.loc[k, "p50"] for k in cfg["multiples"]["headline"]) / len(cfg["multiples"]["headline"])
    dcf = float(inp["dcf_val"].set_index("ticker").loc[cfg["target"], "weighted_per_share"])
    b = cfg["blend"]
    price = float(tb[tb["ticker"] == cfg["target"]].iloc[0]["price"])
    value = b["dcf"] * dcf + b["comps"] * comps
    return {"dcf_weighted": dcf, "comps_value": comps, "w_dcf": b["dcf"], "w_comps": b["comps"], "blended_value": value,
            "price": price, "upside": value / price - 1}


def run(cfg: dict | None = None, inp: dict | None = None) -> dict:
    cfg = cfg or load_cfg()
    inp = inp or read_inputs()
    tb = table(inp, cfg)
    st = stats(tb, cfg)
    imp = implied(tb, st, cfg)
    reg = regression(tb, cfg)
    return {"cfg": cfg, "table": tb, "stats": st, "implied": imp, "regression": reg, "football": football(tb, imp, inp, cfg),
            "blend": blend(tb, imp, inp, cfg), "valuation_date": inp["val"]["cutoff_date"].iloc[0]}


def checks(res: dict) -> list[tuple]:
    """C1 NTM weights in [0, 1] and NTM between the two fiscal years; C2 EV = market cap + net debt - stakes; C3 target never
    in the statistics; C4 each headline multiple has at least 3 peers; C5 blend weights sum to 1; C6 percentiles ordered."""
    tb, st = res["table"], res["stats"]
    out = []
    ok = all(0 <= w <= 1 for w in tb["w_fy0"]) and all(min(a, b) - 1e-9 <= c <= max(a, b) + 1e-9
                                                      for a, b, c in zip(tb["revenue_fy0"], tb["revenue_fy1"], tb["revenue_ntm"]))
    out.append(("C1_ntm_calendarisation", ok, "w " + ", ".join(f"{t} {w:.3f}" for t, w in zip(tb["ticker"], tb["w_fy0"]))))
    err = max(abs(r.ev - (r.market_cap + r.net_debt - r.stakes)) for r in tb.itertuples())
    out.append(("C2_ev_bridge", err < 1e-6, f"largest difference {err:.2e}"))
    t = tb[tb["role"] == "target"]
    out.append(("C3_target_excluded_from_stats", int(t[[f"use_{k}" for k in MULTIPLES]].to_numpy().sum()) == 0, "NVDA in no statistic"))
    thin = [r["multiple"] for r in st.to_dict("records") if r["multiple"] in res["cfg"]["multiples"]["headline"] and r["n"] < 3]
    out.append(("C4_headline_multiples_have_3_peers", not thin, "n = " + ", ".join(f"{r['multiple']} {r['n']}" for r in st.to_dict("records"))))
    b = res["blend"]
    out.append(("C5_blend_weights_sum_to_1", abs(b["w_dcf"] + b["w_comps"] - 1) < 1e-12, f"DCF {b['w_dcf']}, comps {b['w_comps']}"))
    bad = [r["multiple"] for r in st.to_dict("records") if r["n"] and not r["min"] <= r["p25"] <= r["p50"] <= r["p75"] <= r["max"]]
    out.append(("C6_percentiles_ordered", not bad, f"failing {bad or 'none'}"))
    return out
