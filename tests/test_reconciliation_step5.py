"""Step 5 reconciliation: model history against values read from the 10-Ks; NVIDIA base case against consensus;
the Excel workbook against the Python model (needs LibreOffice; otherwise skipped with a reason).
Runs only with:  pytest -m reconciliation"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

import step5_check
import step5_model as m
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
OUT = PROJECT_ROOT / "data" / "clean" / "step5"
REQUIRED = ["ticker", "line_item", "fiscal_year", "reference_value", "reference_unit", "source_form", "accession", "source_url",
            "location_in_filing", "entered_by", "entered_on"]


@pytest.fixture(scope="module")
def md():
    if not (OUT / "model_data.csv").exists():
        pytest.fail("No Step 5 output yet: run  python python/run_step5.py all  first.")
    return pd.read_csv(OUT / "model_data.csv", dtype=str, keep_default_na=False)


def test_step5_reference_values_tie(md):
    r = pd.read_csv(FIX / "reference_values_step5.csv", dtype=str, keep_default_na=False)
    assert not [(i + 2, c) for i, x in r.iterrows() for c in REQUIRED if not x[c].strip()]
    assert set(r["ticker"]) == {"NVDA", "AMD", "AVGO", "MRVL", "QCOM", "INTC"}
    fails = []
    for x in r.itertuples():
        h = md[(md["ticker"] == x.ticker) & (md["line_item"] == x.line_item) & (md["fiscal_year"] == x.fiscal_year)]
        if len(h) != 1 or Decimal(h.iloc[0]["value_m"]) != Decimal(x.reference_value):
            fails.append(f"{x.ticker} {x.line_item} FY{x.fiscal_year}: model {h['value_m'].tolist()} vs filing {x.reference_value}")
    assert not fails, "\n".join(fails)


def test_nvidia_base_case_matches_consensus_where_anchored(md):
    at = pd.read_csv(OUT / "assumptions.csv", dtype=str, keep_default_na=False)
    est = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "step4" / "estimates.csv", dtype=str, keep_default_na=False)
    e = est[(est["ticker"] == "NVDA") & (est["kind"] == "revenue")].set_index("period")["avg"]
    _, h = m.history(md, "NVDA")
    f = m.forecast(h, m.scenario(at, "NVDA", "Base"))
    for i, p in enumerate(("0y", "+1y")):
        cons = Decimal(e[p]) / 1_000_000
        assert abs(f["revenue"][i] / cons - 1) < Decimal("0.005"), f"Base revenue year {i + 1} {f['revenue'][i]} vs consensus {cons}"


def test_excel_matches_python_model(md):
    wb = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"
    at = pd.read_csv(OUT / "assumptions.csv", dtype=str, keep_default_na=False)
    if not step5_check.find_soffice():
        pytest.skip("LibreOffice not installed: open excel\\NVDA_Forecast.xlsx in Excel and check Cover shows OK (MANUAL in m5_acceptance)")
    res = step5_check.compare(wb, md, at)
    assert all(ok for _, ok, _ in res), "\n".join(d for _, ok, d in res if not ok)
