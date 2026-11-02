"""C11 / W1: scale anomalies are flagged and reported, never corrected."""
from decimal import Decimal

from conftest import SYNTHETIC_SNAPSHOT
from common import PROJECT_ROOT, load_config
from parse_companyfacts import load_snapshot, parse_observations
from select_facts import select_line_items
from validate_m1 import find_scale_anomalies, scale_checks


def _fresh():
    cfg = load_config(PROJECT_ROOT / "config" / "project.yaml")
    data, sha = load_snapshot(SYNTHETIC_SNAPSHOT)
    return cfg, select_line_items(parse_observations(data, sha), cfg)


def _row(sel, **cond):
    mask = True
    for k, v in cond.items():
        mask = mask & (sel[k] == v)
    return sel[mask].index[0]


def test_clean_fixture_has_no_anomalies(pipeline_output):
    assert pipeline_output["anomalies"].empty
    levels = {c: lvl for c, _, _, lvl in pipeline_output["checks"]}
    assert levels["C11_no_scale_anomalies_in_target_window"] == "error"
    assert levels["W1_scale_anomalies_outside_window"] == "warning"
    assert all(p for _, p, _, _ in pipeline_output["checks"])


def test_thousands_tagged_as_units_vs_first_filed_is_flagged():
    cfg, sel = _fresh()
    i = _row(sel, line_item="revenue", fiscal_year=2024, value_basis="reported_annual")
    sel.loc[i, "original_value"] = 800000  # first filing 1,000x too small
    a = find_scale_anomalies(sel, cfg, 2026)
    assert list(a["anomaly_type"]) == ["vs_first_filed"]
    assert a.iloc[0]["ratio"] == Decimal("1000.0000") and a.iloc[0]["in_target_window"] is True
    c11, _ = scale_checks(a)
    assert c11[1] is False


def test_jump_vs_previous_period_is_flagged():
    cfg, sel = _fresh()
    i = _row(sel, line_item="total_assets", period_end="2026-01-25")
    sel.loc[i, "value"] = 7000000  # 1,000x smaller than the previous instant
    a = find_scale_anomalies(sel, cfg, 2026)
    hit = a[a["anomaly_type"] == "vs_previous_period"]
    assert len(hit) == 1 and hit.iloc[0]["period_end"] == "2026-01-25"
    assert hit.iloc[0]["compared_with"].startswith("Q1 FY2026")


def test_anomaly_outside_window_is_a_warning_not_an_error():
    cfg, sel = _fresh()
    i = _row(sel, line_item="revenue", fiscal_year=2024, value_basis="reported_annual")
    sel.loc[i, "original_value"] = 800000
    a = find_scale_anomalies(sel, cfg, 2040)  # window FY2031-FY2040: everything is outside
    c11, w1 = scale_checks(a)
    assert c11[1] is True and w1[1] is False and "FY2024-FY2024" in w1[2]


def test_split_sized_changes_are_not_flagged():
    cfg, sel = _fresh()
    i = _row(sel, line_item="revenue", fiscal_year=2024, value_basis="reported_annual")
    sel.loc[i, "original_value"] = 20000000  # 40x, the size of NVIDIA's two splits combined
    assert find_scale_anomalies(sel, cfg, 2026).empty


def test_flagging_never_changes_selected_values():
    cfg, sel = _fresh()
    i = _row(sel, line_item="revenue", fiscal_year=2024, value_basis="reported_annual")
    sel.loc[i, "original_value"] = 800000
    before = sel.copy()
    find_scale_anomalies(sel, cfg, 2026)
    assert sel.equals(before)
