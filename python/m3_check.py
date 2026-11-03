"""Step 3 (M3) status check: runs every remaining Step 3 check in one go and writes one report.

Usage (project folder, project venv, PostgreSQL password set for this PowerShell session):
  $env:PGPASSWORD = "<your postgres password>"
  & $vpy python\\m3_check.py
It rebuilds the Step 3 facts from the signed-off Step 2 collection (offline), reruns them into a temporary folder
to prove reproducibility, rebuilds the PostgreSQL schema twice (exports must be byte-identical), compares every
SQL ratio with an independent Python recomputation, runs the offline and reconciliation tests, reviews the data,
checks Git readiness, and writes data\\clean\\step3\\m3_check_report.txt.
It never edits config, code, tests, references or raw data, and never commits.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import m2_check as m2
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M3_FILES = [
    "config/step3.yaml", "config/manual_facts.csv", "config/database.yaml", "docs/m3_acceptance.md",
    "docs/evidence/m2_check_report_2026-11-02.txt",
    "python/step3_facts.py", "python/run_step3.py", "python/step3_db.py", "python/step3_reference.py", "python/m3_check.py",
    "sql/schema.sql", "sql/views.sql", "sql/checks.sql", "sql/queries/q1_highest_3y_avg_roe.sql",
    "sql/queries/q2_gross_margin_vs_peer_median.sql", "sql/queries/q3_nvda_fcf_vs_net_income.sql",
    "tests/test_step3.py", "tests/test_reconciliation_step3.py", "tests/test_db_step3.py",
    "tests/fixtures/reference_values_step3.csv", "tests/fixtures/ratio_reference_values.csv",
]
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + M3_FILES
OUT = PROJECT_ROOT / "data" / "clean" / "step3"


def postgres():
    section("3. POSTGRESQL")
    import step3_db as db
    cfg = db.load_db_config()
    try:
        psql = db.find_psql(cfg)
    except FileNotFoundError as exc:
        say(f"  {exc}")
        mark("T_pg", "FAIL")
        return False
    _, ver = run([psql, "--version"])
    env = db.psql_env(cfg)
    say(f"  client {ver.strip()} ({psql})")
    say(f"  target {env['PGUSER']}@{env['PGHOST']}:{env['PGPORT']}/{env['PGDATABASE']} schema {cfg['schema']}; "
        f"password from {'PGPASSWORD' if env.get('PGPASSWORD') else 'pgpass file (PGPASSWORD not set)'}")
    code, out, err = db.run_psql(cfg, ["-tA", "-c", "SHOW server_version"])
    if code:
        say(f"  cannot connect: {err.strip()}")
        mark("T_pg", "FAIL")
        return False
    say(f"  server PostgreSQL {out.strip()} (minimum {cfg['min_server_version']})")
    mark("T_pg", "PASS")
    return True


def facts_stage():
    section("5. STEP 3a FACTS ON THE SIGNED-OFF COLLECTION + REPRODUCIBILITY")
    import run_step3
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step3.main(["facts"])
    except Exception as exc:  # noqa: BLE001
        say(f"  Facts stage could not run: {type(exc).__name__}: {exc}")
        mark("T_facts", "FAIL")
        mark("T_repro", "FAIL")
        return None
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_facts", "PASS" if code == 0 else "FAIL")
    man = json.loads((OUT / "facts_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step3.main(["facts", "--out", tmp])
        again = json.loads((Path(tmp) / "facts_manifest.json").read_text(encoding="utf-8"))
    same = [again["output_sha256"].get(k) == v for k, v in man["output_sha256"].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} fact outputs byte-identical on rerun")
    mark("T_repro", "PASS" if all(same) else "FAIL")
    return man


def db_stage(pg_ok: bool):
    section("6. STEP 3b DATABASE BUILD (twice) + IN-DATABASE CHECKS")
    if not pg_ok:
        say("  skipped: PostgreSQL not reachable")
        mark("T_db", "FAIL")
        mark("T_db_repro", "FAIL")
        return
    import step3_db as db
    hashes = []
    for attempt in (1, 2):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ok = db.build(OUT)
        if attempt == 1:
            for x in buf.getvalue().splitlines():
                if x.strip():
                    say("  " + x.strip())
        hashes.append(json.loads((OUT / "db_manifest.json").read_text(encoding="utf-8"))["exports_sha256"])
        mark("T_db", "PASS" if ok else "FAIL")
    same = [hashes[1].get(k) == v for k, v in hashes[0].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} exports byte-identical on a second rebuild")
    mark("T_db_repro", "PASS" if all(same) and same else "FAIL")


def python_vs_sql():
    section("7. SQL VIEWS vs INDEPENDENT PYTHON RECOMPUTATION (Decimal, relative 1e-9)")
    import step3_reference as ref
    try:
        res = ref.compare(OUT / "load", OUT / "exports")
    except Exception as exc:  # noqa: BLE001
        say(f"  could not compare: {type(exc).__name__}: {exc}")
        mark("V_python", "FAIL")
        return
    for c, ok, d in res:
        say(f"  {'PASS' if ok else 'FAIL'}  {c}: {d}")
    mark("V_python", "PASS" if all(ok for _, ok, _ in res) else "FAIL")


def data_review(man):
    section("8. DATA REVIEW (for sign-off; nothing here changes data)")
    if man is None:
        say("  no output")
        return
    v = pd.read_csv(OUT / "validation_step3.csv", dtype=str, keep_default_na=False)
    for t, s in man["companies"].items():
        say(f"  {t:<5} rows {s['rows']:>5}  gaps {s['gaps']:>3}  {s['by_basis']}")
    say("")
    say("  Warnings (report only):")
    for r in v[(v["level"] == "warning") & (v["passed"] != "True")].itertuples():
        say(f"    WARN {r.scope:<5} {r.check}: {r.detail}")
    fails = v[(v["level"] == "error") & (v["passed"] != "True")]
    for r in fails.itertuples():
        say(f"    FAIL {r.scope} {r.check}: {r.detail}")
    say(f"  Error-level checks passing: {int(((v['level'] == 'error') & (v['passed'] == 'True')).sum())}/{int((v['level'] == 'error').sum())}")
    mark("V_checks", "PASS" if fails.empty else "FAIL")
    val = OUT / "exports" / "v_valuation_cutoff.csv"
    if val.exists():
        x = pd.read_csv(val, dtype=str, keep_default_na=False)
        say("")
        say("  Valuation at the cutoff ($ millions; multiples are times):")
        say(f"    {'ticker':<6}{'market cap':>12}{'EV':>12}{'LTM rev':>10}{'LTM NI':>10}{'P/E':>8}{'EV/Rev':>8}{'EV/EBITDA':>10}  EBITDA basis")
        f = lambda s, d=0: f"{float(s):,.{d}f}" if s else "-"  # noqa: E731
        for r in x.itertuples():
            say(f"    {r.ticker:<6}{f(r.market_cap):>12}{f(r.enterprise_value):>12}{f(r.ltm_revenue):>10}{f(r.ltm_net_income):>10}"
                f"{f(r.pe_ltm, 1):>8}{f(r.ev_revenue_ltm, 1):>8}{f(r.ev_ebitda, 1):>10}  {r.ebitda_basis}")
    for q in ("q1_highest_3y_avg_roe", "q2_gross_margin_vs_peer_median", "q3_nvda_fcf_vs_net_income"):
        p = OUT / "exports" / f"{q}.csv"
        if p.exists():
            say("")
            say(f"  {q}:")
            for ln in p.read_text(encoding="utf-8").splitlines()[:8]:
                say(f"    {ln}")


def reconciliation():
    section("9. RECONCILIATION (Step 2 and Step 3 filing references, reported ratios, SQL vs Python)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 3):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def git():
    section("10. GIT READINESS (nothing is committed by this script)")
    _, name = run(["git", "config", "user.name"])
    _, email = run(["git", "config", "user.email"])
    _, status = run(["git", "status", "--porcelain", "--untracked-files=all"])
    pending = [x[3:].strip().strip('"') for x in status.splitlines() if x.strip()]
    allowed = set(m2.EXPECTED_FILES) | {"docs/decision_log.md", "docs/issue_log.md", "docs/data_dictionary.md", "README.md",
                                        "pytest.ini", "requirements.txt"}
    unexpected = [p for p in pending if p not in allowed]
    say(f"  identity {'set' if name.strip() and '@' in email else 'NOT SET'}; files to commit: {len(pending)}")
    for p in pending:
        say(f"    {'UNEXPECTED ' if p in unexpected else ''}{p}")
    ignored = [p for p in ("data/raw/collections/x", "data/clean/step3/x.csv") if run(["git", "check-ignore", "-q", p])[0] != 0]
    say(f"  raw collections and data/clean outputs ignored by Git: {'yes' if not ignored else 'NO: ' + ', '.join(ignored)}")
    sec_email = os.environ.get("SEC_USER_AGENT", "").split()[-1:]          # the e-mail you set for SEC, never in Git
    password = re.compile(r"""pgpassword\s*=\s*["']?(?!<|\.\.\.|["'])\S""", re.I)   # a real value, not a placeholder
    def leaks(p):
        text = (PROJECT_ROOT / p).read_text(encoding="utf-8", errors="replace")
        return (sec_email and "@" in sec_email[0] and sec_email[0].lower() in text.lower()) or password.search(text)
    secret = [p for p in pending if (PROJECT_ROOT / p).is_file()
              and p.endswith((".py", ".yaml", ".md", ".sql", ".ini", ".txt", ".csv", ".conf")) and leaks(p)]
    say(f"  e-mail or stored password in files to commit: {'none' if not secret else ', '.join(secret)}")
    mark("S_git", "PASS" if name.strip() and "@" in email and not unexpected and not ignored and not secret else "FAIL")


def summary():
    section("11. STEP 3 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "PostgreSQL client found, server reachable and new enough", "T_pg"),
             ("T", "Offline test suite passes", "T_offline"),
             ("T", "Facts stage: every error-level check passes", "T_facts"), ("T", "Facts rerun is byte-identical", "T_repro"),
             ("T", "Database builds; DB1-DB6 pass", "T_db"), ("T", "Second rebuild gives byte-identical exports", "T_db_repro"),
             ("V", "Validation has no failing error-level check", "V_checks"),
             ("V", "Every SQL ratio equals the Python recomputation", "V_python"),
             ("V", "Filing references, reported ratios and Step 2 references tie", "V_recon"),
             ("V", "Warnings, definitions and open decision S3-D12 reviewed", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 3 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M3 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
    m2.environment()
    m2.files()
    pg_ok = postgres()
    section("4. OFFLINE TESTS")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 25 if code else 3):
        say("  " + x)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")
    man = facts_stage()
    db_stage(pg_ok)
    python_vs_sql()
    data_review(man)
    reconciliation()
    git()
    summary()
    report = OUT / "m3_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
