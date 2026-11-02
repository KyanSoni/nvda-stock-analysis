"""Selected layer: concept priority, restatement rule, fiscal labels, reported vs derived values.

Expected values below are worked out by hand from tests/fixtures/companyfacts_synthetic.json.
"""
import pytest

from conftest import pick
from select_facts import classify_duration, fiscal_labels


@pytest.mark.parametrize("end, month, expected", [
    ("2026-01-25", 1, (2026, 4)),   # NVIDIA FY2026 year end
    ("2025-04-27", 1, (2026, 1)),
    ("2025-07-27", 1, (2026, 2)),
    ("2025-10-26", 1, (2026, 3)),
    ("2025-01-26", 1, (2025, 4)),
    ("2026-02-01", 1, (2026, 4)),   # 53-week year spilling into February
    ("2025-12-31", 12, (2025, 4)),  # December year-end company
    ("2025-03-31", 12, (2025, 1)),
])
def test_fiscal_labels(end, month, expected):
    assert fiscal_labels(end, month) == expected


def test_duration_classification(cfg):
    b = cfg["selection"]["duration_days"]
    assert classify_duration(90, b) == "quarter"
    assert classify_duration(181, b) == "ytd_6m"
    assert classify_duration(272, b) == "ytd_9m"
    assert classify_duration(363, b) == "annual"
    assert classify_duration(29, b) == "other"
    assert classify_duration(None, b) == "instant"


def test_restatement_latest_filed_wins_and_original_is_kept(pipeline_output):
    row = pick(pipeline_output["selected"], line_item="revenue", fiscal_year=2025, value_basis="reported_annual")
    assert len(row) == 1
    r = row.iloc[0]
    assert r["value"] == "1010000000" and r["accn"] == "0000000000-26-000004"
    assert r["restated"] == "True" and r["n_observations"] == "2" and r["n_distinct_values"] == "2"
    assert r["original_value"] == "1000000000" and r["original_accn"] == "0000000000-25-000001"
    # label from dates (FY2025) even though SEC tagged this comparative fy=2026
    assert r["sec_fy"] == "2026" and r["fiscal_period"] == "FY"


def test_unchanged_value_repeated_in_later_filing_is_not_a_restatement(pipeline_output):
    r = pick(pipeline_output["selected"], line_item="total_assets", period_end="2025-01-26").iloc[0]
    assert r["n_observations"] == "2" and r["n_distinct_values"] == "1" and r["restated"] == "False"
    assert r["accn"] == "0000000000-25-000002"  # latest filing that reported it
    assert r["fiscal_year"] == "2025" and r["fiscal_period"] == "Q4" and r["value_basis"] == "reported_instant"


def test_concept_priority_and_fallback(pipeline_output):
    sel = pipeline_output["selected"]
    fy26 = pick(sel, line_item="revenue", fiscal_year=2026, value_basis="reported_annual").iloc[0]
    assert fy26["concept"] == "Revenues" and fy26["value"] == "2000000000"
    assert fy26["other_candidate_concepts"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    fy24 = pick(sel, line_item="revenue", fiscal_year=2024, value_basis="reported_annual").iloc[0]
    assert fy24["concept"] == "RevenueFromContractWithCustomerExcludingAssessedTax" and fy24["value"] == "800000000"


def test_excluded_forms_and_odd_durations_are_not_selected(pipeline_output):
    sel = pipeline_output["selected"]
    fy26 = pick(sel, line_item="revenue", fiscal_year=2026, value_basis="reported_annual").iloc[0]
    assert fy26["form"] == "10-K" and fy26["n_observations"] == "1"   # the 8-K copy is not counted
    assert pick(sel, line_item="revenue", period_start="2025-12-27").empty  # 30-day period ignored


def test_reported_quarters_and_ytd_are_labelled(pipeline_output):
    sel = pipeline_output["selected"]
    assert pick(sel, line_item="revenue", fiscal_year=2026, fiscal_period="Q2").iloc[0]["value_basis"] == "reported_quarter"
    assert pick(sel, line_item="revenue", fiscal_year=2026, fiscal_period="6M").iloc[0]["value_basis"] == "reported_ytd"
    assert pick(sel, line_item="operating_cash_flow", fiscal_year=2026, fiscal_period="9M").iloc[0]["value"] == "650000000"


def test_derived_q4_is_labelled_and_traceable(pipeline_output):
    sel = pipeline_output["selected"]
    q4 = pick(sel, line_item="revenue", fiscal_year=2026, fiscal_period="Q4")
    assert len(q4) == 1
    r = q4.iloc[0]
    assert r["value_basis"] == "derived_q4" and r["value"] == "650000000" and r["display_value"] == "650"
    assert r["accn"] == "" and r["form"] == "" and r["restated"] == ""
    assert r["derived_from_accns"] == "annual:0000000000-26-000004|9M:0000000000-25-000005"
    assert r["period_start"] == "2025-10-27" and r["period_end"] == "2026-01-25"
    assert r["transformation"].startswith("derived:")
    assert pick(sel, line_item="operating_cash_flow", fiscal_year=2026, fiscal_period="Q4").iloc[0]["value"] == "250000000"


def test_per_share_values_are_never_derived(pipeline_output):
    sel = pipeline_output["selected"]
    assert pick(sel, line_item="eps_diluted", value_basis="derived_q4").empty
    fy = pick(sel, line_item="eps_diluted", fiscal_year=2026, fiscal_period="FY").iloc[0]
    assert fy["value"] == "4.90" and fy["display_value"] == "4.90" and fy["display_unit"] == "USD/shares"


def test_display_values_are_exact_millions(pipeline_output):
    r = pick(pipeline_output["selected"], line_item="revenue", fiscal_year=2026, value_basis="reported_annual").iloc[0]
    assert r["display_value"] == "2000" and r["display_unit"] == "USD millions"
    assert r["transformation"] == "scaled to millions (value / 1,000,000)"
