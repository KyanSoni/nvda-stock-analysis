"""Step 2 market data processing (M2b): prices, corporate actions, cutoff, shares outstanding, risk-free rate.

yfinance columns (issue I-25): "Close" is split-adjusted (not as traded); "Adj Close" is split- and
dividend-adjusted. close_as_traded = Close x the product of all later split ratios, so it can be checked
against historical quotes. Market inputs use the cutoff date (D12), on which Close is the traded price.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from validate_m1 import _num

NY = ZoneInfo("America/New_York")
PRICE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume", "dividend", "split_ratio",
                 "close_as_traded", "source_file", "source_sha256"]


def load_prices(coll: Path, symbols: list[str], manifest: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for sym in symbols:
        path = coll / "market" / f"prices_{sym}.csv"
        if not path.exists():
            continue
        raw = pd.read_csv(path, dtype=str, keep_default_na=False)
        df = pd.DataFrame({
            "ticker": sym,
            "date": raw["Date"].str[:10],
            "open": raw["Open"], "high": raw["High"], "low": raw["Low"], "close": raw["Close"],
            "adj_close": raw["Adj Close"], "volume": raw["Volume"],
            "dividend": raw["Dividends"], "split_ratio": raw["Stock Splits"],
        }, dtype=object)
        # close as traded: multiply by every split that happens after the row's date
        ratios = [Decimal(x) if Decimal(x) != 0 else Decimal(1) for x in df["split_ratio"]]
        later = Decimal(1)
        factor = [Decimal(1)] * len(df)
        for i in range(len(df) - 1, -1, -1):
            factor[i] = later
            later *= ratios[i]
        df["close_as_traded"] = [str((Decimal(c) * f).quantize(Decimal("0.0001"))) for c, f in zip(df["close"], factor)]
        m = manifest[manifest["file"].str.endswith(f"market/prices_{sym}.csv")]
        df["source_file"] = path.name
        df["source_sha256"] = m.iloc[0]["sha256"] if len(m) else ""
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PRICE_COLUMNS, dtype=object)


def cutoff_date(info: dict, prices: pd.DataFrame, reference: str, close_et: str) -> tuple[str, str]:
    """Latest completed trading day before collection (D12), from the reference symbol's calendar."""
    started = datetime.fromisoformat(info["started_new_york"])
    hh, mm = (int(x) for x in close_et.split(":"))
    session_done = (started.hour, started.minute) >= (hh, mm)
    today = started.date().isoformat()
    dates = sorted(prices.loc[prices["ticker"] == reference, "date"])
    eligible = [d for d in dates if d < today or (d == today and session_done)]
    note = f"collection started {info['started_new_york']}; today's session {'complete' if session_done else 'not complete'}"
    return (eligible[-1] if eligible else ""), note


