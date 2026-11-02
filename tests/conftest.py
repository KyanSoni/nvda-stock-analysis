"""Shared test fixtures. Offline tests use only the synthetic snapshot in tests/fixtures."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from common import PROJECT_ROOT, load_config
from run_m1 import OUTPUT_FILES, process_snapshot

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_SNAPSHOT = FIXTURES / "companyfacts_synthetic.json"
SYNTHETIC_OBSERVATION_COUNT = 24  # counted by hand from the fixture file


@pytest.fixture(scope="session")
def cfg():
    return load_config(PROJECT_ROOT / "config" / "project.yaml")


@pytest.fixture(scope="session")
def pipeline_output(cfg, tmp_path_factory):
    """Run the whole M1 pipeline once on the synthetic snapshot and read every output back as text."""
    out = tmp_path_factory.mktemp("m1_out")
    checks, summary = process_snapshot(SYNTHETIC_SNAPSHOT, cfg, out)
    frames = {name: pd.read_csv(out / f, dtype=str, keep_default_na=False) for name, f in OUTPUT_FILES.items()}
    return {"dir": out, "checks": checks, "summary": summary, **frames}


def pick(df: pd.DataFrame, **conditions) -> pd.DataFrame:
    """Rows of df matching every column=value condition (values compared as text)."""
    mask = pd.Series(True, index=df.index)
    for col, val in conditions.items():
        mask &= df[col] == str(val)
    return df[mask]
