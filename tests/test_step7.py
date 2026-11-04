"""Step 7 offline tests: NTM calendarisation, multiples, exclusion rules, peer statistics, implied values, the regression,
the blend and the workbook's Comps tab. Synthetic numbers; no network, no database, no LibreOffice."""
import pandas as pd
import pytest
from openpyxl import load_workbook

import build_comps
import step7_comps as c
from openpyxl import Workbook

TICKERS = ["NVDA", "P1", "P2", "P3", "P4", "P5"]


def synthetic(**over):
    """Target NVDA + five peers. Peer k: price 10k, 100 shares, no debt or cash, LTM revenue 100, NTM revenue 100 + 10k."""
    val, rat, est, din, px = [], [], [], [], []
    for k, t in enumerate(TICKERS):
        price = 100.0 if t == "NVDA" else 10.0 * k
        ni = 50.0 if t != "P5" else -5.0                     # P5 has an LTM loss: LTM P/E is not meaningful
        val.append({"ticker": t, "role": "target" if t == "NVDA" else "peer", "cutoff_date": "2026-11-02", "price": str(price),
                    "market_cap": str(price * 100), "total_debt": "20" if t == "NVDA" else "0", "cash_and_equivalents": "30" if t == "NVDA" else "0",
                    "st_investments": "", "ltm_revenue": "100", "ebitda_used": "40", "ltm_net_income": str(ni), "ltm_period_end": "2026-07-26",
                    "ebitda_basis": "LTM"})
        rat.append({"ticker": t, "period_end": "2026-07-26", "ltm_revenue_growth": "0.5", "ltm_gross_margin": "0.6"})
        for kind, p0, p1 in (("revenue", 100e6 + 1e7 * k, 120e6 + 1e7 * k), ("eps", 1.0, 2.0)):
            est += [{"ticker": t, "kind": kind, "period": "0y", "avg": str(p0)}, {"ticker": t, "kind": kind, "period": "+1y", "avg": str(p1)}]
        y1 = "2027-01-25" if t == "NVDA" else "2026-11-02"
        din.append({"ticker": t, "y1_end": y1, "stakes": "10" if t == "NVDA" else "0", "diluted_shares": "100"})
        px += [{"ticker": t, "date": d, "close": str(v)} for d, v in (("2025-11-01", 1.0), ("2026-01-05", price * 0.8), ("2026-11-02", price),
                                                                     ("2026-11-03", 999.0))]
    dval = pd.DataFrame([{"ticker": "NVDA", "bear_per_share": "50", "base_per_share": "80", "bull_per_share": "120", "weighted_per_share": "82.5"}])
    wg = pd.DataFrame([{"wacc": str(w), "g_0.025": str(90 - 100 * w), "g_0.03": str(95 - 100 * w), "g_0.035": str(100 - 100 * w)}
                       for w in (0.11, 0.12, 0.13, 0.14, 0.15, 0.16)])
    inp = {"val": pd.DataFrame(val), "rat": pd.DataFrame(rat), "est": pd.DataFrame(est), "dcf_in": pd.DataFrame(din),
           "dcf_val": dval, "wacc_g": wg, "prices": pd.DataFrame(px)}
    for k, v in over.items():
        inp[k] = v
    return inp


@pytest.fixture
def res():
    return c.run(inp=synthetic())


def test_ntm_weights_calendarise_to_the_valuation_date(res):
    tb = res["table"].set_index("ticker")
    assert tb.loc["NVDA", "w_fy0"] == pytest.approx(84 / 365.25)        # 2026-11-02 to 2027-01-25
    assert tb.loc["P1", "w_fy0"] == 0                                    # fiscal year ends on the valuation date
    assert tb.loc["NVDA", "revenue_ntm"] == pytest.approx(84 / 365.25 * 100 + (1 - 84 / 365.25) * 120)
    assert tb.loc["P2", "eps_ntm"] == 2.0


def test_ev_and_multiples_by_hand(res):
    tb = res["table"].set_index("ticker")
    assert tb.loc["NVDA", "ev"] == 10000 + 20 - 30 - 10                  # stakes leave EV, as in the DCF bridge
    assert tb.loc["P3", "pe_ntm"] == pytest.approx(30 / 2.0) and tb.loc["P3", "ev_revenue_ltm"] == pytest.approx(3000 / 100)
    assert tb.loc["P3", "ev_ebitda_ntm"] == pytest.approx(3000 / (150 * 0.4))


