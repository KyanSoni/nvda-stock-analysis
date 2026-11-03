"""Step 5a: model line items (config/step5.yaml) from the signed-off collection, and the model's history table.

  facts_model.csv   every selected value for the Step 5 line items, M1 columns + provenance (manual rows included)
  model_data.csv    one row per company, line item and fiscal year for the latest N fiscal years: the Step 3 annual view
                    (exports/v_annual.csv) plus the Step 5 items, in USD millions (EPS in USD, shares in millions)
Checks: F1 manual facts valid; F2 history complete for required tickers (error) / others (warning);
        F3 identities: gross profit = revenue - cost of revenue (NVIDIA, every model year, to $1m).
"""
from __future__ import annotations

import copy
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yaml

import step2_sec as s2
import step3_facts as s3f
from common import PROJECT_ROOT, write_csv

STEP5_CFG = PROJECT_ROOT / "config" / "step5.yaml"
STEP3_ITEMS = ["revenue", "gross_profit", "operating_income", "net_income", "eps_diluted_adj", "shares_diluted_adj",
               "income_tax", "pretax_income", "interest_expense", "depreciation_amortization", "sbc", "operating_cash_flow",
               "capex", "total_assets", "total_liabilities", "stockholders_equity", "cash_and_equivalents", "st_investments",
               "current_assets", "current_liabilities", "inventory", "total_debt"]
MODEL_COLUMNS = ["ticker", "line_item", "fiscal_year", "period_end", "value_m", "source"]


