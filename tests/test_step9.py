"""Step 9 offline tests: the target and rating rules, rounding, rendering and the football-field SVG. Synthetic numbers."""
import pandas as pd
import pytest

import run_step9
import step9_memo as s

CFG = {"target": {"dcf_roll_forward": True, "comps_roll_forward": False, "round_to": 5},
       "rating_bands": {"buy_above": 0.15, "sell_below": -0.10}, "catalysts": [{"when": "17 Nov", "what": "Q3"}]}


def test_target_rolls_dcf_forward_and_rounds():
    r = s.target_and_rating(dcf_w=100.0, ke=0.10, div_yield=0.0, comps=200.0, w_dcf=0.5, w_comps=0.5, price=150.0, cfg=CFG)
    assert r["dcf_fwd"] == pytest.approx(110.0) and r["target_raw"] == pytest.approx(155.0) and r["target"] == 155.0
    r = s.target_and_rating(dcf_w=100.0, ke=0.10, div_yield=0.0, comps=203.0, w_dcf=0.5, w_comps=0.5, price=150.0, cfg=CFG)
    assert r["target_raw"] == pytest.approx(156.5) and r["target"] == 155.0          # 156.5 rounds to the nearest 5
    r = s.target_and_rating(dcf_w=100.0, ke=0.10, div_yield=0.0, comps=205.0, w_dcf=0.5, w_comps=0.5, price=150.0, cfg=CFG)
    assert r["target"] == 160.0                                                         # 157.5 rounds half up


@pytest.mark.parametrize("target_price,rating", [(173.0, "Buy"), (172.5, "Hold"), (135.0, "Hold"), (134.0, "Sell")])
def test_rating_bands(target_price, rating):
    cfg = {**CFG, "target": {**CFG["target"], "dcf_roll_forward": False, "round_to": 0.5}}
    r = s.target_and_rating(dcf_w=target_price, ke=0.10, div_yield=0.0, comps=target_price, w_dcf=0.5, w_comps=0.5, price=150.0, cfg=cfg)
    assert r["rating"] == rating, (r["exp_return"], rating)


def test_dividend_yield_counts_in_expected_return():
    r = s.target_and_rating(dcf_w=100.0, ke=0.10, div_yield=0.02, comps=100.0, w_dcf=0.5, w_comps=0.5, price=100.0, cfg=CFG)
    assert r["dcf_fwd"] == pytest.approx(108.0) and r["exp_return"] == pytest.approx(r["target"] / 100 - 1 + 0.02)


def test_render_fails_on_unfilled_placeholder():
    assert s.render("Target {target:.0f}", {"target": 260.0}, {}, CFG) == "Target 260"
    with pytest.raises(KeyError):
        s.render("Target {nope}", {"target": 260.0}, {}, CFG)


def test_football_svg_marks_price_and_target():
    ff = pd.DataFrame([{"method": "DCF", "low": "50", "high": "150", "point": "100"}, {"method": "Comps P/E", "low": "120", "high": "300", "point": "200"}])
    svg = s.football_svg(ff, price=180.0, target=210.0)
    assert svg.startswith("<svg") and "Price $180.00" in svg and "Target $210" in svg and svg.count("<rect") == 3


def test_markdown_table():
    t = s.table([["a", "1"]], ["x", "y"])
    assert t.splitlines() == ["| x | y |", "| --- | ---: |", "| a | 1 |"]


def test_checks_catch_a_wrong_rating():
    n = {"w_dcf": 0.5, "dcf_w": 100.0, "ke": 0.1, "div_yield": 0.0, "w_comps": 0.5, "comps": 200.0, "target_raw": 155.0, "target": 155.0,
         "price": 150.0, "exp_return": 155 / 150 - 1, "rating": "Buy"}
    res = {"numbers": n, "cfg": CFG, "claims": [], "sources": [(k, v, "x") for k, v in n.items()],
           "memo": "# X: Buy, 12-month target $155 (+3.3% vs $150.00 on d)\n## Exhibits"}
    out = {c: ok for c, ok, _ in run_step9.checks(res, "{target}")}
    assert out["M3_target_arithmetic"] and not out["M4_rating_follows_bands"]          # +3.3% is a Hold, not a Buy
