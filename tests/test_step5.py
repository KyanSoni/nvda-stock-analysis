"""Step 5 offline tests: forecast equations, balance, peer defaults, history table and workbook structure.
Synthetic numbers chosen to be easy to check by hand; no network, no database, no LibreOffice."""
from decimal import Decimal

import pandas as pd
import pytest
from openpyxl import load_workbook

import build_model as b
import step5_facts as f5
import step5_model as m

D = Decimal


def hist(**over):
    h = {k: [D(0)] * 5 for k in m.HIST_ITEMS}
    base = dict(revenue=1000, datacenter_revenue=800, edge_revenue=200, cost_of_revenue=400, gross_profit=600, rd_expense=100,
                sga_expense=50, operating_income=450, interest_income=10, interest_expense=5, pretax_income=455, income_tax=55,
                net_income=400, shares_diluted_adj=100, eps_diluted_adj=4, depreciation_amortization=20, sbc=30,
                operating_cash_flow=420, capex=40, buybacks=100, dividends=10, cash_and_equivalents=300, st_investments=200,
                accounts_receivable=100, inventory=80, current_assets=720, ppe_net=150, total_assets=1000, accounts_payable=60,
                total_debt=100, total_liabilities=300, stockholders_equity=700)
    base.update(over)
    for k, v in base.items():
        h[k] = [D(v)] * 5
    return h


def flat(**over):
    a = {k: [D(0)] * 5 for k in m.DRIVERS}
    vals = dict(datacenter_growth="0.10", edge_growth="0.05", gross_margin="0.60", rd_pct_revenue="0.10", sga_pct_revenue="0.05",
                yield_on_cash="0.04", cost_of_debt="0.05", tax_rate="0.20", da_pct_revenue="0.02", capex_pct_revenue="0.04",
                dso_days="36.5", dio_days="73", dpo_days="36.5", sbc_pct_revenue="0.03", buyback_pct_fcf="0.5",
                dividend_payout="0.1", share_change="-0.01")
    vals.update(over)
    for k, v in vals.items():
        a[k] = [D(v)] * 5
    return a


def test_first_forecast_year_by_hand():
    f = m.forecast(hist(), flat())
    assert f["segment_a"][0] == D("880.00") and f["segment_b"][0] == D("210.00") and f["revenue"][0] == D("1090.00")
    assert f["cost_of_revenue"][0] == D("436.0000") and f["gross_profit"][0] == D("654.0000")
    assert f["operating_income"][0] == D("654.0000") - D("109.0000") - D("54.5000")
    assert f["interest_income"][0] == D("20.00") and f["interest_expense"][0] == D("5.00")   # 4% x 500 opening, 5% x 100
    assert f["accounts_receivable"][0] == D("109.000") and f["inventory"][0] == D("87.20000") and f["shares"][0] == D("99.00")


def test_balance_sheet_balances_every_year_in_odd_cases():
    cases = [flat(), flat(datacenter_growth="-0.5", gross_margin="0.05"), flat(net_debt_issuance="250", buyback_pct_fcf="1.2"),
             flat(tax_rate="0", dividend_payout="0", share_change="0.05")]
    for a in cases:
        f = m.forecast(hist(), a)
        assert max(abs(x) for x in f["balance_check"]) < D("1e-12")


def test_losses_do_not_create_buybacks_or_dividends():
    f = m.forecast(hist(), flat(gross_margin="0.01", rd_pct_revenue="0.5"))
    assert all(x < 0 for x in f["net_income"]) and all(x == 0 for x in f["dividends"])
    assert all(bb == 0 for bb, fcf in zip(f["buybacks"], f["fcf"]) if fcf <= 0)


def test_segments_default_to_total_revenue_without_datacenter_data():
    d = m.derived_history(hist(datacenter_revenue=0, edge_revenue=0))
    assert d["segment_a"][-1] == D(1000) and d["segment_b"][-1] == 0
    assert d["other_liabilities"][-1] == D(1000) - D(700) - D(60) - D(100)


def test_peer_defaults_use_consensus_then_fade():
    cfg = m.load_model_cfg()["peer_defaults"]
    a, reasons = m.peer_assumptions(hist(), D(1200), D(1380), "0.18", cfg)
    g = a["datacenter_growth"]["Base"]
    assert g[0] == D("0.2") and g[1] == D("0.15") and g[4] == D(str(cfg["terminal_growth"]))
    assert g[2] > g[3] > g[4] and a["datacenter_growth"]["Bear"][0] == D("0.1")
    assert a["gross_margin"]["Base"][0] == D("0.6") and a["tax_rate"]["Base"][0] == D("0.18")
    assert "consensus" in reasons["datacenter_growth"]


def test_annual_pick_takes_latest_period_end():
    s5 = f5.load_step5()
    rows = pd.DataFrame([{"line_item": "ppe_net", "fiscal_year": "2025", "fiscal_period": "Q4", "period_end": e, "period_start": "",
                          "value_basis": "reported_instant", "display_value": v} for e, v in (("2025-01-26", "1"), ("2025-01-28", "2"))])
    assert list(f5.annual(rows, s5)["display_value"]) == ["2"]


def test_edge_revenue_is_total_less_datacenter():
    a3 = pd.DataFrame([{"ticker": "NVDA", "fiscal_year": "2026", "period_end": "2026-01-25", **{i: "" for i in f5.STEP3_ITEMS}}])
    a3.loc[0, "revenue"] = "215938"
    picks = {"NVDA": pd.DataFrame([{"line_item": "datacenter_revenue", "fiscal_year": "2026", "period_end": "2026-01-25",
                                    "display_value": "193737", "value_basis": "manual_from_filing", "accn": "x", "concept": ""}])}
    md = f5.model_data(a3, picks, 5)
    assert md[md["line_item"] == "edge_revenue"]["value_m"].tolist() == ["22201"]


def test_workbook_forecast_cells_are_formulas(tmp_path):
    md = pd.DataFrame([["NVDA", k, y, f"{y}-01-25", str(v), "t"] for y in range(2022, 2027)
                       for k, v in [(k, list(map(float, hist()[k]))[0]) for k in m.HIST_ITEMS]], columns=f5.MODEL_COLUMNS)
    at = pd.DataFrame([["NVDA", d, s] + [str(v) for v in flat()[d]] + ["r", "test"] for d in m.DRIVERS for s in ("Bear", "Base", "Bull")],
                      columns=["ticker", "driver", "scenario", "y1", "y2", "y3", "y4", "y5", "reason", "source"])
    est = pd.DataFrame(columns=["ticker", "kind", "period", "avg"])
    path = b.build(md, at, est, tmp_path / "t.xlsx", {"built": "x", "cutoff": "x", "snapshot": "x"})
    wb = load_workbook(path)
    assert {"Cover", "Assumptions", "Historicals", "IS", "BS", "CF", "Schedules", "Data", "AssumptionsData"} <= set(wb.sheetnames)
    assert "Ticker" in wb.defined_names and "Scenario" in wb.defined_names
    typed = []
    for sh in ("IS", "BS", "CF", "Schedules"):
        ws = wb[sh]
        for row in ws.iter_rows(min_row=5, min_col=8, max_col=12):
            for c in row:
                if c.value is not None and not (isinstance(c.value, str) and c.value.startswith("=")):
                    typed.append(f"{sh}!{c.coordinate}")
    assert not typed, f"typed numbers in forecast columns: {typed[:5]}"
    codes = {ws_c.value for ws_c in wb["BS"]["A"] if ws_c.value}
    assert "bs_check" in codes and wb["Cover"]["C5"].value == "NVDA" and wb["Cover"]["C6"].value == 2
