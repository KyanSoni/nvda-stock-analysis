"""Step 2 offline tests: synthetic collection (tests/step2_fixture.py), no network. Expected values by hand."""
from decimal import Decimal

import pandas as pd
import pytest

import step2_market as mk
import step2_sec as sec
from common import load_config, sha256_file
from run_step2 import OUTPUTS, process
from step2_fixture import A, A_OLD, B, build


def pick(df, **kw):
    m = pd.Series(True, index=df.index)
    for k, v in kw.items():
        m &= df[k].astype(str) == str(v)
    return df[m]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("s2")
    coll, uni = build(root)
    out = root / "out"
    checks, summary = process(coll, out, uni, load_config())
    facts = pd.read_csv(out / "facts_selected.csv", dtype=str, keep_default_na=False)
    return {"root": root, "coll": coll, "uni": uni, "out": out, "checks": checks, "summary": summary, "facts": facts}


def failing(checks):
    return {(s, c) for s, c, p, _, lvl in checks if lvl == "error" and not p}


# ---------------- identity and registrants

def test_identity_passes_and_predecessor_chain(run):
    ident = pd.read_csv(run["out"] / "identity_report.csv", dtype=str, keep_default_na=False)
    assert set(ident["cik"]) == {A, A_OLD, B}
    assert ("ALL", "I1_identities_and_fiscal_calendars") not in failing(run["checks"])


def test_identity_catches_wrong_fiscal_month(tmp_path):
    coll, uni = build(tmp_path)
    uni["companies"]["BBB"]["fy_end_month"] = 2
    _, problems = sec.identity_report(coll, uni)
    assert any("BBB" in p and "month" in p for p in problems)


def test_spillover_year_end_maps_to_previous_month(tmp_path):
    coll, uni = build(tmp_path)
    import json
    p = coll / "sec" / f"submissions_CIK{B}.json"
    d = json.loads(p.read_text())
    d["fiscalYearEnd"] = "0202"   # a 52/53-week year ending 2 Feb belongs to January
    p.write_text(json.dumps(d))
    ident, problems = sec.identity_report(coll, uni)
    assert pick(ident, cik=B).iloc[0]["fy_end_month_from_sec"] == 1 and not problems


def test_predecessor_value_replaced_by_successor_restatement(run):
    r = pick(run["facts"], ticker="AAA", line_item="revenue", fiscal_year=2016, value_basis="reported_annual").iloc[0]
    assert r["value"] == "905000000" and r["entity_cik"] == A and r["entity_role"] == "current"
    assert r["original_value"] == "900000000" and r["original_accn"].startswith("0000000002")
    assert r["restated"] == "True"


# ---------------- guarded fallbacks

def test_fallback_used_where_guard_absent(run):
    r = pick(run["facts"], ticker="AAA", line_item="stockholders_equity", period_end="2017-12-31").iloc[0]
    assert r["concept"] == "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest" and r["value"] == "60000000"


def test_fallback_blocked_where_guard_nonzero(run):
    assert pick(run["facts"], ticker="AAA", line_item="stockholders_equity", period_end="2016-12-31").empty
    gaps = pd.read_csv(run["out"] / "AAA" / "gap_report.csv", dtype=str, keep_default_na=False)
    assert not pick(gaps, line_item="stockholders_equity", fiscal_year=2016, fiscal_period="Q4").empty


def test_c13_catches_a_fallback_in_a_blocked_period(tmp_path):
    coll, uni = build(tmp_path)
    obs, files = sec.load_company(coll, uni, "AAA")
    cfg, guards, derived = sec.company_config(load_config(), uni, "AAA")
    sel = sec.select_company(obs, cfg, guards, "AAA")
    row = sel[(sel["line_item"] == "stockholders_equity")].iloc[[0]].copy()
    row["period_end"] = "2016-12-31"
    row["value"] = 55000000
    bad = pd.concat([sel, row], ignore_index=True)
    checks, _ = sec.company_checks(obs, bad, files, cfg, guards, uni, derived, 2017)
    assert any(c == "C13_guarded_fallbacks_respected" and not p for c, p, _, _ in checks)


# ---------------- derived values

