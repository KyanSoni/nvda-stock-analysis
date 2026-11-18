"""Version 2, V2.2 offline tests: the annual-report window, choosing the filer at each date (I-78, I-79), older submissions
pages, name candidates with aliases, and sectors from SIC codes. Synthetic EDGAR records; no network."""
import pandas as pd

import v2_sec as s
import v2_universe as u

CFG = {"sec": {"annual_forms": ["10-K", "10-K405", "10-KT", "20-F", "40-F"], "ten_k_window_months": 18, "name_aliases": {"CR Bard": "BARD C R"},
               "sic_sectors": [[6500, 6553, "Real Estate"], [6000, 6799, "Financials"], [3570, 3579, "Information Technology"],
                               [3660, 3699, "Information Technology"], [2830, 2836, "Health Care"]]},
       "sectors": {"excluded": ["Financials", "Real Estate"]}}


def filings(cik, rows):
    return pd.DataFrame([{"cik": cik, "form": f, "filing_date": d, "report_date": "", "accn": f"{cik}-{i}"} for i, (f, d) in enumerate(rows)],
                        columns=s.FILING_COLUMNS)


def meta(cik, name, sic="3674", tickers=(), former=()):
    """former: (name, from, to) as EDGAR's formerNames give them."""
    hist = [(f, t, s.edgar_norm(n)) for n, f, t in former]
    since = max((t for _, t, _ in hist), default="")
    return {"cik": cik, "name": name, "sic": sic, "sic_description": "", "tickers": list(tickers), "former_names": [h[2] for h in hist],
            "name_history": hist + [(since, "9999-12-31", s.edgar_norm(name))]}


SUBS = {
    "0000000001": (meta("0000000001", "ALCOA CORP", "3334", ["AA"]), filings("0000000001", [("10-K", "2017-03-01"), ("10-Q", "2016-11-01")])),
    "0000000002": (meta("0000000002", "HOWMET AEROSPACE INC", "3334", ["HWM"], [("ALCOA INC", "1994-01-01", "2016-11-01"), ("ARCONIC INC", "2016-11-01", "2020-04-01")]),
                   filings("0000000002", [("10-K", "2016-02-19"), ("10-K", "2015-02-19")])),
    "0000000003": (meta("0000000003", "NVIDIA CORP", "3674", ["NVDA"]), filings("0000000003", [("10-K", "2016-03-17"), ("10-K", "2017-03-01")])),
    "0000000004": (meta("0000000004", "AETNA INC /PA/", "6324"), filings("0000000004", [("10-K", "2016-02-20")])),
    "0000000005": (meta("0000000005", "AETNA INC", "6324"), filings("0000000005", [("10-K", "2016-02-25")])),
    "0000000006": (meta("0000000006", "FOO HOLDINGS", "3674"), filings("0000000006", [("10-K/A", "2016-01-10"), ("8-K", "2016-03-01")])),
}
NAMES = {"0000000001": {"ALCOA"}, "0000000002": {"ALCOA", "ARCONIC", "HOWMET AEROSPACE"}, "0000000003": {"NVIDIA"},
         "0000000004": {"AETNA PA"}, "0000000005": {"AETNA"}, "0000000006": {"FOO"}}


def mem(rows):
    return pd.DataFrame(rows, columns=["date", "ticker", "security", "cik", "cik_basis"])


def test_months_before_and_window():
    assert s.months_before("2016-04-01", 18) == "2014-10-01"
    assert s.months_before("2016-03-31", 1) == "2016-02-28"          # day clipped to 28
    f = SUBS["0000000003"][1]
    assert s.annual_in_window(f, "2016-04-01", CFG)                  # 10-K filed 2016-03-17
    assert not s.annual_in_window(f, "2016-03-17", CFG)              # filed on the date itself does not count
    assert not s.annual_in_window(SUBS["0000000006"][1], "2016-04-01", CFG)   # an amendment is not an annual report here


