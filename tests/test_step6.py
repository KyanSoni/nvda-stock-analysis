"""Step 6 offline tests: the DCF arithmetic by hand, discount timing, the bridge to equity, the reverse DCF, the peer
quality flags and the workbook's DCF tabs. Synthetic numbers; no network, no database, no LibreOffice."""
from decimal import Decimal

import pandas as pd
from openpyxl import load_workbook

import build_model as b
import step6_dcf as d
from test_step5 import flat, hist

import step5_facts as f5
import step5_model as m

D = Decimal


def fc_const(**over):
    v = dict(operating_income=100, pretax_income=100, income_tax=20, depreciation_amortization=10, capex=15,
             change_ar=5, change_inventory=3, change_ap=2)
    v.update(over)
    return {k: [D(x)] * 5 for k, x in v.items()}


def inp(**over):
    r = dict(ticker="TEST", wacc="0.10", terminal_growth="0.02", stub_fraction="0.5", t_first="0.25", cash="50",
             st_investments="30", debt="40", stakes="10", diluted_shares="10", price="100", exit_multiple="10")
    r.update(over)
    return r


def test_ufcf_and_value_by_hand():
    o = d.dcf(fc_const(), inp())
    assert o["nopat"][0] == D(80) and o["ufcf"][0] == D(69)          # 100 x (1 - 20%) + 10 - 15 - (5 + 3 - 2)
    assert o["counted"][0] == D("34.5") and o["counted"][1] == D(69)  # half of year 1 still to come
    assert o["t"] == [D(0), D("0.75"), D("1.75"), D("2.75"), D("3.75")]
    pv = 34.5 + sum(69 / 1.1 ** t for t in (0.75, 1.75, 2.75, 3.75))
    tv = 69 * 1.02 / 0.08
    ev = pv + tv / 1.1 ** 4.25
    assert abs(float(o["tv"]) - tv) < 1e-9 and abs(float(o["ev"]) - ev) < 1e-9
    assert float(o["bridge"]) == 50 + 30 - 40 + 10
    assert abs(float(o["per_share"]) - (ev + 50) / 10) < 1e-9
    assert abs(float(o["implied_exit_multiple"]) - tv / 110) < 1e-9
    assert abs(float(o["per_share_exit"]) - (pv + 1100 / 1.1 ** 4.25 + 50) / 10) < 1e-9


def test_discount_time_never_negative_when_year_1_already_ended():
    o = d.dcf(fc_const(), inp(t_first="-0.1", stub_fraction="0.25"))   # QCOM-like: fiscal year over, 10-K not yet filed
    assert o["t"][0] == 0 and o["t"][1] == D("0.4") and o["df"][0] == 1


def test_higher_wacc_lowers_value_and_higher_growth_raises_it():
    base = d.dcf(fc_const(), inp())["per_share"]
    assert d.dcf(fc_const(), inp(), wacc=D("0.12"))["per_share"] < base < d.dcf(fc_const(), inp(), g=D("0.03"))["per_share"]


def test_bisection_finds_the_root_or_says_none():
    assert abs(d._bisect(lambda x: x * x - 2, D(0), D(2)) - D(2).sqrt()) < D("1e-15")
    assert d._bisect(lambda x: x * x + 1, D(0), D(2)) is None


def test_quality_flags_distorted_peer_tax_and_negative_value():
    assert d.quality({"tax_rate": "0.17"}, {"per_share": D(10)}) == ""
    q = d.quality({"tax_rate": "0.98"}, {"per_share": D(-1)})
    assert "98%" in q and "negative" in q


def synthetic():
    md = pd.DataFrame([["NVDA", k, y, f"{y}-01-25", str(v), "t"] for y in range(2022, 2027)
                       for k, v in [(k, list(map(float, hist()[k]))[0]) for k in m.HIST_ITEMS]], columns=f5.MODEL_COLUMNS)
    at = pd.DataFrame([["NVDA", dr, s] + [str(v) for v in flat()[dr]] + ["r", "test"] for dr in m.DRIVERS for s in ("Bear", "Base", "Bull")],
                      columns=["ticker", "driver", "scenario", "y1", "y2", "y3", "y4", "y5", "reason", "source"])
    i = {c: "0" for c in d.INPUT_COLUMNS}
    i.update(ticker="NVDA", valuation_date="2026-11-02", bs_date="2026-07-26", stakes_source="test", shares_period_end="2026-07-26",
             latest_fy_end="2026-01-25", y1_end="2027-01-25", price="50", market_cap="5000", cash="300", st_investments="200",
             debt="100", stakes="0", diluted_shares="100", t_first="0.23", stub_fraction="0.5", beta_raw="1.5", blume_weight="0.67",
             blume_constant="0.33", risk_free="0.04", erp="0.05", cost_of_equity="0.11", cost_of_debt="0.05", tax_rate="0.2",
             debt_weight="0.0196", wacc="0.11", terminal_growth="0.03", exit_multiple="12", w_bear="0.25", w_base="0.5", w_bull="0.25")
    return md, at, pd.DataFrame([i], columns=d.INPUT_COLUMNS)


def test_reverse_dcf_returns_three_levers():
    md, at, ip = synthetic()
    r = d.reverse_dcf(md, at, ip)
    assert list(r["lever"]) == ["fy2_segment_a_growth", "wacc", "terminal_growth"]
    for x in r.itertuples():
        if x.status == "solved":
            lever = {"wacc": "wacc", "terminal_growth": "g"}.get(x.lever)
            if lever:
                _, h = m.history(md, "NVDA")
                v = d.dcf(m.forecast(h, m.scenario(at, "NVDA", "Base")), ip.iloc[0].to_dict(), **{lever: D(x.implied_value)})
                assert abs(v["per_share"] - D("50")) < D("0.01")


def test_workbook_dcf_tabs_are_formulas(tmp_path):
    md, at, ip = synthetic()
    values, detail = d.value_all(md, at, ip)
    cfg = d.load_dcf_cfg()
    payload = {"inputs": ip, "values": values, "detail": detail, "wacc_g": d.sensitivity_wacc_g(md, at, ip, cfg),
               "gm_sensitivity": d.sensitivity_growth_margin(md, at, ip, cfg), "reverse": d.reverse_dcf(md, at, ip),
               "wacc_grid": cfg["sensitivity"]["wacc"], "g_grid": cfg["sensitivity"]["growth"]}
    est = pd.DataFrame(columns=["ticker", "kind", "period", "avg"])
    wb = load_workbook(b.build(md, at, est, tmp_path / "t.xlsx", {"built": "x", "cutoff": "x", "snapshot": "x"}, payload))
    assert {"WACC", "DCF", "DcfData"} <= set(wb.sheetnames)
    ws = wb["DCF"]
    codes = {ws[f"A{r}"].value: r for r in range(1, ws.max_row + 1) if ws[f"A{r}"].value}
    for code in ("ufcf", "pv"):
        assert all(str(ws[f"{c}{codes[code]}"].value).startswith("=") for c in b.FC)
    for code in ("ev", "equity", "per_share", "x1", "g_ok", "per_share_exit"):
        assert str(ws[f"C{codes[code]}"].value).startswith("=")
    assert str(wb["WACC"]["C17"].value).startswith("=") and wb["WACC"]["A17"].value == "wacc"