@pytest.mark.parametrize("item, period, value, basis", [
    ("revenue", "Q2", "250000000", "derived_quarter"),
    ("revenue", "Q3", "270000000", "derived_quarter"),
    ("revenue", "Q4", "280000000", "derived_q4"),
    ("operating_cash_flow", "Q2", "70000000", "derived_quarter"),
    ("operating_cash_flow", "Q3", "80000000", "derived_quarter"),
    ("operating_cash_flow", "Q4", "100000000", "derived_q4"),
])
def test_derived_quarters(run, item, period, value, basis):
    r = pick(run["facts"], ticker="AAA", line_item=item, fiscal_year=2017, fiscal_period=period).iloc[0]
    assert (r["value"], r["value_basis"]) == (value, basis)
    assert r["accn"] == "" and r["derived_from_accns"] != ""


def test_derived_quarter_dates(run):
    r = pick(run["facts"], ticker="AAA", line_item="revenue", fiscal_year=2017, fiscal_period="Q2").iloc[0]
    assert (r["period_start"], r["period_end"]) == ("2017-04-01", "2017-06-30")


def test_reported_quarters_are_not_rederived(run):
    q = pick(run["facts"], ticker="AAA", line_item="shares_diluted", fiscal_year=2017)
    assert set(q["value_basis"]) == {"reported_quarter"}


def test_derived_component_total_liabilities(run):
    f = run["facts"]
    for end in ("2016-12-31", "2017-12-31"):
        r = pick(f, ticker="AAA", line_item="total_liabilities", period_end=end).iloc[0]
        assert r["value_basis"] == "derived_component" and r["value"] == "40000000"
        assert "liabilities_and_equity" in r["derived_from_accns"] and "total_equity" in r["derived_from_accns"]
    assert set(pick(f, ticker="AAA", line_item="total_equity")["support_item"]) == {"True"}


def test_derivations_only_for_listed_companies(run):
    assert pick(run["facts"], ticker="BBB", value_basis="derived_component").empty
    assert pick(run["facts"], ticker="BBB", support_item="True").empty


def test_c12_and_c14_catch_wrong_arithmetic(tmp_path):
    coll, uni = build(tmp_path)
    obs, files = sec.load_company(coll, uni, "AAA")
    cfg, guards, derived = sec.company_config(load_config(), uni, "AAA")
    sel = sec.select_company(obs, cfg, guards, "AAA")
    sel = pd.concat([sel, sec.derive_quarters(sel, cfg)], ignore_index=True)
    sel = pd.concat([sel, sec.derive_components(sel, cfg, uni, derived)], ignore_index=True)
    sel.loc[sel["value_basis"] == "derived_quarter", "value"] = 1
    sel.loc[sel["value_basis"] == "derived_component", "value"] = 1
    checks, _ = sec.company_checks(obs, sel, files, cfg, guards, uni, derived, 2017)
    failed = {c for c, p, _, _ in checks if not p}
    assert {"C12_derived_quarters_recompute", "C14_derived_components_recompute"} <= failed


# ---------------- checks on the whole run

def test_only_expected_checks_fail(run):
    # the synthetic companies report too few line items for LTM (C18); everything else must pass
    assert failing(run["checks"]) == {("AAA", "C18_ltm_quarters_complete"), ("BBB", "C18_ltm_quarters_complete")}


def test_c1_counts_every_registrant_file(run):
    c1 = [d for s, c, p, d, _ in run["checks"] if s == "AAA" and c == "C1_all_observations_kept"][0]
    assert c1.startswith("21 rows parsed vs 21")  # 18 us-gaap + 2 dei (AAA) + 1 (predecessor)


# ---------------- market

def test_cutoff_includes_completed_session(run):
    assert run["summary"]["market"]["cutoff"] == "2018-03-02"


def test_cutoff_excludes_session_in_progress(tmp_path):
    coll, uni = build(tmp_path, started_new_york="2018-03-02T11:00:00-05:00")
    prices = mk.load_prices(coll, ["SPY"], pd.read_csv(coll / "collection_manifest.csv", dtype=str, keep_default_na=False))
    import json
    cut, note = mk.cutoff_date(json.loads((coll / "collection_info.json").read_text()), prices, "SPY", "16:30")
    assert cut == "2018-03-01" and "not complete" in note


def test_close_as_traded_undoes_later_splits(run):
    p = pd.read_csv(run["out"] / "market" / "prices.csv", dtype=str, keep_default_na=False)
    b = pick(p, ticker="BBB")
    assert pick(b, date="2018-02-26").iloc[0]["close_as_traded"] == "200.0000"   # 50 x 4: before the split
    assert pick(b, date="2018-02-28").iloc[0]["close_as_traded"] == "52.0000"    # split day: already new basis
    assert pick(b, date="2018-03-02").iloc[0]["close_as_traded"] == "54.0000"


