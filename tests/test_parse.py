"""Observations layer: every SEC observation is kept, exactly as published."""
from decimal import Decimal

from conftest import SYNTHETIC_OBSERVATION_COUNT, SYNTHETIC_SNAPSHOT, pick
from parse_companyfacts import load_snapshot, parse_observations


def _obs():
    data, sha = load_snapshot(SYNTHETIC_SNAPSHOT)
    return parse_observations(data, sha), sha


def test_every_observation_is_kept():
    obs, _ = _obs()
    assert len(obs) == SYNTHETIC_OBSERVATION_COUNT
    # kept even though later steps ignore them: other taxonomy, 8-K form, a 30-day period
    assert len(obs[obs["taxonomy"] == "dei"]) == 1
    assert len(obs[obs["form"] == "8-K"]) == 1
    assert len(obs[obs["duration_days"] == 29]) == 1


def test_values_are_exact_not_floats():
    obs, _ = _obs()
    eps = obs[(obs["concept"] == "EarningsPerShareDiluted") & (obs["period_end"] == "2026-01-25")]
    assert eps.iloc[0]["value"] == Decimal("4.90") and str(eps.iloc[0]["value"]) == "4.90"
    rev = obs[(obs["concept"] == "Revenues") & (obs["accn"] == "0000000000-26-000004")
              & (obs["period_end"] == "2026-01-25") & (obs["period_start"] == "2025-01-27")]
    assert rev.iloc[0]["value"] == 2000000000 and isinstance(rev.iloc[0]["value"], int)


def test_instants_and_durations_are_distinguished():
    obs, _ = _obs()
    assets = obs[obs["concept"] == "Assets"]
    assert set(assets["period_type"]) == {"instant"}
    assert set(assets["period_start"]) == {""}
    assert assets["duration_days"].isna().all()


def test_sec_fiscal_tags_are_preserved_as_provenance():
    obs, sha = _obs()
    # the FY2025 comparative inside the FY2026 10-K carries SEC's filing-level tag fy=2026
    row = obs[(obs["concept"] == "Revenues") & (obs["period_end"] == "2025-01-26") & (obs["accn"] == "0000000000-26-000004")]
    assert row.iloc[0]["sec_fy"] == 2026 and row.iloc[0]["sec_fp"] == "FY"
    assert set(obs["snapshot_sha256"]) == {sha}


def test_observations_csv_round_trip(pipeline_output):
    obs = pipeline_output["observations"]
    assert len(obs) == SYNTHETIC_OBSERVATION_COUNT
    assert pick(obs, concept="EarningsPerShareDiluted", period_end="2026-01-25").iloc[0]["value"] == "4.90"
