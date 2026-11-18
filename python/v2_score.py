"""Version 2, V2.5: score every member at a rebalance date and rank them.

Per member (one line per company, V2-D14): point-in-time metrics (v2_facts.metrics), gross margin against the median of
its sector's members at that date, the nine filing-based Step 4 tests (V2-D3), points and the share of available points
(V2-D13: a company needs at least min_tests_scored tests to be ranked; a test it cannot be scored on takes its sector's
median points on that test at that date, so a data gap neither helps nor hurts; a 'fail_when_null' case such as negative
earnings scores 0). Rank: total points of 18, then ROIC (V2-D4), then ticker.
A company is investable at a date only with a usable price on the trade date (V2-D16).
"""
from __future__ import annotations

import pandas as pd

import v2_facts as vf
import v2_prices as vp

TEST_COLS = lambda cfg: [f"t{k}" for k in cfg["scores"]["tests"]]   # noqa: E731


def score_date(d: str, members: pd.DataFrame, obs_by_cik: dict, P: vp.Prices, by_ticker: dict, cik_names: dict, cfg: dict) -> pd.DataFrame:
    t0 = P.trading_day_on_or_after(d) or P.trading_day_on_or_before(d)
    rows = []
    for r in members.itertuples(index=False):
        own, why = vp.owner_ok(r.ticker, r.cik_pit, r.security, by_ticker, cik_names)
        price = P.close_as_traded(r.ticker, t0) if own else None
        obs = obs_by_cik.get(r.cik_pit)
        if isinstance(obs, pd.DataFrame):
            obs = vf.prepare(obs, cfg) if len(obs) else None
        if not obs:
            m = {"fy0_end": "", "fy0_filed": "", "fy0_accn": "", "stale": False, "fail": {}, "flags": ["no company facts"]}
        else:
            m = vf.metrics(vf.pit(obs, d, cfg), d, cfg, price, P.splits(r.ticker) if own else [])
        row = {"date": d, "trade_date": t0, "ticker": r.ticker, "security": r.security, "cik": r.cik_pit, "sector": r.sector,
               "sector_basis": r.sector_basis, "price_as_traded": price, "price_note": "" if own else why}
        row.update({k: v for k, v in m.items() if k not in ("fail", "flags")})
        row["fail_reasons"] = "; ".join(f"{k}: {v}" for k, v in m["fail"].items())
        row["flags"] = "; ".join(m["flags"])
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # one line per company: prefer the ticker with a price, then alphabetical (GOOG before GOOGL)
    df = df.assign(_np=df["price_as_traded"].isna()).sort_values(["cik", "_np", "ticker"])
    dup = df.duplicated("cik", keep="first")
    df["other_classes"] = df["cik"].map(df[dup].groupby("cik")["ticker"].apply(lambda s: " ".join(s))).fillna("")
    df = df[~dup].drop(columns="_np").reset_index(drop=True)
    gm = df.get("gross_margin")
    if gm is not None:
        med = df[df["gross_margin"].notna()].groupby("sector")["gross_margin"].median()
        df["sector_gm_median"] = df["sector"].map(med)
        df["gross_margin_vs_sector"] = df["gross_margin"] - df["sector_gm_median"]
    for col in ("revenue_cagr_5y", "pe_fy", "roe_5y_avg", "quick_ratio", "gross_margin_vs_sector", "fcf_conversion",
                "net_debt_to_ebitda", "roic", "shares_change_5y"):
        if col not in df:
            df[col] = None
    tests = cfg["scores"]["tests"]
    pts, scored, maxp = [], [], []
    per_test = {k: [] for k in tests}
    for r in df.to_dict("records"):
        p = n = 0
        fails = r.get("fail_reasons") or ""
        for k, t in tests.items():
            v = r.get(t["metric"])
            if vf.finite(v):
                s_ = vf.score(v, t)
                n += 1
            elif t.get("fail_when_null") and f"{t['metric']}:" in fails:
                s_ = 0
                n += 1
            else:
                s_ = None
            per_test[k].append(s_)
            p += s_ or 0
        pts.append(p)
        scored.append(n)
        maxp.append(2 * n)
    for k in tests:
        df[f"t{k}"] = per_test[k]
    df["points"], df["tests_scored"], df["max_points"] = pts, scored, maxp
    # V2-D13: a test that cannot be scored takes its sector's median points on that test at this date (all sectors' median
    # if the sector has none), so a data gap neither helps nor hurts; rank on total points out of 2 x number of tests
    imp = [0.0] * len(df)
    for k in tests:
        col = df[f"t{k}"]
        med = df[col.notna()].groupby("sector")[f"t{k}"].median()
        allmed = col.median() if col.notna().any() else 0.0
        fill = df["sector"].map(med).fillna(allmed)
        for i, (v, f) in enumerate(zip(col, fill)):
            if pd.isna(v):
                imp[i] += float(f)
    df["imputed_points"] = imp
    df["score_total"] = df["points"] + df["imputed_points"]
    df["score_pct"] = df["score_total"] / (2 * len(tests))
    df["ranked"] = (df["price_as_traded"].notna() & (df["tests_scored"] >= cfg["scores"]["min_tests_scored"]) & ~df["stale"].astype(bool))
    df["why_not_ranked"] = [
        "" if ok else ("no usable price" if pd.isna(px) else ("latest fiscal year stale" if st else f"only {n} tests scored"))
        for ok, px, st, n in zip(df["ranked"], df["price_as_traded"], df["stale"].astype(bool), df["tests_scored"])]
    rk = df[df["ranked"]].assign(_r=df["roic"].fillna(-1e9)).sort_values(["score_pct", "_r", "ticker"], ascending=[False, False, True])
    df["rank"] = df.index.map({i: n + 1 for n, i in enumerate(rk.index)})
    df = df.sort_values(["rank", "ticker"], na_position="last").reset_index(drop=True)
    df["rank"] = [int(x) if pd.notna(x) else None for x in df["rank"]]
    return df
