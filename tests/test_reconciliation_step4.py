"""Step 4 reconciliation: SQL scorecard views against the independent Python recomputation, and the yfinance
consensus against a second public source. Runs only with:  pytest -m reconciliation"""
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

import step4_estimates as est
import step4_reference as ref
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
FIX = Path(__file__).resolve().parent / "fixtures"
S3, S4 = PROJECT_ROOT / "data" / "clean" / "step3", PROJECT_ROOT / "data" / "clean" / "step4"


def test_step4_views_match_python():
    if not (S4 / "db_manifest_step4.json").exists():
        pytest.fail("No Step 4 exports yet: run  python python/run_step4.py all  first.")
    res = ref.compare(S3 / "load", S4 / "load", S4 / "exports", est.load_scorecard())
    assert all(ok for _, ok, _ in res), "\n".join(f"{c}: {d}" for c, ok, d in res if not ok)


def test_consensus_matches_a_second_source():
    x = pd.read_csv(FIX / "estimates_crosscheck.csv", dtype=str, keep_default_na=False)
    assert len(x) >= 2, "Cross-check pending: fill tests/fixtures/estimates_crosscheck.csv after the estimates fetch (S4-D2)"
    e = pd.read_csv(S4 / "estimates.csv", dtype=str, keep_default_na=False)
    fails = []
    for r in x.itertuples():
        h = e[(e["ticker"] == r.ticker) & (e["kind"] == r.kind) & (e["period"] == r.period)]
        if len(h) != 1 or not h.iloc[0]["avg"]:
            fails.append(f"{r.ticker} {r.kind} {r.period}: no yfinance value")
            continue
        got, want = Decimal(h.iloc[0]["avg"]), Decimal(r.reference_avg)
        if abs(got - want) > abs(want) * Decimal(r.tolerance_pct) / 100:
            fails.append(f"{r.ticker} {r.period}: yfinance {got} vs {r.source} {want} (tolerance {r.tolerance_pct}%)")
    assert not fails, "\n".join(fails)
