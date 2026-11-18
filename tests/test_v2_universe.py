"""Version 2, V2.1 offline tests: the HTML table parser (rowspan, colspan, footnotes), the constituents and changes
tables, membership rebuilt at past dates, CIK mapping with its basis, and the checks. Synthetic pages; no network."""
import json

import pandas as pd
import pytest

import v2_universe as u

CFG = {"universe": {"expected_size": [3, 6], "cik_coverage_error_below": 0.5, "cik_coverage_target": 0.95,
                    "constituents_table_id": "constituents", "changes_table_id": "changes"},
       "sectors": {"gics": ["Information Technology", "Financials", "Energy"], "excluded": ["Financials"]},
       "backtest": {"rebalance_month_day": "04-01", "first_year": 2020, "last_year": 2023}}

PAGE = """<html><body>
<table class="wikitable sortable" id="constituents"><tbody>
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th></tr>
<tr><td><a>NVDA</a></td><td>Nvidia</td><td>Information Technology</td><td>Semiconductors</td><td>Santa Clara</td><td>2001-11-30</td><td>0001045810</td><td>1993</td></tr>
<tr><td>BRK.B</td><td>Berkshire Hathaway<sup class="reference">[3]</sup></td><td>Financials</td><td>Multi-Sector Holdings</td><td>Omaha</td><td>2010-02-16</td><td>0001067983</td><td>1839</td></tr>
<tr><td>NEWCO</td><td>NewCo Inc.</td><td>Energy</td><td>Oil</td><td>Houston</td><td>2022-06-21</td><td>0000000111</td><td>2000</td></tr>
<tr><td>AAA</td><td>Alpha Corp</td><td>Information Technology</td><td>Software</td><td>X</td><td>2015-01-01</td><td>0000000222</td><td>1990</td></tr>
</tbody></table>
<table class="wikitable sortable" id="changes"><tbody>
<tr><th rowspan="2">Effective Date</th><th colspan="2">Added</th><th colspan="2">Removed</th><th rowspan="2">Reason</th></tr>
<tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th></tr>
<tr><td rowspan="2">June 21, 2022</td><td>NEWCO</td><td>NewCo Inc.</td><td>OLDCO</td><td>OldCo Corporation</td><td>Market cap change.<sup>[9]</sup></td></tr>
<tr><td></td><td></td><td>GONE</td><td>Gone Holdings, Inc.</td><td>Acquired.</td></tr>
<tr><td>March 1, 2021</td><td>BRK.B</td><td>Berkshire Hathaway</td><td>ZZZ</td><td>Zed Co</td><td>Replaced.</td></tr>
</tbody></table></body></html>"""
TICKERS = json.dumps({"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
                      "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
                      "2": {"cik_str": 333, "ticker": "ZZZ", "title": "ZED CO"},
                      "3": {"cik_str": 999, "ticker": "GONE", "title": "SOMEBODY ELSE INC"}})       # ticker reused by another company
NAMES = ("OLDCO CORP:0000000444:\nGONE HOLDINGS INC:0000000555:\nGONE HOLDINGS INC.:0000000556:\nNVIDIA CORP:0001045810:\n"
         "ZED CO:0000000333:\nSOMEBODY ELSE INC:0000000999:\n")


@pytest.fixture
def res(tmp_path):
    (tmp_path / "sp500_wikipedia.html").write_text(PAGE, encoding="utf-8")
    (tmp_path / "company_tickers.json").write_text(TICKERS, encoding="utf-8")
    (tmp_path / "cik-lookup-data.txt").write_text(NAMES, encoding="latin-1")
    return u.build(tmp_path, CFG, "2026-11-14")


def test_parser_expands_rowspan_colspan_and_drops_footnotes():
    t = u.parse_tables(PAGE)
    assert t["constituents"][2][1] == "Berkshire Hathaway"                     # <sup>[3]</sup> dropped
    assert t["changes"][0][:6] == ["Effective Date", "Added", "Added", "Removed", "Removed", "Reason"]
    assert t["changes"][3][0] == "June 21, 2022" and t["changes"][3][3] == "GONE"   # date carried down by rowspan


