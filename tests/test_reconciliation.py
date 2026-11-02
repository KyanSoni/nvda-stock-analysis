"""Reconciliation of real pipeline output against values YOU typed from NVIDIA's filings.
Runs only with:  pytest -m reconciliation   (after a live run has produced data/clean outputs)

Rules: reference values are never edited to make a test pass. If a value does not tie, log an issue
and investigate (wrong period, wrong concept, restatement, units) before changing anything.
"""
import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation

REFERENCE = Path(__file__).resolve().parent / "fixtures" / "reference_values.csv"
REQUIRED = ["line_item", "fiscal_year", "fiscal_period", "value_basis", "reference_value", "reference_unit",
            "source_form", "accession", "source_url", "location_in_filing", "entered_by", "entered_on"]
MIN_REFERENCES = 3


@pytest.fixture(scope="module")
def real_output(cfg):
    clean = PROJECT_ROOT / cfg["paths"]["clean_dir"]
    manifest_path = clean / "run_manifest.json"
    if not manifest_path.exists():
        pytest.fail("No pipeline output yet: run  python python/run_m1.py --source live  first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "NVIDIA" not in str(manifest.get("entity_name", "")).upper():
        pytest.fail(f"data/clean was not produced from an NVIDIA snapshot (entity: {manifest.get('entity_name')}).")
    selected = pd.read_csv(clean / "nvda_facts_selected.csv", dtype=str, keep_default_na=False)
    return manifest, selected


@pytest.fixture(scope="module")
def references():
    ref = pd.read_csv(REFERENCE, dtype=str, keep_default_na=False)
    missing_cols = [c for c in REQUIRED if c not in ref.columns]
    assert not missing_cols, f"reference_values.csv is missing columns: {missing_cols}"
    return ref


def test_enough_reference_values(references):
    assert len(references) >= MIN_REFERENCES, (
        f"{len(references)} reference rows; M1 acceptance needs at least {MIN_REFERENCES} typed from the FY26 10-K.")


def test_reference_rows_have_full_provenance(references):
    for r in references.itertuples():
        blanks = [c for c in REQUIRED if getattr(r, c).strip() == ""]
        assert not blanks, f"row {r.Index + 2}: blank {blanks}"


def test_reference_values_tie_exactly(real_output, references):
    _, selected = real_output
    failures = []
    for r in references.itertuples():
        hit = selected[(selected["line_item"] == r.line_item) & (selected["fiscal_year"] == r.fiscal_year)
                       & (selected["fiscal_period"] == r.fiscal_period) & (selected["value_basis"] == r.value_basis)]
        if len(hit) != 1:
            failures.append(f"{r.line_item} FY{r.fiscal_year} {r.fiscal_period}: {len(hit)} matching rows")
            continue
        h = hit.iloc[0]
        ref_unit = r.reference_unit.strip()
        ref_value = r.reference_value.replace(",", "").replace(" ", "").strip()  # "215,938" is accepted
        if h["display_unit"].lower() != ref_unit.lower():
            failures.append(f"{r.line_item} FY{r.fiscal_year} {r.fiscal_period}: unit {h['display_unit']} vs {ref_unit}")
        elif Decimal(h["display_value"]) != Decimal(ref_value):
            failures.append(f"{r.line_item} FY{r.fiscal_year} {r.fiscal_period}: pipeline {h['display_value']} "
                            f"vs filing {ref_value} (pipeline accn {h['accn']}, reference accn {r.accession})")
    assert not failures, "\n".join(failures)
