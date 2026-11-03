"""Step 4 database tests against a real PostgreSQL server. Runs only with:  pytest -m db
Needs the Step 3 schema and data/clean/step4/estimates.csv; rebuilds the Step 4 tables and views."""
import pytest

import step3_db as db
import step4_db
import step4_estimates as est
from common import PROJECT_ROOT

pytestmark = pytest.mark.db
OUT = PROJECT_ROOT / "data" / "clean" / "step4"


@pytest.fixture(scope="module")
def cfg():
    c = db.load_db_config()
    code, _, err = db.run_psql(c, ["-tA", "-c", "SELECT 1"])
    if code:
        pytest.fail(f"PostgreSQL not reachable: {err.strip()}")
    if not (OUT / "estimates.csv").exists():
        pytest.fail("Run  python python/run_step4.py estimates  first.")
    assert step4_db.build(OUT, est.load_scorecard()), "Step 4 build or checks failed"
    return c


def _insert(cfg, sql):
    return db.run_psql(cfg, ["-c", f"SET search_path = \"{cfg['schema']}\"; {sql}"])


def test_estimates_reject_low_above_high(cfg):
    code, _, err = _insert(cfg, "INSERT INTO estimates VALUES ('NVDA','eps','0q',1,2,1,1,NULL,NULL,now(),'x','x','x');")
    assert code != 0 and ("check constraint" in err or "duplicate key" in err)


def test_rules_reject_inconsistent_thresholds(cfg):
    code, _, err = _insert(cfg, "BEGIN; DELETE FROM scorecard_rules WHERE test_no = 1; "
                                "INSERT INTO scorecard_rules VALUES (1,'x','m','higher',0.05,0.10,NULL); ROLLBACK;")
    assert code != 0 and "check constraint" in err


def test_every_company_scored_on_ten_tests(cfg):
    d = db.query_csv(cfg, f"SELECT ticker, count(*) AS n FROM \"{cfg['schema']}\".v_scorecard_detail GROUP BY ticker ORDER BY ticker")
    assert list(d["ticker"]) == ["AMD", "AVGO", "INTC", "MRVL", "NVDA", "QCOM"] and set(d["n"]) == {"10"}