def test_constituents_and_changes(res):
    cur, ch = res["current"], res["changes"]
    assert list(cur["ticker"]) == ["NVDA", "BRK.B", "NEWCO", "AAA"] and cur.loc[0, "cik"] == "0001045810"
    assert cur.loc[0, "date_added"] == "2001-11-30"
    assert len(ch) == 3 and set(ch["date"]) == {"2022-06-21", "2021-03-01"}
    assert ch[ch["removed_ticker"] == "GONE"].iloc[0]["added_ticker"] == ""


def test_membership_undoes_later_changes(res):
    m = res["membership"]
    at = lambda d: set(m[m["date"] == d]["ticker"])  # noqa: E731
    assert at("2026-11-14") == {"NVDA", "BRK.B", "NEWCO", "AAA"}
    assert at("2022-04-01") == {"NVDA", "BRK.B", "OLDCO", "GONE", "AAA"}          # before the June 2022 changes
    assert at("2020-04-01") == {"NVDA", "ZZZ", "OLDCO", "GONE", "AAA"}            # before BRK.B replaced ZZZ
    assert res["dates"] == ["2020-04-01", "2021-04-01", "2022-04-01", "2023-04-01", "2024-04-01", "2026-11-14"]


def test_cik_basis_and_ambiguous_names(res):
    c = res["ciks"].set_index("ticker")
    assert c.loc["NVDA", "cik_basis"] == "wikipedia" and c.loc["ZZZ", "cik_basis"] == "sec_ticker" and c.loc["ZZZ", "cik"] == "0000000333"
    assert c.loc["OLDCO", "cik_basis"] == "sec_name" and c.loc["OLDCO", "cik"] == "0000000444"
    assert c.loc["GONE", "cik_basis"] == "unmapped" and c.loc["GONE", "cik"] == ""   # ticker reused + two CIKs share the name: never guessed


def test_name_normalisation():
    assert u.norm_name("Gone Holdings, Inc.") == u.norm_name("GONE HOLDINGS INC") == "GONE"
    assert u.norm_name("AT&T Inc.") == "AT AND T"


def test_sector_exclusion_and_coverage(res):
    m = res["membership"]
    assert m[m["ticker"] == "BRK.B"]["excluded_sector"].all() and not m[m["ticker"] == "NVDA"]["excluded_sector"].any()
    cov = res["coverage"].set_index("date")
    assert cov.loc["2022-04-01", "members"] == 5 and cov.loc["2022-04-01", "with_cik"] == 4


def test_checks(res):
    out = {c: (ok, lvl) for c, ok, _, lvl in u.checks(res, CFG)}
    assert out["U1_current_constituents"][0] and out["U2_sector_and_cik_present"][0] and out["U3_cik_agrees_with_sec"][0]
    assert out["U8_nvidia_member_every_date"][0]
    assert not out["U4_changes_parsed"][0]                       # only 3 synthetic changes: below the 100 needed for real data


HISTORY = """<html><body><h2>2023</h2>
<table class="wikitable"><tbody>
<tr><th>Date</th><th>Added ticker</th><th>Added security</th><th>Removed ticker</th><th>Removed security</th><th>Reason</th></tr>
<tr><td>May 2, 2023</td><td>NEWCO</td><td>NewCo Inc.</td><td>OLDCO</td><td>OldCo Corporation</td><td>Index rebalance</td></tr>
</tbody></table>
<table class="wikitable"><tbody>
<tr><th>Date</th><th>Added ticker</th><th>Added security</th><th>Removed ticker</th><th>Removed security</th><th>Reason</th></tr>
<tr><td>January 3, 2021</td><td>BRK.B</td><td>Berkshire Hathaway</td><td>ZZZ</td><td>Zed Co</td><td>Replaced.</td></tr>
</tbody></table>
<table class="nowraplinks navbox-inner"><tr><th>Date added removed</th></tr><tr><td>March 1, 2020</td></tr></table>
</body></html>"""


