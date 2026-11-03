"""Step 4 (M4) status check: runs every Step 4 check in one go and writes one report.

Usage (project folder, project venv, $env:PGPASSWORD set, Step 3 built, estimates fetched):
  & $vpy python\\m4_check.py
Reparses the latest estimates snapshot (twice, to prove reproducibility), rebuilds the Step 4 tables and views twice
(exports must be byte-identical), compares every Step 4 view with an independent Python recomputation, runs the offline
and reconciliation tests, shows the scorecard for review, checks Git readiness, and writes
data\\clean\\step4\\m4_check_report.txt. It never edits config, code, tests, references or raw data, and never commits.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import m2_check as m2
import m3_check as m3
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M4_FILES = [
    "config/scorecard.yaml", "docs/m4_acceptance.md", "docs/evidence/m3_check_report_2026-11-03.txt",
    "python/fetch_step4.py", "python/step4_estimates.py", "python/step4_db.py", "python/step4_reference.py",
    "python/run_step4.py", "python/m4_check.py",
    "sql/step4_schema.sql", "sql/scorecard.sql", "sql/step4_checks.sql",
    "tests/test_step4.py", "tests/test_reconciliation_step4.py", "tests/test_db_step4.py",
    "tests/fixtures/estimates_crosscheck.csv",
]
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + m3.M3_FILES + M4_FILES
OUT = PROJECT_ROOT / "data" / "clean" / "step4"
S3 = PROJECT_ROOT / "data" / "clean" / "step3"


def estimates_stage():
    section("5. STEP 4a ESTIMATES SNAPSHOT + REPRODUCIBILITY")
    import run_step4
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step4.main(["estimates"])
    except Exception as exc:  # noqa: BLE001
        say(f"  Estimates stage could not run: {type(exc).__name__}: {exc}")
        mark("T_estimates", "FAIL")
        mark("T_repro", "FAIL")
        return
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_estimates", "PASS" if code == 0 else "FAIL")
    man = json.loads((OUT / "estimates_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step4.main(["estimates", "--out", tmp, "--snapshot", man["snapshot_id"]])
        again = json.loads((Path(tmp) / "estimates_manifest.json").read_text(encoding="utf-8"))
    same = again["output_sha256"] == man["output_sha256"]
    say(f"  reproducibility: estimates.csv {'byte-identical' if same else 'DIFFERS'} on rerun")
    mark("T_repro", "PASS" if same else "FAIL")


def db_stage(pg_ok: bool):
    section("6. STEP 4b SCORECARD DATABASE (twice) + IN-DATABASE CHECKS")
    if not pg_ok:
        say("  skipped: PostgreSQL not reachable")
        mark("T_db", "FAIL")
        mark("T_db_repro", "FAIL")
        return
    import step4_db
    import step4_estimates as est
    sc = est.load_scorecard()
    hashes, oks = [], []
    for attempt in (1, 2):
        buf = io.StringIO()
        with redirect_stdout(buf):
            oks.append(step4_db.build(OUT, sc))
        if attempt == 1:
            for x in buf.getvalue().splitlines():
                if x.strip():
                    say("  " + x.strip())
        p = OUT / "db_manifest_step4.json"
        hashes.append(json.loads(p.read_text(encoding="utf-8"))["exports_sha256"] if p.exists() else {})
    mark("T_db", "PASS" if all(oks) else "FAIL")
    same = [hashes[1].get(k) == v for k, v in hashes[0].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} exports byte-identical on a second rebuild")
    mark("T_db_repro", "PASS" if same and all(same) else "FAIL")


def python_vs_sql():
    section("7. STEP 4 VIEWS vs INDEPENDENT PYTHON RECOMPUTATION")
    import step4_estimates as est
    import step4_reference as ref
    try:
        res = ref.compare(S3 / "load", OUT / "load", OUT / "exports", est.load_scorecard())
    except Exception as exc:  # noqa: BLE001
        say(f"  could not compare: {type(exc).__name__}: {exc}")
        mark("V_python", "FAIL")
        return
    for c, ok, d in res:
        say(f"  {'PASS' if ok else 'FAIL'}  {c}: {d}")
    mark("V_python", "PASS" if all(ok for _, ok, _ in res) else "FAIL")


def data_review():
    section("8. SCORECARD REVIEW (for sign-off; nothing here changes data)")
    ex = OUT / "exports"
    if not (ex / "v_scorecard.csv").exists():
        say("  no exports")
        return
    card = pd.read_csv(ex / "v_scorecard.csv", dtype=str, keep_default_na=False)
    cols = [c for c in card.columns if c[:1] == "t" and c[1:2].isdigit()]
    say("  points per test (blank = not scored)")
    say("    " + f"{'ticker':<6}{'FY':>5}  " + " ".join(f"{c.split('_')[0]:>3}" for c in cols) + "   total")
    for r in card.sort_values("total", key=lambda s: s.astype(int), ascending=False).itertuples():
        d = r._asdict()
        say("    " + f"{r.ticker:<6}{r.fiscal_year:>5}  " + " ".join(f"{d[c] or '-':>3}" for c in cols) + f"   {r.total}/{r.max_possible}")
    det = pd.read_csv(ex / "v_scorecard_detail.csv", dtype=str, keep_default_na=False)
    say("")
    say("  NVIDIA by test:")
    for r in det[det["ticker"] == "NVDA"].itertuples():
        v = f"{float(r.value):.4g}" if r.value else "-"
        say(f"    {r.test_no:>2} {r.name:<34} {v:>10}  {r.result:<10} {r.reason}")
    w = pd.read_csv(ex / "v_wacc.csv", dtype=str, keep_default_na=False)
    p = pd.read_csv(ex / "v_peg.csv", dtype=str, keep_default_na=False).set_index("ticker")
    say("")
    say("  Provisional WACC and forward PEG (S4-D3 to S4-D6):")
    say(f"    {'ticker':<6}{'beta':>6}{'Ke':>8}{'Kd':>7}{'D/(D+E)':>9}{'WACC':>8}{'EPS FY0':>9}{'EPS FY1':>9}{'growth':>8}{'PEG':>6}")
    f = lambda s, n=2, pct=False: (f"{float(s) * 100:.{n}f}%" if pct else f"{float(s):.{n}f}") if s else "-"  # noqa: E731
    for r in w.itertuples():
        q = p.loc[r.ticker]
        say(f"    {r.ticker:<6}{f(r.beta):>6}{f(r.cost_of_equity, 1, True):>8}{f(r.cost_of_debt_pretax, 1, True):>7}"
            f"{f(r.debt_weight, 1, True):>9}{f(r.wacc, 1, True):>8}{f(q.eps_current_fy):>9}{f(q.eps_next_fy):>9}"
            f"{f(q.fwd_eps_growth, 0, True):>8}{f(q.peg_forward):>6}")
    fails = []
    if (OUT / "estimates_manifest.json").exists():
        man = json.loads((OUT / "estimates_manifest.json").read_text(encoding="utf-8"))
        fails += [c["check"] for c in man["checks"] if not c["passed"]]
    else:
        fails.append("estimates manifest missing")
    if (OUT / "db_checks_step4.csv").exists():
        checks = pd.read_csv(OUT / "db_checks_step4.csv", dtype=str, keep_default_na=False)
        fails += list(checks.loc[checks["passed"] != "True", "check"])
    else:
        fails.append("database checks missing")
    say("")
    say(f"  Failing error-level checks: {', '.join(fails) if fails else 'none'}")
    mark("V_checks", "PASS" if not fails else "FAIL")


def reconciliation():
    section("9. RECONCILIATION (all steps: filing references, SQL vs Python, consensus cross-check)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 3):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def summary():
    section("11. STEP 4 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "PostgreSQL reachable", "T_pg"), ("T", "Offline test suite passes", "T_offline"),
             ("T", "Estimates snapshot complete and fresh (E1, E2)", "T_estimates"), ("T", "Estimates rerun byte-identical", "T_repro"),
             ("T", "Scorecard views build; SC1-SC5 pass", "T_db"), ("T", "Second rebuild gives byte-identical exports", "T_db_repro"),
             ("V", "No failing error-level check", "V_checks"), ("V", "Every Step 4 view equals the Python recomputation", "V_python"),
             ("V", "All reconciliation tests pass, incl. the consensus cross-check", "V_recon"),
             ("V", "Scores, WACC inputs and estimate dates reviewed", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 4 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M4 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
    m2.environment()
    m2.files()
    pg_ok = m3.postgres()
    section("4. OFFLINE TESTS")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 25 if code else 3):
        say("  " + x)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")
    estimates_stage()
    db_stage(pg_ok)
    python_vs_sql()
    data_review()
    reconciliation()
    m3.git()
    code, _ = run(["git", "check-ignore", "-q", "data/raw/estimates/x"])
    say(f"  raw estimates snapshots ignored by Git: {'yes' if code == 0 else 'NO (add data/raw/estimates/ to .gitignore)'}")
    if code != 0:
        mark("S_git", "FAIL")
    summary()
    report = OUT / "m4_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