def test_successor_cik_is_replaced_by_the_filer_of_the_time():
    m = mem([["2016-04-01", "AA", "Alcoa", "0000000001", "sec_ticker"], ["2017-04-01", "AA", "Alcoa", "0000000001", "sec_ticker"]])
    r = s.resolve(m, SUBS, {"AA": ["0000000001", "0000000002"]}, NAMES, CFG)
    assert r.iloc[0]["cik_pit"] == "0000000002" and r.iloc[0]["pit_basis"] == "edgar_name_annual_report"      # I-78
    assert r.iloc[1]["cik_pit"] == "0000000001" and r.iloc[1]["pit_basis"] == "v21_cik_annual_report"


def test_unmapped_company_found_by_name_and_ties_left_alone():
    assert s.edgar_norm("AETNA INC /PA/") == "AETNA" and s.edgar_norm("RAYTHEON CO/") == "RAYTHEON"
    m = mem([["2016-04-01", "AET", "Aetna", "", "unmapped"]])
    subs = dict(SUBS)
    subs["0000000004"] = (meta("0000000004", "AETNA SERVICES INC", "6324"), SUBS["0000000004"][1])
    r = s.resolve(m, subs, {"AET": ["0000000005", "0000000004"]}, NAMES, CFG)
    assert r.iloc[0]["cik_pit"] == "0000000005" and r.iloc[0]["n_qualifying"] == 1       # 'Aetna' is short: exact names only
    r = s.resolve(m, SUBS, {"AET": ["0000000005", "0000000004"]}, NAMES, CFG)             # 'AETNA INC' and 'AETNA INC /PA/' both exact
    assert r.iloc[0]["pit_basis"] == "ambiguous" and r.iloc[0]["cik_pit"] == ""        # never guessed


def test_no_candidate_keeps_v21_cik_with_a_label():
    m = mem([["2016-04-01", "FOO", "Foo", "0000000006", "sec_name"], ["2016-04-01", "BAR", "Bar", "", "unmapped"]])
    r = s.resolve(m, SUBS, {}, NAMES, CFG)
    assert r.iloc[0]["pit_basis"] == "no_annual_report_in_window" and r.iloc[0]["cik_pit"] == "0000000006"
    assert r.iloc[1]["pit_basis"] == "unresolved" and r.iloc[1]["cik_pit"] == ""


def test_older_pages_only_when_recent_is_short():
    sub = {"filings": {"recent": {"filingDate": ["2020-01-01", "2019-01-01"]},
                       "files": [{"name": "CIK1-submissions-001.json", "filingFrom": "2010-01-01", "filingTo": "2018-12-31"},
                                 {"name": "CIK1-submissions-002.json", "filingFrom": "2001-01-01", "filingTo": "2009-12-31"}]}}
    assert s.needs_older_pages(sub, "2014-10-01") == ["CIK1-submissions-001.json"]
    sub["filings"]["recent"]["filingDate"].append("2013-01-01")
    assert s.needs_older_pages(sub, "2014-10-01") == []


def test_name_candidates_exact_first_and_alias():
    by_name = {"BARD C R": {"0000000009"}, "BARD C R NJ": {"0000000008"}, "AETNA": {"0000000005"}, "AETNA PA": {"0000000004"},
               "AETNA LIFE INSURANCE": {"0000000007"}}
    names = {"0000000009": {"BARD C R"}, "0000000008": {"BARD C R NJ"}, "0000000005": {"AETNA"}, "0000000004": {"AETNA PA"},
             "0000000007": {"AETNA LIFE INSURANCE"}}
    keys = sorted(by_name)
    assert s.name_candidates("Aetna", by_name, keys, names, {}, 2) == ["0000000005", "0000000004"]
    assert s.name_candidates("CR Bard", by_name, keys, names, CFG["sec"]["name_aliases"], 5) == ["0000000009", "0000000008"]