def load_step5(path: Path = STEP5_CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def company_config(base: dict, uni: dict, s5: dict, ticker: str) -> tuple[dict, dict]:
    cfg = copy.deepcopy(base)
    cfg["company"] = {"ticker": ticker, "cik": uni["companies"][ticker]["cik"],
                      "fiscal_year_end_month": uni["companies"][ticker]["fy_end_month"]}
    cfg["line_items"] = {k: {**copy.deepcopy(v), "derive_q4": False} for k, v in s5["line_items"].items()}
    for item, cands in ((s5.get("company_candidates") or {}).get(ticker) or {}).items():
        cfg["line_items"][item]["candidates"] = list(cands)
    guards = {}
    for item, fb in ((s5.get("guarded_fallbacks") or {}).get(ticker) or {}).items():
        cfg["line_items"][item]["candidates"].append(fb["concept"])
        guards[(item, fb["concept"])] = list(fb["guard_zero_or_absent"])
    return cfg, guards


def select(coll: Path, uni: dict, base: dict, s5: dict, ticker: str) -> tuple[pd.DataFrame, list[str]]:
    obs, _ = s2.load_company(coll, uni, ticker)
    cfg, guards = company_config(base, uni, s5, ticker)
    selectable = {k: v for k, v in cfg["line_items"].items() if v["candidates"]}
    sel = s2.select_company(obs, {**cfg, "line_items": selectable}, guards, ticker)
    for col in s3f.EXTRA_COLUMNS:
        sel[col] = ""
    manual, problems = s3f.manual_facts(PROJECT_ROOT / s5["manual_facts_file"], cfg, ticker, cfg["company"]["fiscal_year_end_month"])
    sel = pd.concat([sel, manual], ignore_index=True)
    for c in s3f.OUT_COLUMNS:
        if c not in sel.columns:
            sel[c] = ""
    return sel[s3f.OUT_COLUMNS], problems


def annual(sel: pd.DataFrame, s5: dict) -> pd.DataFrame:
    """One value per line item and fiscal year: FY flows, Q4 balances; the latest period end wins (as the SQL views)."""
    ptype = {k: v["period_type"] for k, v in s5["line_items"].items()}
    ok = sel[[(ptype[i] == "duration" and p == "FY") or (ptype[i] == "instant" and p == "Q4")
              for i, p in zip(sel["line_item"], sel["fiscal_period"])]]
    ok = ok[ok["value_basis"].isin({"reported_annual", "reported_instant", "manual_from_filing"})]
    ok = ok.sort_values(["line_item", "fiscal_year", "period_end", "period_start"]).groupby(["line_item", "fiscal_year"]).tail(1)
    return ok


def model_data(step3_annual: pd.DataFrame, picks: dict[str, pd.DataFrame], years: int) -> pd.DataFrame:
    rows = []
    for t, g in step3_annual.groupby("ticker"):
        g = g[g["revenue"].astype(str) != ""]
        last = sorted(g["fiscal_year"].astype(int))[-years:]
        for _, r in g[g["fiscal_year"].astype(int).isin(last)].iterrows():
            for item in STEP3_ITEMS:
                if str(r[item]) != "":
                    rows.append([t, item, int(r["fiscal_year"]), r["period_end"], str(r[item]), "Step 3 v_annual"])
        p = picks.get(t)
        if p is not None:
            for r in p[p["fiscal_year"].astype(int).isin(last)].itertuples():
                src = f"manual {r.accn}" if r.value_basis == "manual_from_filing" else f"{r.concept} {r.accn}"
                rows.append([t, r.line_item, int(r.fiscal_year), r.period_end, str(r.display_value), src])
    df = pd.DataFrame(rows, columns=MODEL_COLUMNS)
    # Edge Computing = total revenue - Data Center (NVIDIA, Q2 FY2027 10-Q market platforms), labelled derived
    dc = df[df["line_item"] == "datacenter_revenue"]
    for r in dc.itertuples():
        rev = df[(df["ticker"] == r.ticker) & (df["line_item"] == "revenue") & (df["fiscal_year"] == r.fiscal_year)]
        if len(rev) == 1:
            v = Decimal(rev.iloc[0]["value_m"]) - Decimal(r.value_m)
            rows.append([r.ticker, "edge_revenue", r.fiscal_year, r.period_end, str(v), "derived: revenue - datacenter_revenue"])
    return pd.DataFrame(rows, columns=MODEL_COLUMNS)


def checks(md: pd.DataFrame, s5: dict, problems: dict[str, list[str]]) -> list[tuple]:
    out = [("ALL", "F1_manual_facts_valid", not any(problems.values()),
            "; ".join(f"{t}: {p}" for t, ps in problems.items() for p in ps) or "valid", "error")]
    need = STEP3_ITEMS + [i for i in s5["line_items"] if i != "datacenter_revenue"]
    for t, g in md.groupby("ticker"):
        yrs = sorted(g["fiscal_year"].unique())
        have = set(zip(g["line_item"], g["fiscal_year"]))
        items = need + (["datacenter_revenue", "edge_revenue"] if t == "NVDA" else [])
        miss = [f"{i} FY{y}" for i in items for y in yrs if (i, y) not in have]
        lvl = "error" if t in s5["required_complete"] else "warning"
        out.append((t, "F2_model_history_complete", not miss, f"FY{yrs[0]}-FY{yrs[-1]}; missing {miss or 'none'}", lvl))
    n = md[md["ticker"] == "NVDA"]
    v = {(r.line_item, r.fiscal_year): Decimal(r.value_m) for r in n.itertuples()}
    bad = [y for y in sorted(n["fiscal_year"].unique())
           if all(k in v for k in (("revenue", y), ("cost_of_revenue", y), ("gross_profit", y)))
           and abs(v[("revenue", y)] - v[("cost_of_revenue", y)] - v[("gross_profit", y)]) > 1]
    out.append(("NVDA", "F3_gross_profit_identity", not bad, f"revenue - cost of revenue = gross profit; fails {bad or 'none'}", "error"))
    return out


def build(coll: Path, out: Path, uni: dict, base: dict, s5: dict, step3_exports: Path) -> list[tuple]:
    out.mkdir(parents=True, exist_ok=True)
    frames, picks, problems = [], {}, {}
    for t in uni["companies"]:
        sel, problems[t] = select(coll, uni, base, s5, t)
        frames.append(sel)
        picks[t] = annual(sel, s5)
    write_csv(pd.concat(frames, ignore_index=True), out / "facts_model.csv", s2.KEY)
    a3 = pd.read_csv(step3_exports / "v_annual.csv", dtype=str, keep_default_na=False)
    md = model_data(a3, picks, s5["history_years"])
    write_csv(md, out / "model_data.csv", ["ticker", "line_item", "fiscal_year"])
    res = checks(md, s5, problems)
    write_csv(pd.DataFrame(res, columns=["scope", "check", "passed", "detail", "level"]), out / "validation_step5.csv", ["scope", "check"])
    return res
