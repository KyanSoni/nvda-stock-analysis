"""Builds a small synthetic Step 2 collection on disk. Every value is invented; nothing here is real data.

Company AAA (December year-end) has a predecessor registrant; company BBB (January year-end) has one.
Expected results are worked out by hand in test_step2.py.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

A, A_OLD, B = "0000000001", "0000000002", "0000000003"


def _f(start, end, val, accn, form, filed, fy=2017, fp="FY"):
    d = {"end": end, "val": val, "accn": accn, "fy": fy, "fp": fp, "form": form, "filed": filed}
    if start:
        d["start"] = start
    return d


def _facts(cik, name, concepts: dict, dei: dict | None = None) -> dict:
    facts = {"us-gaap": {c: {"label": c, "description": c, "units": u} for c, u in concepts.items()}}
    if dei:
        facts["dei"] = {c: {"label": c, "description": c, "units": u} for c, u in dei.items()}
    return {"cik": int(cik), "entityName": name, "facts": facts}


def companyfacts() -> dict:
    K17, Q1, Q2, Q3 = "0000000001-18-000010", "0000000001-17-000001", "0000000001-17-000002", "0000000001-17-000003"
    OLD = "0000000002-17-000005"
    aaa = _facts(A, "AAA CORP", {
        "Revenues": {"USD": [
            _f("2016-01-01", "2016-12-31", 900_000_000, OLD, "10-K", "2017-02-20", 2016),   # predecessor, first filed
            _f("2016-01-01", "2016-12-31", 905_000_000, K17, "10-K", "2018-02-20"),          # successor comparative, restated
            _f("2017-01-01", "2017-03-31", 200_000_000, Q1, "10-Q", "2017-05-01", fp="Q1"),
            _f("2017-01-01", "2017-06-30", 450_000_000, Q2, "10-Q", "2017-08-01", fp="Q2"),
            _f("2017-01-01", "2017-09-30", 720_000_000, Q3, "10-Q", "2017-11-01", fp="Q3"),
            _f("2017-01-01", "2017-12-31", 1_000_000_000, K17, "10-K", "2018-02-20"),
        ]},
        "NetCashProvidedByUsedInOperatingActivities": {"USD": [
            _f("2017-01-01", "2017-03-31", 50_000_000, Q1, "10-Q", "2017-05-01", fp="Q1"),
            _f("2017-01-01", "2017-06-30", 120_000_000, Q2, "10-Q", "2017-08-01", fp="Q2"),
            _f("2017-01-01", "2017-09-30", 200_000_000, Q3, "10-Q", "2017-11-01", fp="Q3"),
            _f("2017-01-01", "2017-12-31", 300_000_000, K17, "10-K", "2018-02-20"),
        ]},
        # equity only tagged including NCI; NCI is non-zero at 2016 year end (fallback blocked), absent at 2017
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": {"USD": [
            _f(None, "2016-12-31", 55_000_000, K17, "10-K", "2018-02-20"),
            _f(None, "2017-12-31", 60_000_000, K17, "10-K", "2018-02-20"),
        ]},
        "MinorityInterest": {"USD": [_f(None, "2016-12-31", 5_000_000, K17, "10-K", "2018-02-20")]},
        "LiabilitiesAndStockholdersEquity": {"USD": [
            _f(None, "2016-12-31", 95_000_000, K17, "10-K", "2018-02-20"),
            _f(None, "2017-12-31", 100_000_000, K17, "10-K", "2018-02-20"),
        ]},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"shares": [
            _f("2017-01-01", "2017-03-31", 100_000_000, Q1, "10-Q", "2017-05-01", fp="Q1"),
            _f("2017-04-01", "2017-06-30", 101_000_000, Q2, "10-Q", "2017-08-01", fp="Q2"),
            _f("2017-07-01", "2017-09-30", 404_000_000, Q3, "10-Q", "2017-11-01", fp="Q3"),
        ]},
    }, dei={"EntityCommonStockSharesOutstanding": {"shares": [
        _f(None, "2018-01-31", 300_000_000, K17, "10-K", "2018-02-20"),
        _f(None, "2018-01-31", 104_000_000, K17, "10-K", "2018-02-20"),   # second share class, same filing
    ]}})
    aaa_old = _facts(A_OLD, "AAA HOLDINGS LTD", {"Revenues": {"USD": [
        _f("2016-01-01", "2016-12-31", 900_000_000, OLD, "10-K", "2017-02-20", 2016)]}})
    K = "0000000003-18-000002"
    bbb = _facts(B, "BBB INC", {
        "Revenues": {"USD": [_f("2017-01-30", "2018-01-28", 500_000_000, K, "10-K", "2018-03-01", 2018)]},
        "Assets": {"USD": [_f(None, "2018-01-28", 800_000_000, K, "10-K", "2018-03-01", 2018)]},
    }, dei={"EntityCommonStockSharesOutstanding": {"shares": [_f(None, "2018-02-20", 50_000_000, K, "10-K", "2018-03-01", 2018)]}})
    return {A: aaa, A_OLD: aaa_old, B: bbb}


def submissions() -> dict:
    def sub(cik, name, fye, tickers, tenk, former=()):
        return {"cik": cik, "name": name, "tickers": tickers, "fiscalYearEnd": fye,
                "formerNames": [{"name": n} for n in former],
                "filings": {"recent": {"form": ["10-K"] * len(tenk), "filingDate": ["x"] * len(tenk),
                                       "reportDate": tenk, "accessionNumber": ["x"] * len(tenk),
                                       "primaryDocument": ["x"] * len(tenk)}}}
    return {A: sub(A, "AAA CORP", "1231", ["AAA"], ["2017-12-31"]),
            A_OLD: sub(A_OLD, "AAA HOLDINGS LTD", "1231", [], ["2016-12-31"]),
            B: sub(B, "BBB INC", "0128", ["BBB"], ["2018-01-28"])}


def universe(collections_dir: str) -> dict:
    return {
        "companies": {
            "AAA": {"role": "peer", "cik": A, "fy_end_month": 12, "derived": ["total_liabilities"],
                    "predecessors": [{"cik": A_OLD, "expected_name_contains": "AAA"}],
                    "extra_candidates": {"stockholders_equity": [
                        {"concept": "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                         "guard_zero_or_absent": ["MinorityInterest"]}]}},
            "BBB": {"role": "target", "cik": B, "fy_end_month": 1},
        },
        "benchmarks": ["SPY"],
        "support_items": {
            "cost_of_revenue": {"statement": "IS", "period_type": "duration", "unit": "USD",
                                "candidates": ["CostOfRevenue"], "derive_q4": True},
            "liabilities_and_equity": {"statement": "BS", "period_type": "instant", "unit": "USD",
                                       "candidates": ["LiabilitiesAndStockholdersEquity"], "derive_q4": False},
            "total_equity": {"statement": "BS", "period_type": "instant", "unit": "USD", "derive_q4": False,
                             "candidates": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                                            {"concept": "StockholdersEquity", "guard_zero_or_absent": ["MinorityInterest"]}]},
        },
        "derivations": {"gross_profit": {"minuend": "revenue", "subtrahend": "cost_of_revenue"},
                        "total_liabilities": {"minuend": "liabilities_and_equity", "subtrahend": "total_equity"}},
        "market": {"fred_series": "DGS10", "cutoff_rule": "test rule", "market_close_et": "16:30",
                   "risk_free_max_lag_days": 5},
        "paths": {"collections_dir": collections_dir, "step2_out": "out"},
    }


PRICE_HEADER = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
DATES = ["2018-02-26", "2018-02-27", "2018-02-28", "2018-03-01", "2018-03-02"]


def prices() -> dict:
    def rows(base, split_on=None, div_on=None):
        out = []
        for i, d in enumerate(DATES):
            c = base + i
            out.append([f"{d} 00:00:00-05:00", c, c + 1, c - 1, c, c - 0.5, 1000,
                        0.5 if d == div_on else 0.0, 4.0 if d == split_on else 0.0])
        return out
    # BBB has the split: it has no quarterly SEC share data, so P3 reports it as not checkable (split logic is unit-tested)
    return {"SPY": rows(100), "AAA": rows(10, div_on="2018-03-01"), "BBB": rows(50, split_on="2018-02-28")}


def build(root: Path, started_new_york="2018-03-02T18:00:00-05:00", stamp="20180302T230000Z",
          with_rates=True) -> tuple[Path, dict]:
    uni = universe("collections")
    coll = root / "collections" / stamp
    (coll / "sec").mkdir(parents=True)
    (coll / "market").mkdir()
    rows = []

    def put(rel, data: bytes, source, ticker="", cik=""):
        (coll / rel).write_bytes(data)
        rows.append({"retrieved_at_utc": "2018-03-02T23:00:00+00:00", "source": source, "ticker": ticker, "cik": cik,
                     "role": "", "url": "synthetic", "http_status": 200, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest(), "file": f"collections/{stamp}/{rel}",
                     "required": "true", "ok": "true", "note": ""})

    tickers = {"0": {"cik_str": int(A), "ticker": "AAA", "title": "AAA CORP"},
               "1": {"cik_str": int(B), "ticker": "BBB", "title": "BBB INC"}}
    put("sec/company_tickers.json", json.dumps(tickers).encode(), "ticker_file")
    for cik, data in submissions().items():
        put(f"sec/submissions_CIK{cik}.json", json.dumps(data).encode(), "submissions", cik=cik)
    for cik, data in companyfacts().items():
        put(f"sec/companyfacts_CIK{cik}.json", json.dumps(data).encode(), "companyfacts", cik=cik)
    for sym, prow in prices().items():
        lines = [",".join(PRICE_HEADER)] + [",".join(str(x) for x in r) for r in prow]
        put(f"market/prices_{sym}.csv", ("\n".join(lines) + "\n").encode(), "prices", ticker=sym)
        rows[-1]["note"] = f"5 rows; yfinance shares={404000000 if sym == 'AAA' else ''}"
    if with_rates:
        put("market/fred_DGS10.csv", b"observation_date,DGS10\n2018-02-28,2.86\n2018-03-01,2.81\n2018-03-02,.\n",
            "fred", ticker="DGS10")
    fields = list(rows[0])
    with open(coll / "collection_manifest.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    info = {"collection_id": stamp, "started_utc": "2018-03-02T23:00:00+00:00", "started_new_york": started_new_york,
            "packages": {"yfinance": "test"}}
    (coll / "collection_info.json").write_text(json.dumps(info), encoding="utf-8")
    return coll, copy.deepcopy(uni)
