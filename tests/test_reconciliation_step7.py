"""Step 7 reconciliation: the comps inputs tie to the verified upstream outputs (Step 3 valuation view, Step 4 consensus,
Step 6 DCF), NVIDIA's NTM EPS agrees with the second consensus source (Nasdaq, Step 4 fixture), and the workbook's Comps
tab equals Python (needs LibreOffice; otherwise skipped with a reason).
Runs only with:  pytest -m reconciliation"""
from pathlib import Path

import pandas as pd
import pytest

import step7_check
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
CLEAN = PROJECT_ROOT / "data" / "clean"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


@pytest.fixture(scope="module")
def tb():
    if not (CLEAN / "step7" / "comps_table.csv").exists():
        pytest.fail("No Step 7 output yet: run  python python/run_step7.py  first.")
    return rd(CLEAN / "step7" / "comps_table.csv").set_index("ticker")


def test_inputs_tie_to_step3_and_step4(tb):
    val = rd(CLEAN / "step3" / "exports" / "v_valuation_cutoff.csv").set_index("ticker")
    est = rd(CLEAN / "step4" / "estimates.csv").set_index(["ticker", "kind", "period"])["avg"]
    fails = []
    for t, r in tb.iterrows():
        for a, b in (("price", "price"), ("market_cap", "market_cap"), ("debt", "total_debt"), ("cash", "cash_and_equivalents"),
                     ("revenue_ltm", "ltm_revenue"), ("net_income_ltm", "ltm_net_income")):
            if abs(float(r[a]) - float(val.loc[t, b])) > 1e-6 * max(1, abs(float(val.loc[t, b]))):
                fails.append(f"{t} {a}")
        for a, kind, p, scale in (("revenue_fy0", "revenue", "0y", 1e6), ("revenue_fy1", "revenue", "+1y", 1e6),
                                  ("eps_fy0", "eps", "0y", 1), ("eps_fy1", "eps", "+1y", 1)):
            if abs(float(r[a]) - float(est[(t, kind, p)]) / scale) > 1e-5:
                fails.append(f"{t} {a}")
    assert not fails, fails


def test_blend_uses_the_step6_dcf_value():
    b = rd(CLEAN / "step7" / "comps_blend.csv").iloc[0]
    v = rd(CLEAN / "step6" / "dcf_values.csv").set_index("ticker").loc["NVDA"]
    assert abs(float(b["dcf_weighted"]) - float(v["weighted_per_share"])) < 1e-6


def test_nvidia_ntm_eps_agrees_with_second_source(tb):
    x = rd(FIX / "estimates_crosscheck.csv")
    x = x[(x["ticker"] == "NVDA") & (x["kind"] == "eps")].set_index("period")["reference_avg"].astype(float)
    w = float(tb.loc["NVDA", "w_fy0"])
    alt = w * x["0y"] + (1 - w) * x["+1y"]
    assert abs(float(tb.loc["NVDA", "eps_ntm"]) / alt - 1) < 0.05, f"Yahoo NTM {tb.loc['NVDA', 'eps_ntm']} vs Nasdaq {alt:.3f}"


def test_excel_comps_matches_python():
    import step7_comps as c
    if not step7_check.find_soffice():
        pytest.skip("LibreOffice not installed: open excel\\NVDA_Forecast.xlsx in Excel; Comps blended value must equal comps_blend.csv (MANUAL in m7_acceptance)")
    import step6_dcf as d
    s5 = CLEAN / "step5"
    res = c.run(inp=c.read_inputs(d.payload(rd(s5 / "model_data.csv"), rd(s5 / "assumptions.csv"))))
    out = step7_check.compare(PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx", res)
    assert all(ok for _, ok, _ in out), "\n".join(dd for _, ok, dd in out if not ok)
