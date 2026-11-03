"""Step 3 reconciliation: real output in data/clean/step3 against values read from the filings, and the
PostgreSQL views against the independent Python recomputation. Runs only with:  pytest -m reconciliation
Reference values are never edited to make a test pass; a failure is investigated and logged."""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

import step3_reference as ref
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
OUT = PROJECT_ROOT / "data" / "clean" / "step3"
REQUIRED = ["ticker", "line_item", "fiscal_year", "fiscal_period", "value_basis", "reference_value", "reference_unit",
            "source_form", "accession", "source_url", "location_in_filing", "entered_by", "entered_on"]
NEW_ITEMS = {"current_assets", "current_liabilities", "inventory", "st_investments", "total_debt", "income_tax",
             "pretax_income", "interest_expense", "sbc", "depreciation_amortization"}


@pytest.fixture(scope="module")
def facts():
    if not (OUT / "facts_manifest.json").exists():
        pytest.fail("No Step 3 output yet: run  python python/run_step3.py all  first.")
    return pd.read_csv(OUT / "facts_extended.csv", dtype=str, keep_default_na=False)


def test_step3_reference_values_tie(facts):
    r = pd.read_csv(FIX / "reference_values_step3.csv", dtype=str, keep_default_na=False)
    assert not [c for c in REQUIRED if c not in r.columns]
    assert not [(i + 2, c) for i, x in r.iterrows() for c in REQUIRED if not x[c].strip()], "blank required fields"
    assert set(r["line_item"]) == NEW_ITEMS, "every new line item has a reference"
    assert set(r["ticker"]) == {"NVDA", "AMD", "AVGO", "MRVL", "QCOM", "INTC"}
    fails = []
    for x in r.itertuples():
        h = facts[(facts["ticker"] == x.ticker) & (facts["line_item"] == x.line_item) & (facts["fiscal_year"] == x.fiscal_year)
                  & (facts["fiscal_period"] == x.fiscal_period) & (facts["value_basis"] == x.value_basis)
                  & (facts["support_item"] == "False")]
        if len(h) != 1:
            fails.append(f"{x.ticker} {x.line_item} FY{x.fiscal_year} {x.fiscal_period} {x.value_basis}: {len(h)} rows")
        elif h.iloc[0]["display_unit"].lower() != x.reference_unit.lower():
            fails.append(f"{x.ticker} {x.line_item}: unit {h.iloc[0]['display_unit']} vs {x.reference_unit}")
        elif Decimal(h.iloc[0]["display_value"]) != Decimal(x.reference_value.replace(",", "")):
            fails.append(f"{x.ticker} {x.line_item}: pipeline {h.iloc[0]['display_value']} vs filing {x.reference_value}")
    assert not fails, "\n".join(fails)


def test_reported_ratios_tie():
    r = pd.read_csv(FIX / "ratio_reference_values.csv", dtype=str, keep_default_na=False)
    fails = []
    for x in r.itertuples():
        v = pd.read_csv(OUT / "exports" / f"{x.view}.csv", dtype=str, keep_default_na=False)
        h = v[(v["ticker"] == x.ticker) & (v["fiscal_year"] == x.fiscal_year)]
        got = round(Decimal(h.iloc[0][x.column]), int(x.decimals)) if len(h) == 1 and h.iloc[0][x.column] else None
        if got != Decimal(x.reference_value):
            fails.append(f"{x.ticker} FY{x.fiscal_year} {x.column}: {got} vs reported {x.reference_value}")
    assert not fails, "\n".join(fails)


def test_sql_views_match_python_recomputation():
    if not (OUT / "db_manifest.json").exists():
        pytest.fail("No database exports yet: run  python python/run_step3.py db  first.")
    results = ref.compare(OUT / "load", OUT / "exports")
    assert all(ok for _, ok, _ in results), "\n".join(f"{c}: {d}" for c, ok, d in results if not ok)
