"""Step 3 offline tests: small synthetic frames, expected values worked out by hand. No network, no database."""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

import step3_facts as s3f
import step3_reference as ref

T = "TST"
S3 = {
    "derivations": {"debt_sum": {"target": "total_debt", "terms": ["debt_current", "debt_noncurrent"]},
                    "da_sum": {"target": "depreciation_amortization", "terms": ["da_base", "amortization_intangibles"]}},
    "companies": {T: {"optional_zero_terms": {"da_sum": {"amortization_intangibles": {"through_fiscal_year": 2020}}},
                      "declared_zero": {"st_investments": {"from_fiscal_year": 2021, "evidence": "no such line on the balance sheet"}}}},
}
CFG = {"line_items": {
    "total_debt": {"statement": "BS", "period_type": "instant", "unit": "USD"},
    "depreciation_amortization": {"statement": "CF", "period_type": "duration", "unit": "USD"},
    "st_investments": {"statement": "BS", "period_type": "instant", "unit": "USD"},
    "inventory": {"statement": "BS", "period_type": "instant", "unit": "USD"},
    "revenue": {"statement": "IS", "period_type": "duration", "unit": "USD"},
}}


def row(item, value, fy, fp, start, end, basis="reported_instant", accn="0000000000-00-000001", filed="2021-03-01", unit="USD"):
    r = {c: "" for c in s3f.OUT_COLUMNS}
    r.update(ticker=T, line_item=item, value=str(value), fiscal_year=str(fy), fiscal_period=fp, period_start=start,
             period_end=end, value_basis=basis, accn=accn, filed=filed, unit=unit, support_item="False")
    return r


def frame(rows):
    return pd.DataFrame(rows, columns=s3f.OUT_COLUMNS, dtype=object)


# ---------------- derived sums

def test_derived_sum_adds_terms_and_skips_periods_with_a_missing_term():
    sel = frame([row("debt_current", 100, 2021, "Q4", "", "2021-12-31"),
                 row("debt_noncurrent", 900, 2021, "Q4", "", "2021-12-31"),
                 row("debt_noncurrent", 800, 2020, "Q4", "", "2020-12-31")])        # no current debt in 2020
    out = s3f.derive_sums(sel, CFG, S3, T, ["debt_sum"])
    assert len(out) == 1
    r = out.iloc[0]
    assert (r["period_end"], Decimal(str(r["value"])), r["value_basis"]) == ("2021-12-31", Decimal(1000), "derived_sum")
    assert "debt_current:0000000000-00-000001" in r["derived_from_accns"] and r["accn"] == ""


def test_derived_sum_never_overwrites_a_reported_value():
    sel = frame([row("debt_current", 100, 2021, "Q4", "", "2021-12-31"),
                 row("debt_noncurrent", 900, 2021, "Q4", "", "2021-12-31"),
                 row("total_debt", 1001, 2021, "Q4", "", "2021-12-31")])
    assert s3f.derive_sums(sel, CFG, S3, T, ["debt_sum"]).empty