def test_sic_sectors_and_wikipedia_first():
    t = CFG["sec"]["sic_sectors"]
    assert s.sic_sector("6798", t) == "Financials" and s.sic_sector("6512", t) == "Real Estate"   # first matching range wins
    assert s.sic_sector("3674", t) == "Information Technology" and s.sic_sector("", t) == "" and s.sic_sector("9999", t) == ""
    res = pd.DataFrame([{"date": "2016-04-01", "ticker": "NVDA", "cik_pit": "0000000003", "cik_v21": "0000000003"},
                        {"date": "2016-04-01", "ticker": "AET", "cik_pit": "0000000005", "cik_v21": ""}])
    cur = pd.DataFrame({"ticker": ["NVDA"], "cik": ["0000000003"], "sector": ["Information Technology"]})
    out = s.sectors(res, cur, SUBS, CFG)
    assert out["sector_basis"].tolist() == ["wikipedia_gics", "sic 6324"]
    assert out["excluded_sector"].tolist() == [False, True]


def test_filer_with_no_filings_is_handled():
    empty = s.filings_from({}, "0000000010")
    assert len(empty) == 0 and not s.annual_in_window(empty, "2016-04-01", CFG)
    odd = s.filings_from({"accessionNumber": ["a"], "filingDate": [None], "form": ["10-K"]}, "0000000010")
    assert not s.annual_in_window(odd, "2016-04-01", CFG)


EXTRA = {
    # FOX-style: a new spin-off that existed (Form 10 filed) but had no 10-K yet; an unrelated 'FOX ...' filer reports
    "0000000020": (meta("0000000020", "FOX CORP"), filings("0000000020", [("10-12B", "2018-10-01"), ("10-K", "2019-08-01")])),
    "0000000021": (meta("0000000021", "FOX FACTORY HOLDING CORP"), filings("0000000021", [("10-K", "2019-02-20")])),
    # JCI-style: the V2.1 CIK reported in 2016, but as Tyco; Johnson Controls Inc was the member
    "0000000030": (meta("0000000030", "Johnson Controls International plc", former=[("TYCO INTERNATIONAL PLC", "2014-01-01", "2016-09-02")]),
                   filings("0000000030", [("10-K", "2015-11-13")])),
    "0000000031": (meta("0000000031", "JOHNSON CONTROLS INC"), filings("0000000031", [("10-K", "2015-11-18")])),
    # Meta-style: renamed, no other filer -> kept
    "0000000040": (meta("0000000040", "Meta Platforms, Inc.", former=[("FACEBOOK INC", "2004-01-01", "2021-10-28")]), filings("0000000040", [("10-K", "2016-01-28")])),
    # deregistered after its last 10-K (taken over)
    "0000000050": (meta("0000000050", "BROADCOM CORP"), filings("0000000050", [("10-K", "2016-01-29"), ("15-12B", "2016-02-12")])),
    "0000000051": (meta("0000000051", "AVAGO TECHNOLOGIES LTD"), filings("0000000051", [("10-K", "2015-12-18"), ("15-12B", "2016-02-12")])),
    "0000000052": (meta("0000000052", "Broadcom Inc."), filings("0000000052", [("10-K", "2018-12-21")])),
}
ALL = {**SUBS, **EXTRA}


def test_short_name_is_not_matched_to_a_longer_filer_name():
    m = mem([["2019-04-01", "FOX", "Fox Corporation (Class B)", "0000000020", "wikipedia"]])
    r = s.resolve(m, ALL, {"FOX": ["0000000021"]}, {}, CFG)
    assert r.iloc[0]["cik_pit"] == "0000000020" and r.iloc[0]["pit_basis"] == "no_annual_report_in_window"


