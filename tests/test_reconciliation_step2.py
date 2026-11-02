"""Step 2 reconciliation: real output in data/clean/step2 against values read from the filings and an
independent price source. Runs only with:  pytest -m reconciliation
Reference values are never edited to make a test pass; a failure is investigated and logged."""
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
OUT = PROJECT_ROOT / "data" / "clean" / "step2"
REQUIRED = ["ticker", "line_item", "fiscal_year", "fiscal_period", "value_basis", "reference_value", "reference_unit",
            "source_form", "accession", "source_url", "location_in_filing", "entered_by", "entered_on"]


@pytest.fixture(scope="module")
def facts():
    if not (OUT / "run_manifest.json").exists():
        pytest.fail("No Step 2 output yet: run  python python/run_step2.py  first.")
    return pd.read_csv(OUT / "facts_selected.csv", dtype=str, keep_default_na=False)


def _clean(v: str) -> Decimal:
    return Decimal(v.replace(",", "").replace(" ", "").strip())


def test_step2_sec_reference_values_tie(facts):
    ref = pd.read_csv(FIX / "reference_values_step2.csv", dtype=str, keep_default_na=False)
    assert len(ref) >= 15 and not [c for c in REQUIRED if c not in ref.columns]
    blanks = [(i + 2, c) for i, r in ref.iterrows() for c in REQUIRED if not r[c].strip()]
    assert not blanks, f"blank required fields: {blanks}"
    assert ref.groupby("ticker").size().min() >= 3, "M2-D9 needs at least 3 values per peer"
    fails = []
    for r in ref.itertuples():
        h = facts[(facts["ticker"] == r.ticker) & (facts["line_item"] == r.line_item) & (facts["fiscal_year"] == r.fiscal_year)
                  & (facts["fiscal_period"] == r.fiscal_period) & (facts["value_basis"] == r.value_basis)
                  & (facts["support_item"] == "False")]
        if len(h) != 1:
            fails.append(f"{r.ticker} {r.line_item} FY{r.fiscal_year} {r.fiscal_period} {r.value_basis}: {len(h)} rows")
        elif h.iloc[0]["display_unit"].lower() != r.reference_unit.strip().lower():
            fails.append(f"{r.ticker} {r.line_item}: unit {h.iloc[0]['display_unit']} vs {r.reference_unit}")
        elif Decimal(h.iloc[0]["display_value"]) != _clean(r.reference_value):
            fails.append(f"{r.ticker} {r.line_item} FY{r.fiscal_year} {r.fiscal_period}: pipeline {h.iloc[0]['display_value']} "
                         f"vs filing {r.reference_value}")
    assert not fails, "\n".join(fails)


def test_step2_price_reference_values_tie():
    prices = pd.read_csv(OUT / "market" / "prices.csv", dtype=str, keep_default_na=False)
    ref = pd.read_csv(FIX / "price_reference_values.csv", dtype=str, keep_default_na=False)
    assert len(ref) >= 6
    fails = []
    for r in ref.itertuples():
        h = prices[(prices["ticker"] == r.ticker) & (prices["date"] == r.date)]
        if len(h) != 1:
            fails.append(f"{r.ticker} {r.date}: {len(h)} price rows")
        elif Decimal(h.iloc[0]["close_as_traded"]).quantize(Decimal("0.01")) != _clean(r.reference_close):
            fails.append(f"{r.ticker} {r.date}: yfinance {h.iloc[0]['close_as_traded']} vs {r.source} {r.reference_close}")
    assert not fails, "\n".join(fails)


def test_step2_nvda_matches_m1_output(facts):
    """NVIDIA's reported values must be unchanged from M1 when built from the same SEC snapshot."""
    m1_path = PROJECT_ROOT / "data" / "clean" / "nvda_facts_selected.csv"
    m1_manifest = PROJECT_ROOT / "data" / "clean" / "run_manifest.json"
    s2_manifest = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    if not m1_path.exists():
        pytest.fail("M1 output data/clean/nvda_facts_selected.csv is missing: run python python/run_m1.py --source snapshot")
    m1 = pd.read_csv(m1_path, dtype=str, keep_default_na=False)
    snap = json.loads(m1_manifest.read_text(encoding="utf-8"))["snapshot_sha256"]
    nv = facts[(facts["ticker"] == "NVDA") & (facts["support_item"] == "False") & (facts["value_basis"] != "derived_quarter")]
    if set(nv["snapshot_sha256"]) != {snap}:
        pytest.fail(f"NVIDIA snapshot changed since M1 ({snap[:12]}...); compare manually before accepting "
                    f"(collection {s2_manifest['collection_id']})")
    cols = list(m1.columns)
    a = m1[cols].sort_values(cols).reset_index(drop=True)
    b = nv[cols].sort_values(cols).reset_index(drop=True)
    assert len(a) == len(b) and a.equals(b)
