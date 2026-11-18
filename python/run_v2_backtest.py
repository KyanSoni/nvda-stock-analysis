"""Version 2, V2.6 and V2.7: run the backtest and the robustness tests, offline.

Main test (V2-D4, V2-D5): every 1 April 2016-2025, buy the 30 highest-ranked companies in equal weights, hold a year,
0.1% cost a side; compare with SPY and with an equal-weight portfolio of every ranked company (V2-D15).
Robustness (V2.7), one change at a time: 20 or 50 holdings; no costs; a 1 July rebalance; today's members only (shows how
much survivorship bias would flatter the result); 1,000 random 30-stock portfolios from the same ranked companies.

Writes data/clean/v2/backtest/: nav_daily.csv, periods.csv, holdings.csv, stats.csv, robustness.csv, random_cagrs.csv,
manifest_v2_backtest.json. Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yaml

import v2_backtest as bt
import v2_prices as vp
from common import PROJECT_ROOT, write_csv
from run_v2_prices import load_panel

CFG = PROJECT_ROOT / "config" / "v2.yaml"
OUT = PROJECT_ROOT / "data" / "clean" / "v2" / "backtest"


def schedule(sc: pd.DataFrame, cfg: dict, month_day: str) -> tuple[dict, str, str]:
    """{trade_date: ranked frame} for the test years, the end trade date (next year's rebalance) and that end's label."""
    b = cfg["backtest"]
    dates = [f"{y}-{month_day}" for y in range(b["first_year"], b["last_year"] + 2)]
    have = sorted(set(sc["date"]) & set(dates))
    if len(have) < 2:
        return {}, "", ""
    sched = {}
    for d in have[:-1]:
        g = sc[(sc["date"] == d) & (sc["ranked"])].sort_values("rank")
        sched[g["trade_date"].iloc[0]] = g
    end = sc[sc["date"] == have[-1]]["trade_date"].iloc[0]
    return sched, end, have[-1]


def picks_top(sched: dict, n: int, only: set | None = None) -> dict:
    out = {}
    for t, g in sched.items():
        g = g if only is None else g[g["ticker"].isin(only)]
        out[t] = g["ticker"].head(n).tolist()
    return out


def fast_random(P: vp.Prices, sched: dict, end: str, n_hold: int, n: int, seed: int, cost: float) -> list[float]:
    """Random equal-weight portfolios with the engine's mechanics, computed from each period's end-of-period price
    relatives (equal weights drift with prices, so a period's growth is the mean relative of the names held)."""
    cuts = bt.periods(list(sched), end)
    rel = []
    for a, b in cuts:
        names = sorted(sched[a]["ticker"])
        r = {}
        for t in names:
            s = P.adj_series(t, a, b)
            r[t] = s.iloc[-1] / s.iloc[0] if pd.notna(s.iloc[0]) and s.iloc[0] else 1.0
        rel.append(r)
    years = (pd.Timestamp(end) - pd.Timestamp(cuts[0][0])).days / 365.25
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        v, held = 1.0, {}
        for r in rel:
            pick = rng.sample(sorted(r), min(n_hold, len(r)))
            w = 1.0 / len(pick)
            traded = sum(abs((w if t in pick else 0.0) - held.get(t, 0.0)) for t in set(pick) | set(held)) if held else 1.0
            g = np.array([r[t] for t in pick])
            v *= (1 - cost * traded) * g.mean()
            held = dict(zip(pick, g / g.sum()))
        out.append(v ** (1 / years) - 1)
    return out


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    b, rb = cfg["backtest"], cfg["robustness"]
    sc = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "v2" / "scores" / "scores_by_date.csv", dtype={"date": str, "trade_date": str, "ticker": str, "cik": str},
                     keep_default_na=False, na_values=[""])
    sc["ranked"] = sc["ranked"].astype(str) == "True"
    print("Loading prices ...", flush=True)
    P = vp.Prices(load_panel(cfg))
    sched, end, end_label = schedule(sc, cfg, b["rebalance_month_day"])
    if not sched:
        print("Not enough rebalance dates in scores_by_date.csv")
        return 1
    n, cost = b["holdings"], b["cost_per_side"]
    strat, per = bt.run(P, picks_top(sched, n), end, cost)
    univ, per_u = bt.run(P, {t: g["ticker"].tolist() for t, g in sched.items()}, end, 0.0)
    start = min(sched)
    spy = bt.benchmark(P, b["benchmark"], start, end)
    nav = pd.DataFrame({"strategy": strat, "universe_ew": univ, "spy": spy}).ffill()
    cuts = bt.periods(list(sched), end)
    per["universe_ew"] = bt.period_returns(univ, cuts)
    per["spy"] = bt.period_returns(spy, cuts)
    per["excess_vs_spy"] = per["return"] - per["spy"]
    per["excess_vs_universe"] = per["return"] - per["universe_ew"]
    st = pd.DataFrame([{"series": k, **bt.stats(nav[k], nav["spy"] if k != "spy" else None, cfg["backtest_v2"]["rf"])} for k in nav.columns])

    hold = []
    for (a, z) in cuts:
        g = sched[a].head(n)
        for r in g.itertuples():
            s = P.adj_series(r.ticker, a, z)
            hold.append({"trade_date": a, "period_end": z, "rank": int(r.rank), "ticker": r.ticker, "security": r.security, "sector": r.sector,
                         "score_total": r.score_total, "tests_scored": int(r.tests_scored), "roic": r.roic,
                         "return": s.iloc[-1] / s.iloc[0] - 1 if pd.notna(s.iloc[0]) else None,
                         "prices_end_early": P.last_date(r.ticker) < z})
    hold = pd.DataFrame(hold)

    # ---- robustness, one change at a time ----
    rob = []

    def add(name, s, note=""):
        x = bt.stats(s, spy.reindex(s.index).ffill() if len(s) else None)
        rob.append({"variant": name, "cagr": x["cagr"], "volatility": x["volatility"], "sharpe": x["sharpe"], "max_drawdown": x["max_drawdown"],
                    "information_ratio": x.get("information_ratio"), "vs_spy_cagr": x["cagr"] - bt.stats(spy.reindex(s.index).ffill())["cagr"], "note": note})
    add(f"Main: top {n}, 1 April, {cost:.1%} a side", strat)
    for k in rb["holdings"]:
        if k != n:
            add(f"Top {k}", bt.run(P, picks_top(sched, k), end, cost)[0])
    add("No trading costs", bt.run(P, picks_top(sched, n), end, 0.0)[0])
    cur = set(pd.read_csv(PROJECT_ROOT / cfg["universe"]["clean_dir"] / "constituents_current.csv", dtype=str)["ticker"])
    add("Today's members only (survivorship-biased)", bt.run(P, picks_top(sched, n, cur), end, cost)[0],
        "only companies still in the index today; shows how much survivorship would flatter the test")
    add("Equal-weight all ranked (universe benchmark)", univ, "no costs")
    js, jend, _ = schedule(sc, cfg, rb["alt_month_day"])
    if js:
        jstrat = bt.run(P, picks_top(js, n), jend, cost)[0]
        x = bt.stats(jstrat, bt.benchmark(P, b["benchmark"], min(js), jend))
        spj = bt.stats(bt.benchmark(P, b["benchmark"], min(js), jend))
        rob.append({"variant": f"1 July rebalance ({min(js)[:7]} to {jend[:7]})", "cagr": x["cagr"], "volatility": x["volatility"], "sharpe": x["sharpe"],
                    "max_drawdown": x["max_drawdown"], "information_ratio": x.get("information_ratio"), "vs_spy_cagr": x["cagr"] - spj["cagr"],
                    "note": "SPY over the same July-to-July span"})
    print(f"Random portfolios ({rb['random_portfolios']}) ...", flush=True)
    rc = fast_random(P, sched, end, n, rb["random_portfolios"], rb["random_seed"], cost)
    main_cagr = st.set_index("series").loc["strategy", "cagr"]
    pct = sum(x < main_cagr for x in rc) / len(rc)
    rob.append({"variant": f"Random {n}-stock portfolios: median of {len(rc)}", "cagr": float(np.median(rc)), "volatility": None, "sharpe": None,
                "max_drawdown": None, "information_ratio": None, "vs_spy_cagr": float(np.median(rc)) - st.set_index("series").loc["spy", "cagr"],
                "note": f"the screen beat {pct:.0%} of random portfolios; 5th-95th percentile {np.percentile(rc, 5):.2%} to {np.percentile(rc, 95):.2%}"})
    rob = pd.DataFrame(rob)

    OUT.mkdir(parents=True, exist_ok=True)
    nav.index.name = "date"
    nav.reset_index().to_csv(OUT / "nav_daily.csv", index=False, lineterminator="\n")
    write_csv(per, OUT / "periods.csv", ["start"])
    hold.sort_values(["trade_date", "rank"]).to_csv(OUT / "holdings.csv", index=False, lineterminator="\n")
    write_csv(st, OUT / "stats.csv", ["series"])
    rob.to_csv(OUT / "robustness.csv", index=False, lineterminator="\n")
    pd.DataFrame({"cagr": rc}).to_csv(OUT / "random_cagrs.csv", index=False, lineterminator="\n")

    full = len(per) == b["last_year"] - b["first_year"] + 1 and (per["holdings"] == n).all()
    ident = abs(math.prod(1 + r for r in per["return"]) - strat.iloc[-1]) < 1e-9
    cks = [("B1_full_periods", full, f"{len(per)} holding periods {per['start'].min()} to {end}, holdings {sorted(set(per['holdings']))}", "error"),
           ("B2_daily_values_complete", nav.notna().all().all() and len(nav) > 200 * len(per), f"{len(nav)} trading days, no gaps", "error"),
           ("B3_returns_compound_to_value", ident, f"product of period returns {math.prod(1 + r for r in per['return']):.6f} vs final value {strat.iloc[-1]:.6f}", "error"),
           ("B4_holdings_ending_early", True, f"{int(hold['prices_end_early'].sum())} of {len(hold)} holdings' prices end before the period does (held at last price)", "info"),
           ("B5_random_benchmark", len(rc) == rb["random_portfolios"], f"{len(rc)} random portfolios; the screen beat {pct:.0%}", "info")]
    print(f"V2.6 backtest {start} to {end} ({end_label} rebalance) -> {OUT}")
    for c, ok, d, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl != 'error' else 'FAIL')}  {c}: {d}")
    s = st.set_index("series")
    for k, lab in (("strategy", f"Top {n} (net of costs)"), ("universe_ew", "Equal-weight all ranked"), ("spy", "SPY")):
        x = s.loc[k]
        print(f"  {lab:<26} CAGR {x['cagr']:7.2%}  vol {x['volatility']:6.2%}  Sharpe {x['sharpe']:5.2f}  max drawdown {x['max_drawdown']:7.2%}"
              + (f"  IR vs SPY {x['information_ratio']:5.2f}" if k != "spy" else ""))
    print(f"  Years beating SPY: {(per['excess_vs_spy'] > 0).sum()}/{len(per)}; beating the equal-weight universe: {(per['excess_vs_universe'] > 0).sum()}/{len(per)}")
    print("  Robustness:")
    for r in rob.itertuples():
        print(f"    {r.variant:<52} CAGR {r.cagr:7.2%}  vs SPY {r.vs_spy_cagr:+7.2%}  {r.note}")
    m = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "start": start, "end": end,
         "checks": [{"check": c, "passed": bool(ok), "detail": d, "level": lvl} for c, ok, d, lvl in cks]}
    (OUT / "manifest_v2_backtest.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
