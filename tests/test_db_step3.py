"""Step 3b database tests against a real PostgreSQL server. Runs only with:  pytest -m db
Uses config/database.yaml and the libpq environment ($env:PGPASSWORD); rebuilds the analytics schema."""
import pandas as pd
import pytest

import step3_db as db
from common import PROJECT_ROOT

pytestmark = pytest.mark.db
OUT = PROJECT_ROOT / "data" / "clean" / "step3"


@pytest.fixture(scope="module")
def cfg():
    c = db.load_db_config()
    code, _, err = db.run_psql(c, ["-tA", "-c", "SELECT 1"])
    if code:
        pytest.fail(f"PostgreSQL not reachable: {err.strip()}")
    if not (OUT / "facts_extended.csv").exists():
        pytest.fail("Run  python python/run_step3.py facts  first.")
    assert db.build(OUT), "database build or in-database checks failed"
    return c


def test_constraints_reject_a_reported_row_without_accession(cfg):
    sql = (f"SET search_path = \"{cfg['schema']}\"; INSERT INTO facts (ticker, line_item, fiscal_year, fiscal_period, value_basis, "
           "period_end, value, unit, display_value, display_unit, support_item) VALUES "
           "('NVDA','revenue',2026,'FY','reported_annual','2026-01-25',1,'USD',1,'USD millions',false);")
    code, _, err = db.run_psql(cfg, ["-c", sql])
    assert code != 0 and "check constraint" in err


def test_constraints_reject_unknown_value_basis(cfg):
    sql = (f"SET search_path = \"{cfg['schema']}\"; INSERT INTO facts (ticker, line_item, fiscal_year, fiscal_period, value_basis, "
           "period_end, value, unit, display_value, display_unit, support_item) VALUES "
           "('NVDA','revenue',2026,'FY','guessed','2026-01-25',1,'USD',1,'USD millions',false);")
    code, _, err = db.run_psql(cfg, ["-c", sql])
    assert code != 0 and "check constraint" in err


def test_every_company_has_a_valuation_row(cfg):
    v = db.query_csv(cfg, f"SELECT ticker, market_cap, enterprise_value FROM \"{cfg['schema']}\".v_valuation_cutoff ORDER BY ticker")
    assert list(v["ticker"]) == ["AMD", "AVGO", "INTC", "MRVL", "NVDA", "QCOM"]
    assert (v["market_cap"] != "").all() and (v["enterprise_value"] != "").all()


def test_row_counts_match_load_files(cfg):
    m = db.query_csv(cfg, f"SELECT table_name, rows FROM \"{cfg['schema']}\".load_manifest ORDER BY table_name")
    for r in m.itertuples():
        n = len(pd.read_csv(OUT / "load" / f"{r.table_name}.csv", dtype=str))
        assert int(r.rows) == n
