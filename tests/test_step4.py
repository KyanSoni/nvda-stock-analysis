"""Step 4 offline tests: scoring rules, estimates parsing and beta on synthetic data. No network, no database."""
import csv
import hashlib
from decimal import Decimal

import pandas as pd
import pytest

import step4_estimates as est
import step4_reference as ref

SC = est.load_scorecard()


# ---------------- scoring rules

@pytest.mark.parametrize("value,direction,pass_v,near_v,points", [
    ("25.25", "lower", "25", "35", 1),     # NVIDIA's P/E: just over the pass line -> near miss
    ("25", "lower", "25", "35", 1),        # pass is strict
    ("24.99", "lower", "25", "35", 2),
    ("35", "lower", "25", "35", 1),        # near miss is inclusive
    ("35.01", "lower", "25", "35", 0),
    ("0.10", "higher", "0.10", "0.05", 1),
    ("0.1001", "higher", "0.10", "0.05", 2),
    ("0.05", "higher", "0.10", "0.05", 1),
    ("0.0499", "higher", "0.10", "0.05", 0),
    ("-0.03", "lower", "-0.02", "0.02", 2),  # shares falling more than 2%
    ("0.02", "lower", "-0.02", "0.02", 1),   # flat within +/-2%
    ("0.021", "lower", "-0.02", "0.02", 0),
])
def test_score_boundaries(value, direction, pass_v, near_v, points):
    assert ref.score(Decimal(value), direction, Decimal(pass_v), Decimal(near_v)) == points


def test_missing_value_scores_zero():
    assert ref.score(None, "higher", Decimal("0.1"), Decimal("0.05")) == 0


def test_config_has_ten_consistent_tests():
    tests = SC["tests"]
    assert sorted(tests) == list(range(1, 11))
    for n, t in tests.items():
        assert t["direction"] in ("higher", "lower")
        assert (t["near"] <= t["pass"]) if t["direction"] == "higher" else (t["near"] >= t["pass"]), n
    assert 0.03 <= SC["wacc"]["equity_risk_premium"] <= 0.07 and SC["wacc"]["months"] == 60


# ---------------- estimates parsing

def _snapshot(tmp_path, eps_rows, ok=True, tamper=False):
    snap = tmp_path / "20261103T120000Z"
    snap.mkdir()
    body = "period,avg,low,high,yearAgoEps,numberOfAnalysts,growth\n" + "".join(eps_rows)
    (snap / "eps_TST.csv").write_bytes(body.encode("utf-8"))   # bytes: no Windows newline translation
    digest = hashlib.sha256(body.encode()).hexdigest()
    if tamper:
        (snap / "eps_TST.csv").write_bytes((body + "+1q,1,1,1,1,1,0\n").encode("utf-8"))
    with open(snap / "estimates_manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["retrieved_at_utc", "ticker", "kind", "attribute", "rows", "bytes", "sha256", "file", "required", "ok", "note"])
        w.writerow(["2026-11-03T12:00:00+00:00", "TST", "eps", "earnings_estimate", len(eps_rows), len(body), digest,
                    "eps_TST.csv" if ok else "", True, ok, "" if ok else "ValueError: empty result"])
    return snap


def test_parse_snapshot_keeps_values_and_provenance(tmp_path):
    snap = _snapshot(tmp_path, ["0y,4.60,4.1,5.0,3.0,40,0.53\n", "+1y,7.20,6,8.5,4.6,38,0.56\n", "0q,nan,,,,,\n"])
    rows, problems = est.parse_snapshot(snap, ["TST"])
    assert not problems
    r0 = next(r for r in rows if r["period"] == "0y")
    assert (r0["avg"], r0["analysts"], r0["year_ago"]) == ("4.60", "40", "3.0")
    assert r0["raw_file"] == "20261103T120000Z/eps_TST.csv" and len(r0["raw_sha256"]) == 64
    assert next(r for r in rows if r["period"] == "0q")["avg"] == ""          # 'nan' is blank, never 0


def test_parse_snapshot_reports_missing_period_failed_fetch_and_tampering(tmp_path):
    rows, problems = est.parse_snapshot(_snapshot(tmp_path, ["0y,4.6,4,5,3,40,0.5\n"]), ["TST"])
    assert problems == ["TST: no consensus EPS for period +1y"]
    (tmp_path / "b").mkdir()
    _, problems = est.parse_snapshot(_snapshot(tmp_path / "b", [], ok=False), ["TST"])
    assert any("not collected" in p for p in problems)
    (tmp_path / "c").mkdir()
    _, problems = est.parse_snapshot(_snapshot(tmp_path / "c", ["0y,1,1,1,1,1,0\n", "+1y,2,2,2,2,2,0\n"], tamper=True), ["TST"])
    assert any("hash differs" in p for p in problems)


def test_snapshot_age_limit():
    rows = [{"fetched_at_utc": "2026-11-05T10:00:00+00:00"}]
    assert est.snapshot_age_ok(rows, "2026-11-02", 7)[0]
    assert not est.snapshot_age_ok(rows, "2026-11-02", 2)[0]
    assert not est.snapshot_age_ok([{"fetched_at_utc": "2026-10-30T10:00:00+00:00"}], "2026-11-02", 7)[0]


# ---------------- beta

def test_beta_of_a_levered_copy_is_its_leverage():
    days = pd.bdate_range("2020-01-01", "2026-11-02")
    bench, stock, b, s = [], [], 100.0, 100.0
    for i, d in enumerate(days):
        r = 0.001 * ((i % 7) - 3)
        b, s = b * (1 + r), s * (1 + 2 * r)
        bench.append(b)
        stock.append(s)
    rows = [{"ticker": t, "price_date": d.strftime("%Y-%m-%d"), "adj_close": repr(v)}
            for t, series in (("BEN", bench), ("STK", stock)) for d, v in zip(days, series)]
    out = ref.betas(pd.DataFrame(rows), "2026-11-02", 60, ["STK"], ["BEN"])[("STK", "BEN")]
    assert out["months"] == 60 and out["last_month"] == "2026-10-01" and out["first_month"] == "2021-11-01"
    assert 1.9 < float(out["beta"]) < 2.1          # monthly compounding makes it close to, not exactly, 2
    assert float(out["correlation"]) > 0.99
