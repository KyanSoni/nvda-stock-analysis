"""Gap report and validation checks, including proof that the checks catch broken data."""
import pandas as pd

from conftest import SYNTHETIC_OBSERVATION_COUNT, SYNTHETIC_SNAPSHOT, pick
from parse_companyfacts import load_snapshot, parse_observations
from select_facts import select_line_items
from validate_m1 import run_checks


def test_window_is_ten_years_ending_at_latest_annual(pipeline_output):
    assert pipeline_output["summary"]["latest_fiscal_year"] == 2026
    assert pipeline_output["summary"]["target_window"] == "FY2017-FY2026"


def test_gap_reasons(pipeline_output):
    gaps = pipeline_output["gaps"]
    assert pick(gaps, line_item="operating_cash_flow", fiscal_year=2026, fiscal_period="Q2").iloc[0]["reason"] == "only_ytd_reported"
    assert pick(gaps, line_item="operating_cash_flow", fiscal_year=2026, fiscal_period="Q3").iloc[0]["reason"] == "only_ytd_reported"
    assert pick(gaps, line_item="eps_diluted", fiscal_year=2026, fiscal_period="Q4").iloc[0]["reason"] == "not_derivable_by_subtraction"
    assert pick(gaps, line_item="gross_profit", fiscal_year=2026, fiscal_period="FY").iloc[0]["reason"] == "no_observation"
    assert pick(gaps, line_item="revenue", fiscal_year=2025, fiscal_period="Q4").iloc[0]["reason"] == "derived_q4_inputs_missing: 9M YTD"
    # FY2017 is inside the window with no data at all: listed, not filled
    assert not pick(gaps, line_item="revenue", fiscal_year=2017, fiscal_period="FY").empty


def test_no_gap_is_also_a_selected_value(pipeline_output):
    sel, gaps = pipeline_output["selected"], pipeline_output["gaps"]
    for g in gaps.itertuples():
        hit = sel[(sel["line_item"] == g.line_item) & (sel["fiscal_year"] == g.fiscal_year)
                  & (sel["fiscal_period"] == g.fiscal_period)
                  & (sel["value_basis"].isin(["reported_annual", "reported_quarter", "reported_instant", "derived_q4"]))]
        assert hit.empty, f"gap listed but value present: {g}"


def test_revenue_fy2026_has_all_four_quarters(pipeline_output):
    gaps = pipeline_output["gaps"]
    assert pick(gaps, line_item="revenue", fiscal_year=2026).empty


def test_all_validation_checks_pass_on_fixture(pipeline_output):
    failed = [c for c in pipeline_output["checks"] if c[3] == "error" and not c[1]]
    assert not failed, failed
    assert pipeline_output["validation"]["passed"].eq("True").all()


# ---- the checks must fail when the data is wrong ----

def _fresh():
    from common import load_config, PROJECT_ROOT
    cfg = load_config(PROJECT_ROOT / "config" / "project.yaml")
    data, sha = load_snapshot(SYNTHETIC_SNAPSHOT)
    obs = parse_observations(data, sha)
    return cfg, obs, select_line_items(obs, cfg)


def _failed(cfg, obs, sel, count=SYNTHETIC_OBSERVATION_COUNT):
    return {c for c, ok, _ in run_checks(obs, sel, cfg, count) if not ok}


def test_check_catches_dropped_observation():
    cfg, obs, sel = _fresh()
    assert "C1_all_observations_kept" in _failed(cfg, obs.iloc[1:], sel)


def test_check_catches_duplicate_selected_row():
    cfg, obs, sel = _fresh()
    assert "C2_unique_selected_keys" in _failed(cfg, obs, pd.concat([sel, sel.iloc[[0]]], ignore_index=True))


def test_check_catches_original_value_used_instead_of_restated():
    cfg, obs, sel = _fresh()
    i = sel[(sel["line_item"] == "revenue") & (sel["period_end"] == "2025-01-26")].index[0]
    sel.loc[i, "value"] = 1000000000
    sel.loc[i, "accn"] = "0000000000-25-000001"
    assert "C7_latest_filed_rule" in _failed(cfg, obs, sel)


def test_check_catches_derived_row_posing_as_reported():
    cfg, obs, sel = _fresh()
    i = sel[sel["value_basis"] == "derived_q4"].index[0]
    sel.loc[i, "accn"] = "0000000000-26-000004"
    assert "C4_derived_rows_labelled" in _failed(cfg, obs, sel)


def test_check_catches_wrong_derived_arithmetic():
    cfg, obs, sel = _fresh()
    i = sel[sel["value_basis"] == "derived_q4"].index[0]
    sel.loc[i, "value"] = 1
    assert "C9_derived_q4_arithmetic" in _failed(cfg, obs, sel)
