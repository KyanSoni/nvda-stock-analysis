"""Version 2, V2.4: the daily price panel and the questions V2 asks of it.

Yahoo's 'Close' is adjusted for splits (not dividends) back from today; 'Adj Close' for splits and dividends (total return).
  close_as_traded(t, d)  the price actually traded on d = Close(d) x every split after d   (for the P/E, V2-D13)
  adj(t)                 adjusted close, forward-filled within the series                   (for returns)
A ticker's Yahoo history is used for a member only if the ticker still belongs to that company or nobody (V2-D14, I-81):
when SEC's ticker file says the ticker now belongs to a different filer whose name does not match the member's, Yahoo's
history is that other company's and is not used.
"""
from __future__ import annotations

import bisect
from pathlib import Path

import pandas as pd

import v2_universe as u

PANEL_COLUMNS = ["ticker", "date", "close", "adj_close", "split"]


def read_raw(path: Path, ticker: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    return pd.DataFrame({"ticker": ticker, "date": raw["Date"].astype(str).str[:10], "close": raw["Close"].astype(float),
                         "adj_close": raw["Adj Close"].astype(float), "split": raw["Stock Splits"].astype(float)})


class Prices:
    def __init__(self, panel: pd.DataFrame):
        self.by = {}
        for t, g in panel.sort_values(["ticker", "date"]).groupby("ticker", sort=False):
            g = g.drop_duplicates("date", keep="last")
            self.by[t] = {"dates": g["date"].tolist(), "close": g["close"].tolist(), "adj": g["adj_close"].tolist(),
                          "splits": [(d, r) for d, r in zip(g["date"], g["split"]) if r and r > 0 and r != 1]}
        spy = self.by.get("SPY")
        self.calendar = spy["dates"] if spy else sorted({d for v in self.by.values() for d in v["dates"]})

    def has(self, t: str) -> bool:
        return t in self.by

    def splits(self, t: str) -> list:
        return self.by[t]["splits"] if t in self.by else []

    def trading_day_on_or_after(self, d: str) -> str | None:
        i = bisect.bisect_left(self.calendar, d)
        return self.calendar[i] if i < len(self.calendar) else None

    def trading_day_on_or_before(self, d: str) -> str | None:
        i = bisect.bisect_right(self.calendar, d)
        return self.calendar[i - 1] if i else None

    def _idx(self, t: str, d: str, max_stale: int = 5):
        """Index of the last row on or before d, if it is within max_stale rows of d's position in the calendar."""
        s = self.by.get(t)
        if not s:
            return None
        i = bisect.bisect_right(s["dates"], d) - 1
        if i < 0:
            return None
        gap = bisect.bisect_right(self.calendar, d) - bisect.bisect_right(self.calendar, s["dates"][i])
        return i if gap <= max_stale else None

    def close_as_traded(self, t: str, d: str):
        i = self._idx(t, d)
        if i is None:
            return None
        f = 1.0
        for sd, r in self.by[t]["splits"]:
            if sd > d:
                f *= r
        return self.by[t]["close"][i] * f

    def adj_series(self, t: str, start: str, end: str) -> pd.Series:
        """Adjusted close on every calendar trading day in [start, end], forward-filled; NaN before the first price.
        After the last Yahoo price the last value is held (the position becomes cash at that price, V2-D16)."""
        days = self.calendar[bisect.bisect_left(self.calendar, start): bisect.bisect_right(self.calendar, end)]
        s = self.by.get(t)
        if not s:
            return pd.Series(float("nan"), index=days)
        ser = pd.Series(s["adj"], index=s["dates"])
        return ser.reindex(sorted(set(days) | set(ser.index))).ffill().reindex(days)

    def last_date(self, t: str) -> str:
        return self.by[t]["dates"][-1] if t in self.by else ""


def owner_ok(ticker: str, cik: str, security: str, by_ticker: dict, cik_names: dict) -> tuple[bool, str]:
    """Whether Yahoo's history under this ticker can be the member's (see module notes)."""
    owner = by_ticker.get(ticker.upper().replace(".", "-"))
    if owner is None:
        return True, "ticker not in SEC's current file"
    if owner == cik:
        return True, "ticker still belongs to this filer"
    if u.names_agree(security, cik_names.get(owner, set())):
        return True, "ticker belongs to a successor with the same name"
    return False, f"ticker now belongs to CIK {owner} ({sorted(cik_names.get(owner, {'?'}))[0][:30]})"
