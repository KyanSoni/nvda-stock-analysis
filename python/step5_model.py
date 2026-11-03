"""Step 5b: the forecast model as plain Python (the reference the Excel formulas are checked against), and the
assumption table for every company.

The same equations are written as Excel formulas by build_model.py. Both read the same inputs: model_data.csv (history)
and assumptions.csv (drivers). Units: USD millions, shares in millions, rates as fractions.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd
import yaml

from common import PROJECT_ROOT

MODEL_CFG = PROJECT_ROOT / "config" / "model.yaml"
DRIVERS = ["datacenter_growth", "edge_growth", "gross_margin", "rd_pct_revenue", "sga_pct_revenue", "other_opex_pct_revenue",
           "yield_on_cash", "cost_of_debt", "tax_rate", "da_pct_revenue", "capex_pct_revenue", "dso_days", "dio_days",
           "dpo_days", "sbc_pct_revenue", "buyback_pct_fcf", "dividend_payout", "share_change", "net_debt_issuance"]
DRIVER_LABELS = {
    "datacenter_growth": ("Segment A growth (NVDA: Data Center; others: total revenue)", "%"),
    "edge_growth": ("Segment B growth (NVDA: Edge Computing)", "%"),
    "gross_margin": ("Gross margin", "%"), "rd_pct_revenue": ("R&D, % of revenue", "%"),
    "sga_pct_revenue": ("SG&A, % of revenue", "%"), "other_opex_pct_revenue": ("Other operating expense, % of revenue", "%"),
    "yield_on_cash": ("Interest yield on opening cash and investments", "%"), "cost_of_debt": ("Interest rate on opening debt", "%"),
    "tax_rate": ("Tax rate", "%"), "da_pct_revenue": ("D&A, % of revenue", "%"), "capex_pct_revenue": ("Capex, % of revenue", "%"),
    "dso_days": ("Receivable days (DSO)", "days"), "dio_days": ("Inventory days (DIO)", "days"), "dpo_days": ("Payable days (DPO)", "days"),
    "sbc_pct_revenue": ("Stock-based compensation, % of revenue", "%"), "buyback_pct_fcf": ("Buybacks, % of FCF", "%"),
    "dividend_payout": ("Dividends, % of net income", "%"), "share_change": ("Change in diluted shares", "%"),
    "net_debt_issuance": ("Net debt issuance ($m)", "$m"),
}
HIST_ITEMS = ["revenue", "datacenter_revenue", "edge_revenue", "cost_of_revenue", "gross_profit", "rd_expense", "sga_expense",
              "operating_income", "interest_income", "interest_expense", "pretax_income", "income_tax", "net_income",
              "shares_diluted_adj", "eps_diluted_adj", "depreciation_amortization", "sbc", "operating_cash_flow", "capex",
              "buybacks", "dividends", "cash_and_equivalents", "st_investments", "accounts_receivable", "inventory",
              "current_assets", "ppe_net", "total_assets", "accounts_payable", "total_debt", "total_liabilities",
              "stockholders_equity"]


def load_model_cfg(path: Path = MODEL_CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def history(md: pd.DataFrame, ticker: str) -> tuple[list[int], dict[str, list[Decimal]]]:
    """Five fiscal years, oldest first; a missing value is 0 (and is listed by checks F2)."""
    g = md[md["ticker"] == ticker]
    years = sorted(int(y) for y in g["fiscal_year"].unique())
    v = {(r.line_item, int(r.fiscal_year)): Decimal(str(r.value_m)) for r in g.itertuples()}
    return years, {i: [v.get((i, y), Decimal(0)) for y in years] for i in HIST_ITEMS}


def derived_history(h: dict[str, list[Decimal]]) -> dict[str, list[Decimal]]:
    d = {}
    n = len(h["revenue"])
    d["segment_a"] = [h["datacenter_revenue"][k] if h["datacenter_revenue"][k] > 0 else h["revenue"][k] for k in range(n)]
    d["segment_b"] = [h["revenue"][k] - d["segment_a"][k] for k in range(n)]
    d["other_opex"] = [h["gross_profit"][k] - h["rd_expense"][k] - h["sga_expense"][k] - h["operating_income"][k] for k in range(n)]
    d["cash_inv"] = [h["cash_and_equivalents"][k] + h["st_investments"][k] for k in range(n)]
    d["other_current_assets"] = [h["current_assets"][k] - d["cash_inv"][k] - h["accounts_receivable"][k] - h["inventory"][k] for k in range(n)]
    d["other_noncurrent_assets"] = [h["total_assets"][k] - h["current_assets"][k] - h["ppe_net"][k] for k in range(n)]
    d["other_liabilities"] = [h["total_assets"][k] - h["stockholders_equity"][k] - h["accounts_payable"][k] - h["total_debt"][k] for k in range(n)]
    d["other_nonoperating"] = [h["pretax_income"][k] - h["operating_income"][k] - h["interest_income"][k] + h["interest_expense"][k] for k in range(n)]
    d["fcf"] = [h["operating_cash_flow"][k] - h["capex"][k] for k in range(n)]
    return d


def forecast(h: dict[str, list[Decimal]], a: dict[str, list[Decimal]]) -> dict[str, list[Decimal]]:
    """a[driver] = five values for the chosen scenario. Returns every forecast row (five values)."""
    d = derived_history(h)
    p = {"segment_a": d["segment_a"][-1], "segment_b": d["segment_b"][-1], "cash_inv": d["cash_inv"][-1],
         "debt": h["total_debt"][-1], "ar": h["accounts_receivable"][-1], "inv": h["inventory"][-1],
         "ap": h["accounts_payable"][-1], "ppe": h["ppe_net"][-1], "equity": h["stockholders_equity"][-1],
         "shares": h["shares_diluted_adj"][-1], "oca": d["other_current_assets"][-1],
         "onca": d["other_noncurrent_assets"][-1], "ol": d["other_liabilities"][-1]}
    out = {k: [] for k in ["segment_a", "segment_b", "revenue", "cost_of_revenue", "gross_profit", "rd_expense", "sga_expense",
                           "other_opex", "operating_income", "interest_income", "interest_expense", "pretax_income", "income_tax",
                           "net_income", "shares", "eps", "depreciation_amortization", "sbc", "change_ar", "change_inventory",
                           "change_ap", "operating_cash_flow", "capex", "fcf", "buybacks", "dividends", "debt_issuance",
                           "net_change_cash", "cash_inv", "accounts_receivable", "inventory", "other_current_assets", "ppe_net",
                           "other_noncurrent_assets", "total_assets", "accounts_payable", "total_debt", "other_liabilities",
                           "stockholders_equity", "total_liabilities_equity", "balance_check"]}
    for t in range(5):
        g = lambda k: a[k][t]  # noqa: E731
        sa = p["segment_a"] * (1 + g("datacenter_growth"))
        sb = p["segment_b"] * (1 + g("edge_growth"))
        rev = sa + sb
        cogs = rev * (1 - g("gross_margin"))
        gp = rev - cogs
        rd, sga, oth = rev * g("rd_pct_revenue"), rev * g("sga_pct_revenue"), rev * g("other_opex_pct_revenue")
        ebit = gp - rd - sga - oth
        ii = g("yield_on_cash") * p["cash_inv"]
        ie = g("cost_of_debt") * p["debt"]
        pre = ebit + ii - ie
        tax = pre * g("tax_rate")
        ni = pre - tax
        shares = p["shares"] * (1 + g("share_change"))
        da, sbc = rev * g("da_pct_revenue"), rev * g("sbc_pct_revenue")
        ar = rev * g("dso_days") / 365
        inv = cogs * g("dio_days") / 365
        ap = cogs * g("dpo_days") / 365
        car, cinv, cap = ar - p["ar"], inv - p["inv"], ap - p["ap"]
        cfo = ni + da + sbc - car - cinv + cap
        capex = rev * g("capex_pct_revenue")
        fcf = cfo - capex
        bb = max(fcf, Decimal(0)) * g("buyback_pct_fcf")
        div = max(ni, Decimal(0)) * g("dividend_payout")
        iss = g("net_debt_issuance")
        dcash = fcf - bb - div + iss
        cash = p["cash_inv"] + dcash
        ppe = p["ppe"] + capex - da
        debt = p["debt"] + iss
        eq = p["equity"] + ni + sbc - bb - div
        ta = cash + ar + inv + p["oca"] + ppe + p["onca"]
        tle = ap + debt + p["ol"] + eq
        row = dict(segment_a=sa, segment_b=sb, revenue=rev, cost_of_revenue=cogs, gross_profit=gp, rd_expense=rd, sga_expense=sga,
                   other_opex=oth, operating_income=ebit, interest_income=ii, interest_expense=ie, pretax_income=pre, income_tax=tax,
                   net_income=ni, shares=shares, eps=ni / shares if shares else Decimal(0), depreciation_amortization=da, sbc=sbc,
                   change_ar=car, change_inventory=cinv, change_ap=cap, operating_cash_flow=cfo, capex=capex, fcf=fcf,
                   buybacks=bb, dividends=div, debt_issuance=iss, net_change_cash=dcash, cash_inv=cash, accounts_receivable=ar,
                   inventory=inv, other_current_assets=p["oca"], ppe_net=ppe, other_noncurrent_assets=p["onca"], total_assets=ta,
                   accounts_payable=ap, total_debt=debt, other_liabilities=p["ol"], stockholders_equity=eq,
                   total_liabilities_equity=tle, balance_check=ta - tle)
        for k, v in row.items():
            out[k].append(v)
        p.update(segment_a=sa, segment_b=sb, cash_inv=cash, debt=debt, ar=ar, inv=inv, ap=ap, ppe=ppe, equity=eq, shares=shares)
    return out


# ---------------------------------------------------------------- assumptions for every company

def _q(x) -> Decimal:
    return Decimal(str(round(float(x), 6)))


def peer_assumptions(h: dict, rev0y, rev1y, tax_used, pd_cfg: dict) -> tuple[dict, dict]:
    """Mechanical defaults (S5-D6): consensus growth for years 1-2, linear fade to terminal growth by year 5,
    every other driver at its latest-year value. Returns ({driver: {scenario: [5]}}, {driver: reason})."""
    d = derived_history(h)
    last = {k: v[-1] for k, v in {**h, **d}.items()}
    rev = last["revenue"]
    g1 = rev0y / rev - 1 if rev0y and rev else Decimal("0.05")
    g2 = rev1y / rev0y - 1 if rev1y and rev0y else g1
    term = Decimal(str(pd_cfg["terminal_growth"]))
    base_g = [g1, g2] + [g2 + (term - g2) * k / 3 for k in (1, 2, 3)]
    div0 = lambda a, b: a / b if b else Decimal(0)  # noqa: E731
    gm = div0(last["gross_profit"], rev)
    fcf = last["fcf"]
    debt_prev = h["total_debt"][-2] if len(h["total_debt"]) > 1 else last["total_debt"]
    vals = {
        "datacenter_growth": base_g, "edge_growth": [Decimal(0)] * 5, "gross_margin": [gm] * 5,
        "rd_pct_revenue": [div0(last["rd_expense"], rev)] * 5, "sga_pct_revenue": [div0(last["sga_expense"], rev)] * 5,
        "other_opex_pct_revenue": [div0(last["other_opex"], rev)] * 5,
        "yield_on_cash": [Decimal(str(pd_cfg["yield_on_cash"]))] * 5,
        "cost_of_debt": [div0(last["interest_expense"], debt_prev) if debt_prev and last["interest_expense"] else Decimal(str(pd_cfg["cost_of_debt_if_unknown"]))] * 5,
        "tax_rate": [Decimal(str(tax_used)) if tax_used not in (None, "") else Decimal(str(pd_cfg["tax_rate_if_unknown"]))] * 5,
        "da_pct_revenue": [div0(last["depreciation_amortization"], rev)] * 5, "capex_pct_revenue": [div0(last["capex"], rev)] * 5,
        "dso_days": [div0(last["accounts_receivable"], rev) * 365] * 5,
        "dio_days": [div0(last["inventory"], last["cost_of_revenue"]) * 365] * 5,
        "dpo_days": [div0(last["accounts_payable"], last["cost_of_revenue"]) * 365] * 5,
        "sbc_pct_revenue": [div0(last["sbc"], rev)] * 5,
        "buyback_pct_fcf": [min(max(div0(last["buybacks"], fcf), Decimal(0)), Decimal(1)) if fcf > 0 else Decimal(0)] * 5,
        "dividend_payout": [min(max(div0(last["dividends"], last["net_income"]), Decimal(0)), Decimal(1)) if last["net_income"] > 0 else Decimal(0)] * 5,
        "share_change": [Decimal(0)] * 5, "net_debt_issuance": [Decimal(0)] * 5,
    }
    out = {}
    for k, v in vals.items():
        v = [_q(x) for x in v]
        if k == "datacenter_growth":
            out[k] = {"Bear": [_q(x + Decimal(str(pd_cfg["bear_growth_shift"]))) for x in v], "Base": v,
                      "Bull": [_q(x + Decimal(str(pd_cfg["bull_growth_shift"]))) for x in v]}
        elif k == "gross_margin":
            out[k] = {"Bear": [_q(x + Decimal(str(pd_cfg["bear_margin_shift"]))) for x in v], "Base": v,
                      "Bull": [_q(x + Decimal(str(pd_cfg["bull_margin_shift"]))) for x in v]}
        else:
            out[k] = {"Bear": v, "Base": v, "Bull": v}
    reasons = {k: "Mechanical peer default (S5-D6): latest fiscal year's value, all scenarios" for k in vals}
    reasons["datacenter_growth"] = ("Mechanical peer default (S5-D6): years 1-2 = consensus revenue growth (Step 4 snapshot), "
                                    f"linear fade to {pd_cfg['terminal_growth']:.0%} by year 5; Bear/Bull +/-10pt")
    reasons["gross_margin"] = "Mechanical peer default (S5-D6): latest fiscal year; Bear -2pt, Bull +1pt"
    reasons["edge_growth"] = "Not used for this company (single revenue line)"
    reasons["yield_on_cash"] = f"Mechanical peer default (S5-D6): {pd_cfg['yield_on_cash']:.0%}"
    return out, reasons


def assumption_table(md: pd.DataFrame, mcfg: dict, estimates: pd.DataFrame, ratios: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in sorted(md["ticker"].unique()):
        if t in mcfg:
            a = {k: {s: [_q(x) for x in mcfg[t][k][s]] for s in mcfg["scenarios"]} for k in DRIVERS}
            reasons = {k: mcfg[t][k]["reason"] for k in DRIVERS}
            source = "config/model.yaml (argued)"
        else:
            years, h = history(md, t)
            e = estimates[(estimates["ticker"] == t) & (estimates["kind"] == "revenue")].set_index("period")["avg"]
            r0 = Decimal(e["0y"]) / 1_000_000 if "0y" in e and e["0y"] else None
            r1 = Decimal(e["+1y"]) / 1_000_000 if "+1y" in e and e["+1y"] else None
            rr = ratios[(ratios["ticker"] == t) & (ratios["fiscal_year"].astype(int) == years[-1])]
            tax = rr.iloc[0]["tax_rate_used"] if len(rr) else None
            a, reasons = peer_assumptions(h, r0, r1, tax, mcfg["peer_defaults"])
            source = "generated (S5-D6)"
        for k in DRIVERS:
            for s in mcfg["scenarios"]:
                rows.append([t, k, s] + [str(x) for x in a[k][s]] + [reasons[k], source])
    return pd.DataFrame(rows, columns=["ticker", "driver", "scenario", "y1", "y2", "y3", "y4", "y5", "reason", "source"])


def scenario(at: pd.DataFrame, ticker: str, name: str) -> dict[str, list[Decimal]]:
    x = at[(at["ticker"] == ticker) & (at["scenario"] == name)]
    return {r.driver: [Decimal(getattr(r, f"y{k}")) for k in range(1, 6)] for r in x.itertuples()}
