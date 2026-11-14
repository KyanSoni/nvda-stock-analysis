"""Step 9 reconciliation: the memo's target and headline figures tie to the Step 6 and Step 7 outputs, and the memo in
docs/memo is the current render (not stale). Runs only with:  pytest -m reconciliation"""
import pandas as pd
import pytest

import run_step9
import step9_memo as s
from common import PROJECT_ROOT

pytestmark = pytest.mark.reconciliation
CLEAN = PROJECT_ROOT / "data" / "clean"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


@pytest.fixture(scope="module")
def nums():
    p = CLEAN / "step9" / "memo_numbers.csv"
    if not p.exists():
        pytest.fail("No Step 9 output yet: run  python python/run_step9.py  first.")
    return rd(p).set_index("name")["value"]


def test_target_ties_to_step6_and_step7(nums):
    dv = rd(CLEAN / "step6" / "dcf_values.csv").set_index("ticker").loc["NVDA"]
    di = rd(CLEAN / "step6" / "dcf_inputs.csv").set_index("ticker").loc["NVDA"]
    bl = rd(CLEAN / "step7" / "comps_blend.csv").iloc[0]
    assert abs(float(nums["dcf_w"]) - float(dv["weighted_per_share"])) < 1e-5
    assert abs(float(nums["comps"]) - float(bl["comps_value"])) < 1e-5
    assert abs(float(nums["ke"]) - float(di["cost_of_equity"])) < 1e-6
    raw = 0.5 * float(dv["weighted_per_share"]) * (1 + float(di["cost_of_equity"]) - float(nums["div_yield"])) + 0.5 * float(bl["comps_value"])
    assert abs(raw - float(nums["target_raw"])) < 1e-3 and abs(float(nums["target"]) - raw) <= 2.5


def test_memo_in_docs_is_current_and_leads_with_the_call(nums):
    assert run_step9.main(["--check"]) == 0, "docs/memo is stale or a check fails: run python/run_step9.py"
    first = s.MEMO.read_text(encoding="utf-8").splitlines()[0]
    assert nums["rating"] in first and f"${float(nums['target']):,.0f}" in first
