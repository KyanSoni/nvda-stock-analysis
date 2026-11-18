"""Version 2, V2.4, V2.6 and V2.7 offline tests: price lookups (as-traded close, forward fill, held after delisting, reused
tickers), portfolio mechanics against hand-computed values (drift, costs, turnover), statistics on known series, and the fast
random-portfolio method against the full engine. Synthetic prices; no network."""
import math

import pandas as pd
import pytest

import v2_backtest as bt
import v2_prices as vp
from run_v2_backtest import fast_random

DAYS = ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08"]


def panel(series: dict, splits: dict | None = None) -> pd.DataFrame:
    rows = []
    for t, vals in series.items():
        for d, v in zip(DAYS, vals):
            if v is not None:
                rows.append({"ticker": t, "date": d, "close": v, "adj_close": v, "split": (splits or {}).get((t, d), 0.0)})
    return pd.DataFrame(rows)


def test_close_as_traded_and_staleness():
    P = vp.Prices(panel({"SPY": [1] * 5, "AAA": [10, 10, 10, 10, 10]}, {("AAA", "2020-01-07"): 2.0}))
    assert P.close_as_traded("AAA", "2020-01-03") == 20.0     # before the 2-for-1 split it traded at twice Yahoo's Close
    assert P.close_as_traded("AAA", "2020-01-08") == 10.0
    assert P.trading_day_on_or_after("2020-01-04") == "2020-01-06" and P.trading_day_on_or_before("2020-01-04") == "2020-01-03"
    Q = vp.Prices(panel({"SPY": [1] * 5, "OLD": [5, None, None, None, None]}))
    assert Q.close_as_traded("OLD", "2020-01-03") == 5.0
    assert Q._idx("OLD", "2020-01-08", max_stale=2) is None   # too stale to trade on


def test_adj_series_forward_fills_and_holds_after_last_price():
    P = vp.Prices(panel({"SPY": [1] * 5, "AAA": [10, None, 12, None, None]}))
    s = P.adj_series("AAA", DAYS[0], DAYS[-1])
    assert s.tolist() == [10, 10, 12, 12, 12]
    assert math.isnan(P.adj_series("ZZZ", DAYS[0], DAYS[-1]).iloc[0])


def test_owner_ok_rejects_reused_tickers():
    names = {"0000000009": {"SEA"}, "0000000001": {"SPECTRA ENERGY"}}
    assert vp.owner_ok("SE", "0000000001", "Spectra Energy", {"SE": "0000000009"}, names)[0] is False
    assert vp.owner_ok("SE", "0000000009", "Sea", {"SE": "0000000009"}, names)[0] is True
    assert vp.owner_ok("GONE", "0000000001", "Gone", {}, names)[0] is True


def test_run_drift_cost_and_compounding():
    P = vp.Prices(panel({"SPY": [1] * 5, "A": [10, 11, 12, 12, 12], "B": [10, 9, 8, 8, 16], "C": [5, 5, 5, 5, 10]}))
    picks = {"2020-01-02": ["A", "B"], "2020-01-06": ["A", "C"]}
    s, per = bt.run(P, picks, "2020-01-08", cost=0.01)
    # period 1: buy A and B (traded 1.0, cost 1%), end value 0.99 x (0.5 x 1.2 + 0.5 x 0.8) = 0.99
    assert per.iloc[0]["return"] == pytest.approx(0.99 - 1)
    # drifted weights A 0.6, B 0.4 -> new A 0.5, C 0.5: traded 0.1 + 0.4 + 0.5 = 1.0
    assert per.iloc[1]["turnover"] == pytest.approx(1.0)
    v2 = 0.99 * (1 - 0.01) * (0.5 * 1.0 + 0.5 * 2.0)
    assert s.iloc[-1] == pytest.approx(v2)
    assert s.iloc[0] == 1.0
    assert math.prod(1 + r for r in per["return"]) == pytest.approx(s.iloc[-1])


def test_stats_on_known_series():
    idx = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2020-01-01", "2022-01-01")]
    v = pd.Series([2 ** (i / (len(idx) - 1)) for i in range(len(idx))], index=idx)
    x = bt.stats(v, v)
    yrs = (pd.Timestamp(idx[-1]) - pd.Timestamp(idx[0])).days / 365.25
    assert x["cagr"] == pytest.approx(2 ** (1 / yrs) - 1)
    assert x["max_drawdown"] == 0 and x["tracking_error"] == pytest.approx(0)
    dd = pd.Series([1, 2, 1, 1.5], index=["2020-01-01", "2020-06-01", "2021-01-01", "2021-06-01"])
    assert bt.stats(dd)["max_drawdown"] == pytest.approx(-0.5)


def test_fast_random_matches_engine_for_a_full_draw():
    P = vp.Prices(panel({"SPY": [1] * 5, "A": [10, 11, 12, 12, 12], "B": [10, 9, 8, 8, 16]}))
    sched = {"2020-01-02": pd.DataFrame({"ticker": ["A", "B"]}), "2020-01-06": pd.DataFrame({"ticker": ["A", "B"]})}
    s, _ = bt.run(P, {k: ["A", "B"] for k in sched}, "2020-01-08", 0.001)
    yrs = (pd.Timestamp("2020-01-08") - pd.Timestamp("2020-01-02")).days / 365.25
    got = fast_random(P, sched, "2020-01-08", 2, 3, 1, 0.001)
    assert len(got) == 3 and all(g == pytest.approx(s.iloc[-1] ** (1 / yrs) - 1) for g in got)
