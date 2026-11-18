"""Version 2, V2.3 and V2.5 offline tests: extracting annual-report facts, the point-in-time cut (filed before the date,
latest-filed wins, concept priority per year), the Version 1 formulas, split adjustment, staleness, scored fails, and
scoring/ranking a date (one line per company, gross margin vs sector median). Synthetic companies; no network."""
import pandas as pd
import pytest
import yaml

import v2_facts as vf
import v2_prices as vp
import v2_score as vs
from common import PROJECT_ROOT

CFG = yaml.safe_load((PROJECT_ROOT / "config" / "v2.yaml").read_text(encoding="utf-8"))
ENDS = ["2010-12-31", "2011-12-31", "2012-12-31", "2013-12-31", "2014-12-31", "2015-12-31"]


def fact(concept, end, val, filed, start=None, form="10-K", unit="USD", accn=None):
    return {"concept": concept, "unit": unit, "end": end, "val": val, "filed": filed, "form": form, "accn": accn or f"a-{filed}",
            **({"start": start} if start else {})}


def company(extra=()):
    """Six fiscal years (calendar) each filed in its own 10-K on 1 March of the next year. Revenue doubles over 5 years."""
    rows = []
    for i, e in enumerate(ENDS):
        y = int(e[:4])
        st, fd = f"{y}-01-01", f"{y + 1}-03-01"
        rev = 1000 * 2 ** (i / 5)
        rows += [fact("Revenues", e, rev, fd, st), fact("CostOfRevenue", e, rev * 0.4, fd, st), fact("OperatingIncomeLoss", e, 200, fd, st),
                 fact("NetIncomeLoss", e, 150, fd, st), fact("EarningsPerShareDiluted", e, 1.5, fd, st, unit="USD/shares"),
                 fact("WeightedAverageNumberOfDilutedSharesOutstanding", e, 100, fd, st, unit="shares"),
                 fact("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", e, 190, fd, st),
                 fact("IncomeTaxExpenseBenefit", e, 40, fd, st), fact("NetCashProvidedByUsedInOperatingActivities", e, 180, fd, st),
                 fact("PaymentsToAcquirePropertyPlantAndEquipment", e, 30, fd, st), fact("DepreciationDepletionAndAmortization", e, 50, fd, st),
                 fact("AssetsCurrent", e, 600, fd), fact("LiabilitiesCurrent", e, 300, fd), fact("InventoryNet", e, 100, fd),
                 fact("StockholdersEquity", e, 1000, fd), fact("CashAndCashEquivalentsAtCarryingValue", e, 100, fd),
                 fact("LongTermDebtNoncurrent", e, 300, fd), fact("LongTermDebtCurrent", e, 50, fd)]
    rows += list(extra)
    facts = {"us-gaap": {}}
    for r in rows:
        units = facts["us-gaap"].setdefault(r.pop("concept"), {"units": {}})["units"]
        units.setdefault(r.pop("unit"), []).append(r)
    facts["us-gaap"]["SomethingElse"] = {"units": {"USD": [fact("x", "2015-12-31", 1, "2016-03-01")]}}
    return vf.extract({"facts": facts}, "0000000001", CFG)


def test_extract_keeps_needed_concepts_and_annual_forms_only():
    obs = company([fact("Revenues", "2015-09-30", 1, "2015-11-01", "2015-07-01", form="10-Q")])
    assert "SomethingElse" not in set(obs["concept"]) and "10-Q" not in set(obs["form"])
    assert (obs[obs["concept"] == "AssetsCurrent"]["days"] == -1).all()


def test_pit_cuts_at_filing_date_and_latest_filed_wins():
    obs = company([fact("Revenues", "2015-12-31", 9999, "2016-08-01", "2015-01-01", form="10-K/A")])
    p = vf.pit(obs, "2016-04-01", CFG)
    assert p["revenue"][-1].end == "2015-12-31" and p["revenue"][-1].value == pytest.approx(2000)
    p = vf.pit(obs, "2016-09-01", CFG)                      # the amendment is known by September
    assert p["revenue"][-1].value == 9999
    p = vf.pit(obs, "2016-03-01", CFG)                      # FY2015 10-K filed on the date itself is not yet known
    assert p["revenue"][-1].end == "2014-12-31"


def test_concept_priority_per_year():
    obs = company([fact("RevenueFromContractWithCustomerExcludingAssessedTax", "2015-12-31", 5, "2016-03-01", "2015-01-01")])
    p = vf.pit(obs, "2016-04-01", CFG)
    assert p["revenue"][-1].concept == "Revenues"           # first listed concept wins when both exist
    assert vf.pit(vf.prepare(obs, CFG), "2016-04-01", CFG) == p   # prepared once, cut per date: same answer


