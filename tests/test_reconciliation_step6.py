"""Step 6 reconciliation: NVIDIA's valuation-bridge inputs against the Q2 FY2027 10-Q; the WACC inputs against the
Step 4 beta export; the workbook's DCF against Python (needs LibreOffice; otherwise skipped with a reason).
Runs only with:  pytest -m reconciliation"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

import step6_check
import step6_dcf as d
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
OUT = PROJECT_ROOT / "data" / "clean" / "step6"
S5 = PROJECT_ROOT / "data" / "clean" / "step5"
REQUIRED = ["ticker", "item", "period_end", "reference_value", "tolerance", "source_form", "accession", "source_url",
            "location_in_filing", "entered_by", "entered_on"]
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


@pytest.fixture(scope="module")
def inp():
    if not (OUT / "dcf_inputs.csv").exists():
        pytest.fail("No Step 6 output yet: run  python python/run_step6.py  first.")
    return rd(OUT / "dcf_inputs.csv")


def test_step6_reference_values_tie(inp):
    r = rd(FIX / "reference_values_step6.csv")
    assert not [(i + 2, c) for i, x in r.iterrows() for c in REQUIRED if not x[c].strip()]
    row = inp[inp["ticker"] == "NVDA"].iloc[0]
    assert row["bs_date"] == "2026-07-26" and row["shares_period_end"] == "2026-07-26"
    fails = [f"{x.item}: model {row[x.item]} vs 10-Q {x.reference_value}" for x in r.itertuples()
             if abs(Decimal(row[x.item]) - Decimal(x.reference_value)) > Decimal(x.tolerance)]
    assert not fails, "\n".join(fails)


def test_wacc_inputs_follow_config_and_step4_beta(inp):
    beta = rd(PROJECT_ROOT / "data" / "clean" / "step4" / "exports" / "v_beta.csv")
    cfg = d.load_dcf_cfg()
    for x in inp.itertuples():
        raw = Decimal(beta[(beta["ticker"] == x.ticker) & (beta["benchmark"] == "SPY")].iloc[0]["beta"])
        assert Decimal(x.beta_raw) == raw
        assert Decimal(x.beta_adjusted) == Decimal(str(cfg["beta"]["blume_weight"])) * raw + Decimal(str(cfg["beta"]["blume_constant"]))
        assert Decimal(x.cost_of_equity) == Decimal(x.risk_free) + Decimal(x.beta_adjusted) * Decimal(str(cfg["equity_risk_premium"]))
        assert Decimal(x.terminal_growth) < Decimal(x.wacc)


def test_excel_dcf_matches_python(inp):
    md, at = rd(S5 / "model_data.csv"), rd(S5 / "assumptions.csv")
    if not step6_check.find_soffice():
        pytest.skip("LibreOffice not installed: open excel\\NVDA_Forecast.xlsx in Excel; DCF tab must show OK (MANUAL in m6_acceptance)")
    res = step6_check.compare(PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx", md, at, inp, rd(OUT / "sensitivity_wacc_g.csv"))
    assert all(ok for _, ok, _ in res), "\n".join(dd for _, ok, dd in res if not ok)