def test_optional_zero_term_applies_only_through_the_configured_year():
    sel = frame([row("da_base", 50, 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual"),
                 row("da_base", 60, 2021, "FY", "2021-01-01", "2021-12-31", "reported_annual")])
    out = s3f.derive_sums(sel, CFG, S3, T, ["da_sum"])
    assert list(out["fiscal_year"].astype(str)) == ["2020"]          # 2021 needs the amortisation term
    assert "taken as 0 by decision (through FY2020)" in out.iloc[0]["transformation"]


def test_derived_sums_recompute_check_catches_a_tampered_value():
    sel = frame([row("debt_current", 100, 2021, "Q4", "", "2021-12-31"),
                 row("debt_noncurrent", 900, 2021, "Q4", "", "2021-12-31")])
    out = s3f.derive_sums(sel, CFG, S3, T, ["debt_sum"])
    facts = pd.concat([sel, out], ignore_index=True)
    revenue = frame([row("revenue", 5, 2021, "FY", "2021-01-01", "2021-12-31", "reported_annual")])
    checks = {c[0]: c[1] for c in s3f.step3_checks(pd.concat([facts, revenue]), sel.iloc[0:0], CFG, S3, T, [])}
    assert checks["C21_derived_sums_recompute"]
    facts.loc[facts["value_basis"] == "derived_sum", "value"] = "999"
    checks = {c[0]: c[1] for c in s3f.step3_checks(pd.concat([facts, revenue]), sel.iloc[0:0], CFG, S3, T, [])}
    assert not checks["C21_derived_sums_recompute"]


# ---------------- declared zeros

def test_declared_zero_only_from_configured_year_and_only_where_missing():
    sel = frame([row("total_assets", 1, 2020, "Q4", "", "2020-12-31"),
                 row("total_assets", 1, 2021, "Q4", "", "2021-12-31"),
                 row("total_assets", 1, 2022, "Q4", "", "2022-12-31"),
                 row("st_investments", 7, 2022, "Q4", "", "2022-12-31")])
    out = s3f.declared_zeros(sel, CFG, S3, T)
    assert list(out["period_end"]) == ["2021-12-31"]
    assert out.iloc[0]["value_basis"] == "declared_zero" and str(out.iloc[0]["value"]) == "0"
    assert "no such line" in out.iloc[0]["transformation"]


# ---------------- manual facts

MANUAL_HEADER = ",".join(s3f.MANUAL_COLUMNS)


def _manual(tmp_path, line):
    p = tmp_path / "manual_facts.csv"
    p.write_text(MANUAL_HEADER + "\n" + line + "\n", encoding="utf-8")
    return p


def test_manual_fact_with_full_provenance_is_loaded(tmp_path):
    p = _manual(tmp_path, f"{T},inventory,2021,Q4,,2021-12-31,123,USD,10-K,0000000000-22-000001,2022-02-01,"
                          "https://www.sec.gov/x.htm,Balance sheet: Inventories,Kyan,2026-11-03,test")
    rows, problems = s3f.manual_facts(p, CFG, T, 12)
    assert not problems and len(rows) == 1
    assert rows.iloc[0]["value_basis"] == "manual_from_filing" and rows.iloc[0]["accn"] == "0000000000-22-000001"


def test_manual_fact_with_missing_provenance_or_wrong_label_is_rejected(tmp_path):
    p = _manual(tmp_path, f"{T},inventory,2021,Q4,,2021-12-31,123,USD,10-K,,2022-02-01,"
                          "https://www.sec.gov/x.htm,Balance sheet,Kyan,2026-11-03,")
    rows, problems = s3f.manual_facts(p, CFG, T, 12)
    assert rows.empty and "blank ['accession']" in problems[0]
    p = _manual(tmp_path, f"{T},inventory,2022,Q4,,2021-12-31,123,USD,10-K,0000000000-22-000001,2022-02-01,"
                          "https://www.sec.gov/x.htm,Balance sheet,Kyan,2026-11-03,")
    rows, problems = s3f.manual_facts(p, CFG, T, 12)
    assert rows.empty and "does not match period end" in problems[0]


def test_shipped_manual_facts_file_is_empty_header_only():
    from common import PROJECT_ROOT
    text = (PROJECT_ROOT / "config" / "manual_facts.csv").read_text(encoding="utf-8").strip().splitlines()
    assert text == [MANUAL_HEADER]


# ---------------- split adjustment

def test_split_adjustment_uses_splits_after_the_filing_date():
    splits = pd.DataFrame({"ticker": [T, T], "date": ["2021-07-20", "2024-06-10"], "ratio": ["4", "10"]})
    f = frame([row("eps_diluted", "4.00", 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual", filed="2021-02-20", unit="USD/shares"),
               row("shares_diluted", "250", 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual", filed="2021-02-20", unit="shares"),
               row("eps_diluted", "1.00", 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual", filed="2022-02-20", unit="USD/shares"),
               row("eps_diluted", "0.10", 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual", filed="2025-02-20", unit="USD/shares")])
    out = s3f.apply_split_adjustment(f, splits, ["eps_diluted", "shares_diluted"])
    assert [Decimal(str(x)) for x in out["split_factor"]] == [40, 40, 10, 1]
    assert Decimal(str(out.iloc[0]["value_split_adjusted"])) == Decimal("0.1")
    assert Decimal(str(out.iloc[1]["value_split_adjusted"])) == Decimal(10000)
    assert Decimal(str(out.iloc[2]["value_split_adjusted"])) == Decimal("0.1")
    assert Decimal(str(out.iloc[3]["value_split_adjusted"])) == Decimal("0.1")


def test_split_adjustment_leaves_other_items_and_unfiled_rows_alone():
    splits = pd.DataFrame({"ticker": [T], "date": ["2024-06-10"], "ratio": ["10"]})
    f = frame([row("revenue", 5, 2020, "FY", "2020-01-01", "2020-12-31", "reported_annual", filed="2021-02-20"),
               row("eps_diluted", "1", 2020, "FY", "2020-01-01", "2020-12-31", "derived_q4", accn="", filed="")])
    out = s3f.apply_split_adjustment(f, splits, ["eps_diluted", "shares_diluted"])
    assert (out["split_factor"] == "").all()


# ---------------- Python recomputation helpers (step3_reference)

def test_reference_helpers_handle_missing_and_zero():
    assert ref._div(Decimal(1), Decimal(0)) is None and ref._sub(Decimal(1), None) is None
    assert ref._close(Decimal("1.0000000000001"), Decimal(1)) and not ref._close(Decimal("1.001"), Decimal(1))
    assert ref._close(None, None) and not ref._close(None, Decimal(0))
