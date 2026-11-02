"""Live SEC retrieval. Runs only with:  pytest -m live
Writes into a temporary folder, never into data/raw, so it cannot change the project's saved snapshots.
"""
import csv
import os

import pytest

from fetch_sec import fetch_companyfacts
from parse_companyfacts import load_snapshot, parse_observations

pytestmark = pytest.mark.live


def test_live_companyfacts_fetch(cfg, tmp_path):
    if not os.environ.get(cfg["sec"]["user_agent_env"]):
        pytest.fail(f"Set {cfg['sec']['user_agent_env']} before running live tests.")
    saved = fetch_companyfacts(cfg, root=tmp_path)
    assert saved.exists() and saved.stat().st_size > 1_000_000

    with open(tmp_path / cfg["paths"]["manifest"], encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["http_status"] == "200" and rows[0]["valid_json"] == "true"

    data, sha = load_snapshot(saved)
    assert int(data["cik"]) == int(cfg["company"]["cik"])
    assert "NVIDIA" in data["entityName"].upper()
    assert sha == rows[0]["sha256"]

    obs = parse_observations(data, sha)
    present = set(obs.loc[obs["taxonomy"] == "us-gaap", "concept"])
    missing = {item: spec["candidates"] for item, spec in cfg["line_items"].items()
               if not present.intersection(spec["candidates"])}
    assert not missing, f"no candidate concept found for: {missing}"