def test_metrics_follow_version1_formulas():
    m = vf.metrics(vf.pit(company(), "2016-04-01", CFG), "2016-04-01", CFG, price_as_traded=30.0, splits=[])
    assert m["fy0_end"] == "2015-12-31" and not m["stale"]
    assert m["revenue_cagr_5y"] == pytest.approx(2 ** 0.2 - 1)
    assert m["gross_margin"] == pytest.approx(0.6)          # derived from cost of revenue
    assert any("derived" in f for f in m["flags"])
    assert m["roe_5y_avg"] == pytest.approx(0.15)
    assert m["quick_ratio"] == pytest.approx(500 / 300)
    assert m["fcf_conversion"] == pytest.approx(150 / 150)
    assert m["net_debt_to_ebitda"] == pytest.approx((350 - 100) / 250)
    t = 40 / 190
    assert m["roic"] == pytest.approx(200 * (1 - t) / (350 - 100 + 1000))
    assert m["shares_change_5y"] == pytest.approx(0.0)
    assert m["pe_fy"] == pytest.approx(20.0)


def test_splits_after_filing_put_shares_and_eps_on_todays_basis():
    obs = company([fact("WeightedAverageNumberOfDilutedSharesOutstanding", "2015-12-31", 400, "2016-03-01", "2015-01-01", unit="shares",
                        accn="b")])
    # a 4-for-1 split in 2014 after the FY2010 shares were filed; FY2015 filed after it reports 400 (post-split)
    obs = obs[~((obs["concept"] == "WeightedAverageNumberOfDilutedSharesOutstanding") & (obs["end"] == "2015-12-31") & (obs["value"] == 100))]
    m = vf.metrics(vf.pit(obs, "2016-04-01", CFG), "2016-04-01", CFG, 30.0, [("2014-06-01", 4.0)])
    assert m["shares_change_5y"] == pytest.approx(0.0)      # 400 vs 100 x 4
    m2 = vf.metrics(vf.pit(company(), "2016-04-01", CFG), "2016-04-01", CFG, 7.5, [("2016-03-15", 4.0)])
    assert m2["pe_fy"] == pytest.approx(7.5 / (1.5 / 4))    # EPS filed before the split, price after it


def test_stale_and_scored_fails():
    m = vf.metrics(vf.pit(company(), "2017-07-01", CFG), "2017-07-01", CFG, 30.0)
    assert m["stale"]
    loss = company([fact("NetIncomeLoss", "2015-12-31", -10, "2016-03-02", "2015-01-01"),
                    fact("EarningsPerShareDiluted", "2015-12-31", -0.1, "2016-03-02", "2015-01-01", unit="USD/shares")])
    m = vf.metrics(vf.pit(loss, "2016-04-01", CFG), "2016-04-01", CFG, 30.0)
    assert m["pe_fy"] is None and "pe_fy" in m["fail"] and "fcf_conversion" in m["fail"]


def test_score_rule_matches_step4():
    t = {"direction": "higher", "pass": 0.10, "near": 0.05}
    assert [vf.score(x, t) for x in (0.11, 0.10, 0.05, 0.04)] == [2, 1, 1, 0]
    t = {"direction": "lower", "pass": 25, "near": 35}
    assert [vf.score(x, t) for x in (24, 25, 35, 36)] == [2, 1, 1, 0]


def test_score_date_ranks_one_line_per_company():
    obs = company()
    lean = company([fact("Revenues", e, 1000, f"{int(e[:4]) + 1}-03-02", f"{e[:4]}-01-01") for e in ENDS])   # flat revenue, later filing wins
    panel = pd.DataFrame([{"ticker": t, "date": d, "close": 30.0, "adj_close": 30.0, "split": 0.0}
                          for t in ("AAA", "BBB", "BBBK", "SPY") for d in ("2016-03-31", "2016-04-01", "2016-04-04")])
    P = vp.Prices(panel)
    members = pd.DataFrame([
        {"ticker": "AAA", "security": "Alpha", "cik_pit": "1", "sector": "Information Technology", "sector_basis": "wikipedia_gics"},
        {"ticker": "BBB", "security": "Beta", "cik_pit": "2", "sector": "Information Technology", "sector_basis": "wikipedia_gics"},
        {"ticker": "BBBK", "security": "Beta", "cik_pit": "2", "sector": "Information Technology", "sector_basis": "wikipedia_gics"}])
    df = vs.score_date("2016-04-01", members, {"1": obs, "2": lean}, P, {}, {}, CFG)
    assert df["ticker"].tolist() == ["AAA", "BBB"] and df.iloc[1]["other_classes"] == "BBBK"
    assert df.iloc[0]["rank"] == 1 and df.iloc[0]["t1"] == 2 and df.iloc[1]["t1"] == 0       # 14.9% CAGR passes; flat revenue fails
    assert df.iloc[0]["t6"] == 2 and df["sector_gm_median"].nunique() == 1                    # gross margin vs the sector's median