def corporate_actions(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in prices.itertuples():
        if Decimal(r.split_ratio) != 0:
            rows.append({"ticker": r.ticker, "date": r.date, "action": "split", "value": r.split_ratio})
        if Decimal(r.dividend) != 0:
            rows.append({"ticker": r.ticker, "date": r.date, "action": "dividend", "value": r.dividend})
    return pd.DataFrame(rows, columns=["ticker", "date", "action", "value"], dtype=object)


def risk_free(coll: Path, uni: dict, cutoff: str) -> dict:
    """10-year yield on or before the cutoff: FRED DGS10, else the Treasury par yield file (M2-D8)."""
    series = uni["market"]["fred_series"]
    fred = coll / "market" / f"fred_{series}.csv"
    out = {"series": "", "source_file": "", "observation_date": "", "value_pct": "", "lag_days": ""}
    obs = []
    if fred.exists():
        df = pd.read_csv(fred, dtype=str, keep_default_na=False)
        date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
        for d, v in zip(df[date_col], df[series]):
            if v not in ("", ".") and d <= cutoff:
                obs.append((d, v))
        out.update(series=f"FRED {series}", source_file=fred.name)
    else:
        files = sorted((coll / "market").glob("treasury_par_yield_*.csv"))
        for f in files:
            df = pd.read_csv(f, dtype=str, keep_default_na=False)
            for d, v in zip(df["Date"], df["10 Yr"]):
                iso = datetime.strptime(d, "%m/%d/%Y").date().isoformat()
                if v and iso <= cutoff:
                    obs.append((iso, v))
        if files:
            out.update(series="US Treasury daily par yield curve, 10 Yr", source_file="|".join(f.name for f in files))
    if obs:
        d, v = max(obs)
        out.update(observation_date=d, value_pct=v,
                   lag_days=(date.fromisoformat(cutoff) - date.fromisoformat(d)).days)
    return out


def shares_outstanding(obs: pd.DataFrame, cutoff: str) -> dict:
    """Latest cover-page share count (dei:EntityCommonStockSharesOutstanding) filed on or before the cutoff (M2-D7)."""
    s = obs[(obs["taxonomy"] == "dei") & (obs["concept"] == "EntityCommonStockSharesOutstanding")
            & (obs["unit"] == "shares") & (obs["filed"] <= cutoff)]
    if s.empty:
        return {}
    s = s.sort_values(["period_end", "filed", "accn"], kind="mergesort")
    last_end = s.iloc[-1]["period_end"]
    same = s[(s["period_end"] == last_end) & (s["accn"] == s.iloc[-1]["accn"])]
    total = sum(_num(v) for v in same["value"])  # some registrants report one value per share class
    r = same.iloc[-1]
    return {"shares": total, "as_of": last_end, "accn": r["accn"], "form": r["form"], "filed": r["filed"],
            "classes": len(same)}


def yfinance_shares(manifest: pd.DataFrame, sym: str) -> str:
    m = manifest[(manifest["source"] == "prices") & (manifest["ticker"] == sym)]
    if m.empty:
        return ""
    hit = re.search(r"yfinance shares=([0-9.]+)", m.iloc[0]["note"] or "")
    return hit.group(1) if hit else ""


def price_checks(prices: pd.DataFrame, cutoff: str, reference: str, symbols: list[str]) -> list:
    out = []
    ref_dates = set(prices.loc[(prices["ticker"] == reference) & (prices["date"] <= cutoff), "date"])
    bad = []
    for sym in symbols:
        d = set(prices.loc[(prices["ticker"] == sym) & (prices["date"] <= cutoff), "date"])
        if not d:
            bad.append(f"{sym}: no prices")
            continue
        missing = sorted(x for x in ref_dates if x >= min(d) and x not in d)
        extra = sorted(d - ref_dates)
        if missing or extra:
            bad.append(f"{sym}: {len(missing)} missing, {len(extra)} extra trading days")
    out.append(("P1_trading_days_match_reference", not bad, "; ".join(bad) or f"all {len(symbols)} match {reference}"))
    problems = 0
    for r in prices.itertuples():
        try:
            o, h, l, c = (Decimal(x) for x in (r.open, r.high, r.low, r.close))
            if min(o, h, l, c) <= 0 or h < l or not (l - Decimal("0.01") <= c <= h + Decimal("0.01")):
                problems += 1
        except Exception:  # noqa: BLE001 - any unparsable price is a problem
            problems += 1
    out.append(("P2_prices_positive_and_consistent", problems == 0, f"{problems} rows with missing or inconsistent OHLC"))
    has_cut = [s for s in symbols if not ((prices["ticker"] == s) & (prices["date"] == cutoff)).any()]
    out.append(("P4a_every_symbol_has_cutoff_bar", not has_cut, f"missing cutoff {cutoff}: {has_cut}" if has_cut else f"cutoff {cutoff}"))
    return out


def split_crosscheck(actions: pd.DataFrame, facts: pd.DataFrame, tolerance=Decimal("0.15")) -> tuple[bool, str, list]:
    """Each yfinance split of a company must show up as a share-count jump of the same size in SEC data,
    comparing first-filed diluted shares of the last quarter before and first quarter after the split."""
    details, ok = [], True
    for a in actions[actions["action"] == "split"].itertuples():
        f = facts[(facts["ticker"] == a.ticker) & (facts["line_item"] == "shares_diluted")
                  & (facts["value_basis"] == "reported_quarter")]
        if f.empty:
            details.append(f"{a.ticker} {a.date} x{a.value}: no SEC share data (benchmark or ETF), not checked")
            continue
        before = f[f["period_end"] < a.date].sort_values("period_end")
        after = f[f["period_start"] > a.date].sort_values("period_end")
        if before.empty or after.empty:
            ok = False
            details.append(f"{a.ticker} {a.date}: no quarter on one side of the split")
            continue
        b, n = before.iloc[-1], after.iloc[0]
        ratio = _num(n["original_value"]) / _num(b["original_value"])
        within = abs(Decimal(ratio) / Decimal(a.value) - 1) <= tolerance
        ok &= bool(within)
        details.append(f"{a.ticker} {a.date} x{a.value}: SEC first-filed shares {b['fiscal_period']} FY{b['fiscal_year']} "
                       f"-> {n['fiscal_period']} FY{n['fiscal_year']} ratio {Decimal(ratio):.3f} {'OK' if within else 'MISMATCH'}")
    return ok, "; ".join(details), details
