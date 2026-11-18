"""Version 2, V2.6 and V2.7: the backtest engine and its statistics.

Portfolio mechanics (V2-D5, V2-D16):
  - At each rebalance date the top N ranked companies are bought in equal weights at the close of the trade date
    (the first trading day on or after the rebalance date). Holdings drift with their total-return prices until the next
    rebalance. A holding whose Yahoo prices end (taken over, delisted) is held at its last price (as cash) to the next rebalance.
  - Cost: cost_per_side x the total weight traded at each rebalance (the first purchase counts as traded).
  - Benchmarks: SPY total return (adjusted close); and an equal-weight portfolio of every ranked company, rebuilt the same
    way, which shares the portfolio's data and survivorship limits (V2-D15), so the gap between the two is the screen's effect.
Statistics on daily values: CAGR, annualised volatility, Sharpe on returns over rf (0, labelled), maximum drawdown,
information ratio and tracking error against a benchmark, and returns per holding period.
"""
from __future__ import annotations

import math

import pandas as pd

import v2_prices as vp


def periods(trade_dates: list[str], end: str) -> list[tuple[str, str]]:
    ds = sorted(trade_dates)
    return [(a, b) for a, b in zip(ds, ds[1:] + [end]) if a < b]


def run(P: vp.Prices, picks: dict, end: str, cost: float = 0.0) -> tuple[pd.Series, pd.DataFrame]:
    """picks: trade_date -> list of tickers. Returns daily portfolio value (1.0 before the first purchase) and one row
    per holding period (return net of that rebalance's cost)."""
    value, out, rows = 1.0, [], []
    held = {}                                  # ticker -> weight just before the rebalance (after drift)
    for a, b in periods(list(picks), end):
        names = [t for t in picks[a] if P.has(t)]
        if not names:
            continue
        w_new = {t: 1.0 / len(names) for t in names}
        traded = sum(abs(w_new.get(t, 0.0) - held.get(t, 0.0)) for t in set(w_new) | set(held)) if held else 1.0
        after_cost = value * (1 - cost * traded)
        rel = pd.DataFrame({t: P.adj_series(t, a, b) for t in names})
        rel = rel.divide(rel.iloc[0]).fillna(1.0)   # ranked names have a price on the trade date; guard anyway
        port = rel.mul(pd.Series(w_new)).sum(axis=1) * after_cost
        if not out:
            port.iloc[0] = value               # the first day closes before the purchase cost
            out.append(port)
        else:
            out.append(port.iloc[1:])
        last = rel.iloc[-1].mul(pd.Series(w_new))
        held = (last / last.sum()).to_dict()
        rows.append({"start": a, "end": b, "holdings": len(names), "turnover": traded, "cost": cost * traded,
                     "return": port.iloc[-1] / value - 1, "ended_early": sum(P.last_date(t) < b for t in names)})
        value = port.iloc[-1]
    return (pd.concat(out) if out else pd.Series(dtype=float)), pd.DataFrame(rows)


def benchmark(P: vp.Prices, sym: str, start: str, end: str) -> pd.Series:
    s = P.adj_series(sym, start, end)
    return s / s.iloc[0]


def stats(v: pd.Series, bench: pd.Series | None = None, rf: float = 0.0, days: int = 252) -> dict:
    v = v.dropna()
    r = v.pct_change().dropna()
    yrs = (pd.Timestamp(v.index[-1]) - pd.Timestamp(v.index[0])).days / 365.25
    cagr = (v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else float("nan")
    vol = r.std() * math.sqrt(days)
    sharpe = ((r.mean() - rf / days) * days) / vol if vol else float("nan")
    dd = (v / v.cummax() - 1).min()
    out = {"start": v.index[0], "end": v.index[-1], "years": yrs, "total_return": v.iloc[-1] / v.iloc[0] - 1, "cagr": cagr,
           "volatility": vol, "sharpe": sharpe, "max_drawdown": dd}
    if bench is not None:
        b = bench.reindex(v.index).ffill().pct_change().dropna()
        act = (r - b.reindex(r.index)).dropna()
        te = act.std() * math.sqrt(days)
        out.update(tracking_error=te, information_ratio=(act.mean() * days) / te if te else float("nan"))
    return out


def period_returns(v: pd.Series, cuts: list[tuple[str, str]]) -> list[float]:
    out = []
    for a, b in cuts:
        x = v[(v.index >= a) & (v.index <= b)]
        out.append(x.iloc[-1] / x.iloc[0] - 1 if len(x) > 1 else float("nan"))
    return out