def test_history_page_split_tables_single_header_and_navbox_ignored(tmp_path):
    main = PAGE[:PAGE.index('<table class="wikitable sortable" id="changes">')] + "</body></html>"   # main page without history
    (tmp_path / "sp500_wikipedia.html").write_text(main, encoding="utf-8")
    (tmp_path / "sp500_history_wikipedia.html").write_text(HISTORY, encoding="utf-8")
    (tmp_path / "company_tickers.json").write_text(TICKERS, encoding="utf-8")
    (tmp_path / "cik-lookup-data.txt").write_text(NAMES, encoding="latin-1")
    r = u.build(tmp_path, CFG, "2026-11-14")
    assert len(r["changes"]) == 2 and len(r["changes_tables"]) == 2 and all(k.startswith("history:") for k in r["changes_tables"])
    m = r["membership"]
    assert set(m[m["date"] == "2022-04-01"]["ticker"]) == {"NVDA", "BRK.B", "OLDCO", "AAA"}
    assert set(m[m["date"] == "2020-04-01"]["ticker"]) == {"NVDA", "ZZZ", "OLDCO", "AAA"}


def test_names_agree_rejects_reused_tickers():
    assert u.names_agree("VF Corporation", {"V F"}) and u.names_agree("Nov", {"NOV"}) and u.names_agree("H&R Block", {"H AND R BLOCK"})
    assert not u.names_agree("Anadarko Petroleum", {"ARKO PETROLEUM"}) and not u.names_agree("SunTrust Banks", {"NUBIA BRAND INTERNATIONAL"})


def _cur(rows):
    return pd.DataFrame(rows, columns=["ticker", "security", "sector", "sub_industry", "date_added", "cik"])


def test_ticker_changes_linked_on_evidence_only():
    cur = _cur([["CPAY", "Corpay", "Financials", "x", "2018-06-20", "0000001175"],      # was FLT: same date added
                ["UA", "Under Armour (Class C)", "Consumer Discretionary", "x", "2016-12-07", ""],    # renamed later: name rule
                ["DAY", "Dayforce", "Industrials", "x", "2010-01-01", ""],                   # was CDAY: only SEC links the names
                ["XYZ", "Unrelated", "Energy", "x", "2010-01-01", ""]])
    ch = pd.DataFrame([["2021-09-20", "CDAY", "Ceridian", "UNM", "Unum", ""], ["2018-06-20", "FLT", "FleetCor Technologies", "TWX", "Time Warner", ""],
                       ["2016-04-08", "UA.C", "Under Armour (Class C)", "", "", ""], ["2015-01-01", "NOPE", "Nobody", "", "", ""]],
                      columns=["date", "added_ticker", "added_security", "removed_ticker", "removed_security", "reason"])
    by_name = {"CERIDIAN HCM": {"0001725057"}, "DAYFORCE": {"0001725057", "0001496678"}, "DAYFORCE CORP": {"0001496678"}}
    m, warn, ren = u.membership(cur, ch, ["2014-04-01", "2019-04-01", "2026-11-17"], by_name)
    r = ren.set_index("old_ticker")
    assert r.loc["FLT", "ticker"] == "CPAY" and r.loc["FLT", "basis"] == "date_added"
    assert r.loc["UA.C", "ticker"] == "UA" and r.loc["UA.C", "basis"] == "same_name"
    assert r.loc["CDAY", "ticker"] == "DAY" and r.loc["CDAY", "basis"] == "shared_cik" and r.loc["CDAY", "cik"] == "0001725057"
    assert warn == ["2015-01-01: added NOPE was not a member when undoing"]                  # no evidence: reported, not linked
    assert set(m[m["date"] == "2019-04-01"]["ticker"]) == {"CPAY", "UA", "UNM", "XYZ"}      # DAY not yet a member in 2019
    assert set(m[m["date"] == "2014-04-01"]["ticker"]) == {"UNM", "TWX", "XYZ"}


def test_changes_header_must_be_recognised():
    with pytest.raises(ValueError):
        u.changes([["Date", "Something"], ["x", "y"]])