def test_corporate_actions(run):
    a = pd.read_csv(run["out"] / "market" / "corporate_actions.csv", dtype=str, keep_default_na=False)
    assert set(zip(a["ticker"], a["date"], a["action"])) == {("BBB", "2018-02-28", "split"), ("AAA", "2018-03-01", "dividend")}


def test_split_crosscheck_pass_and_mismatch():
    facts = pd.DataFrame([
        {"ticker": "X", "line_item": "shares_diluted", "value_basis": "reported_quarter", "fiscal_year": 2020,
         "fiscal_period": "Q1", "period_start": "2020-01-01", "period_end": "2020-03-31", "original_value": 100},
        {"ticker": "X", "line_item": "shares_diluted", "value_basis": "reported_quarter", "fiscal_year": 2020,
         "fiscal_period": "Q3", "period_start": "2020-07-01", "period_end": "2020-09-30", "original_value": 402},
    ])
    ok, detail, _ = mk.split_crosscheck(pd.DataFrame([{"ticker": "X", "date": "2020-05-15", "action": "split", "value": "4.0"}]), facts)
    assert ok and "OK" in detail
    ok, detail, _ = mk.split_crosscheck(pd.DataFrame([{"ticker": "X", "date": "2020-05-15", "action": "split", "value": "10.0"}]), facts)
    assert not ok and "MISMATCH" in detail


def test_market_inputs(run):
    m = pd.read_csv(run["out"] / "market" / "market_inputs.csv", dtype=str, keep_default_na=False).set_index("ticker")
    a = m.loc["AAA"]
    assert a["shares_outstanding"] == "404000000"          # two share classes in one filing, summed
    assert a["close_2dp"] == "14.00" and a["market_cap_usd"] == str(14 * 404000000)
    assert a["shares_diff_pct"] == "0.00"
    rf = m.loc["RISK_FREE_10Y"]
    assert rf["close"] == "2.81" and rf["shares_as_of"] == "2018-03-01"   # '.' on the cutoff day is skipped


def test_missing_risk_free_fails_p4b(tmp_path):
    coll, uni = build(tmp_path, with_rates=False)
    checks, _ = process(coll, tmp_path / "out", uni, load_config())
    assert ("MARKET", "P4b_risk_free_at_cutoff") in failing(checks)


@pytest.mark.parametrize("obs_date, lag, ok", [("03/02/2018", 0, True), ("02/26/2018", 4, True), ("02/23/2018", 7, False)])
def test_p4b_accepts_same_day_and_rejects_stale_yield(tmp_path, obs_date, lag, ok):
    coll, uni = build(tmp_path, with_rates=False)
    (coll / "market" / "treasury_par_yield_2018.csv").write_text(f'Date,"10 Yr"\n{obs_date},2.87\n', encoding="utf-8")
    checks, _ = process(coll, tmp_path / "out", uni, load_config())
    p4b = [(p, d) for s, c, p, d, _ in checks if c == "P4b_risk_free_at_cutoff"][0]
    assert p4b[0] is ok and f"({lag} days" in p4b[1]


def test_treasury_fallback_file_is_read(tmp_path):
    coll, uni = build(tmp_path, with_rates=False)
    (coll / "market" / "treasury_par_yield_2018.csv").write_text('Date,"1 Mo","10 Yr"\n03/02/2018,1.5,2.87\n', encoding="utf-8")
    rf = mk.risk_free(coll, uni, "2018-03-02")
    assert rf["value_pct"] == "2.87" and rf["lag_days"] == 0 and "Treasury" in rf["series"]


# ---------------- reproducibility

def test_same_collection_gives_byte_identical_outputs(run, tmp_path):
    process(run["coll"], tmp_path / "again", run["uni"], load_config())
    for f in OUTPUTS:
        assert sha256_file(run["out"] / f) == sha256_file(tmp_path / "again" / f), f


def test_raw_collection_is_never_modified(run, tmp_path):
    before = {p.name: sha256_file(p) for p in run["coll"].rglob("*") if p.is_file()}
    process(run["coll"], tmp_path / "x", run["uni"], load_config())
    assert before == {p.name: sha256_file(p) for p in run["coll"].rglob("*") if p.is_file()}