def test_exclusions_target_negative_and_above_100x(res):
    tb = res["table"].set_index("ticker")
    assert tb.loc["NVDA"][[f"use_{k}" for k in c.MULTIPLES]].sum() == 0
    assert pd.isna(tb.loc["P5", "pe_ltm"]) and tb.loc["P5", "use_pe_ltm"] == 0       # LTM loss
    assert tb.loc["P5", "ev_revenue_ltm"] == pytest.approx(50.0) and tb.loc["P5", "use_ev_revenue_ltm"] == 1
    assert tb.loc["P4", "ev_ebitda_ltm"] == pytest.approx(4000 / 40) and tb.loc["P4", "use_ev_ebitda_ltm"] == 1   # exactly 100x stays
    assert tb.loc["P5", "ev_ebitda_ltm"] == pytest.approx(125.0) and tb.loc["P5", "use_ev_ebitda_ltm"] == 0       # above 100x leaves


def test_fiscal_year_ebitda_peer_has_no_ebitda_multiples():
    cfg = c.load_cfg()
    cfg["exclusions"]["ebitda_fy_basis"] = ["P2"]
    tb = c.run(cfg=cfg, inp=synthetic())["table"].set_index("ticker")
    assert pd.isna(tb.loc["P2", "ev_ebitda_ntm"]) and tb.loc["P2", "use_ev_ebitda_ntm"] == 0


def test_statistics_and_implied_values(res):
    st, im = res["stats"].set_index("multiple"), res["implied"].set_index("multiple")
    pe = [10 * k / 2.0 for k in range(1, 6)]                             # 5, 10, 15, 20, 25
    assert st.loc["pe_ntm", "p50"] == 15 and st.loc["pe_ntm", "p25"] == 10 and st.loc["pe_ntm", "n"] == 5
    assert im.loc["pe_ntm", "p50"] == pytest.approx(15 * res["table"].set_index("ticker").loc["NVDA", "eps_ntm"])
    n = res["table"].set_index("ticker").loc["NVDA"]
    m = st.loc["ev_revenue_ntm", "p50"]
    assert im.loc["ev_revenue_ntm", "p50"] == pytest.approx((m * n["revenue_ntm"] + 30 + 10 - 20) / 100)
    assert pe == sorted(pe)


def test_regression_and_blend(res):
    r = res["regression"]
    assert r["n"] == 5 and 0 <= r["r2"] <= 1
    b = res["blend"]
    assert b["dcf_weighted"] == 82.5 and b["blended_value"] == pytest.approx(0.5 * 82.5 + 0.5 * b["comps_value"])
    i = res["implied"].set_index("multiple")
    assert b["comps_value"] == pytest.approx((i.loc["pe_ntm", "p50"] + i.loc["ev_ebitda_ntm", "p50"]) / 2)


def test_52_week_range_stops_at_the_cutoff(res):
    n = res["table"].set_index("ticker").loc["NVDA"]
    assert n["low_52w"] == 80.0 and n["high_52w"] == 100.0               # 2025-11-01 is too old, 2026-11-03 after the cutoff


def test_checks_pass_on_synthetic(res):
    assert all(ok for _, ok, _ in c.checks(res))


def test_comps_tab_is_formulas(res):
    wb = Workbook()
    wb.create_sheet("Data")
    build_comps.add(wb, res)
    ws = wb["Comps"]
    assert {"Comps", "CompsData"} <= set(wb.sheetnames) and len(ws._charts) == 2
    head = {ws.cell(3, j).value: ws.cell(3, j).column_letter for j in range(1, ws.max_column + 1) if ws.cell(3, j).value}
    for k in list(c.MULTIPLES) + ["ev", "revenue_ntm", "eps_ntm", "w_fy0"]:
        for r in range(5, 11):
            assert str(ws[f"{head[k]}{r}"].value).startswith("="), (k, r)
    codes = {ws[f"A{r}"].value: r for r in range(1, ws.max_row + 1) if ws[f"A{r}"].value}
    for k in ("blended", "comps_value", "reg_slope", "stat_p50", "imp_p50"):
        assert k in codes
    assert str(ws[f"C{codes['blended']}"].value).startswith("=")