def test_name_on_the_date_decides_between_successor_and_member():
    m = mem([["2016-04-01", "JCI", "Johnson Controls", "0000000030", "wikipedia"], ["2017-04-01", "JCI", "Johnson Controls", "0000000030", "wikipedia"],
             ["2016-04-01", "META", "Meta Platforms", "0000000040", "wikipedia"]])
    r = s.resolve(m, ALL, {"JCI": ["0000000030", "0000000031"], "META": []}, {}, CFG)
    assert r.iloc[0]["cik_pit"] == "0000000031" and r.iloc[0]["name_agrees"]          # Tyco's CIK is not Johnson Controls in 2016
    assert r.iloc[2]["cik_pit"] == "0000000040" and r.iloc[2]["pit_basis"] == "v21_cik_annual_report" and "FACEBOOK" in r.iloc[2]["note"]
    assert s.names_at(ALL["0000000030"][0], "2017-04-01") == {"JOHNSON CONTROLS INTERNATIONAL"}


def test_deregistered_filer_is_not_a_member_and_v1_chain_wins():
    assert s.deregistered(ALL["0000000050"][1], "2016-04-01", CFG) and not s.deregistered(ALL["0000000050"][1], "2016-02-01", CFG)
    m = mem([["2016-04-01", "AVGO", "Broadcom", "0000000052", "wikipedia"], ["2019-04-01", "AVGO", "Broadcom", "0000000052", "wikipedia"]])
    r = s.resolve(m, ALL, {"AVGO": ["0000000050"]}, {}, CFG)
    assert r.iloc[0]["pit_basis"] == "no_annual_report_in_window"                       # old Broadcom Corp had deregistered
    chains = {"AVGO": ["0000000052", "0000000051"]}
    r = s.resolve(m, ALL, {}, {}, CFG, chains)
    assert r["cik_pit"].tolist() == ["0000000051", "0000000052"] and r.iloc[0]["pit_basis"] == "v1_verified_chain"


def test_agree_and_aliases_add():
    assert s.agree(["Bunge Global"], {"BUNGE"}) and not s.agree(["Fox"], {"ZYNEX"}) and not s.agree(["AA"], {"AAON"})
    assert s.agree(["Alcoa"], {"ALCOA"}) and not s.agree(["Fox Corporation (Class B)"], {"FOX FACTORY"}) and not s.agree(["Amcor"], {"AMCOR FLEXIBLES NORTH AMERICA"})
    assert s.queries("Skydance", {"Skydance": ["PARAMOUNT", "CBS"]}) == ["Skydance", "PARAMOUNT", "CBS"]


def test_bond_deregistration_does_not_end_reporting():
    f = filings("0000000060", [("10-K", "2015-08-07"), ("15-12B", "2015-09-01"), ("10-Q", "2015-10-27")])
    assert not s.deregistered(f, "2016-04-01", CFG)
    assert not s.deregistered(f, "2015-10-01", CFG)          # the next 10-Q comes after the date: still a reporting company
    assert s.edgar_norm("MYLAN N.V.") == "MYLAN" and s.edgar_norm("CA, INC.") == "CA"


def test_ticker_alias_and_continuity_tie_break():
    assert s.queries("DuPont", {"DD": "DUPONT E I DE NEMOURS & CO"}, "DD") == ["DuPont", "DUPONT E I DE NEMOURS & CO"]
    subs = {"0000000070": (meta("0000000070", "MYLAN INC"), filings("0000000070", [("10-K", "2015-03-02")])),
            "0000000071": (meta("0000000071", "MYLAN N.V."), filings("0000000071", [("10-K", "2016-02-16"), ("10-K", "2017-03-01")]))}
    m = mem([["2016-04-01", "VTRS", "Viatris", "", "unmapped"], ["2017-04-01", "VTRS", "Viatris", "", "unmapped"]])
    r = s.resolve(m, subs, {"VTRS": ["0000000070", "0000000071"]}, {}, {**CFG, "sec": {**CFG["sec"], "name_aliases": {"Viatris": "MYLAN"}}})
    assert r["cik_pit"].tolist() == ["0000000071", "0000000071"] and "tie broken" in r.iloc[0]["note"]
