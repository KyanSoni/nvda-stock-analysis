"""Step 2 (M2) status check: runs every remaining check in one go and writes one report.

Usage (project folder, project venv):
  & $vpy python\\m2_check.py
It reprocesses the latest collection offline into data\\clean\\step2, reruns it into a temporary folder to
prove reproducibility, runs the offline and reconciliation tests, reviews the data, checks Git readiness,
and writes data\\clean\\step2\\m2_check_report.txt. It never edits config, code, tests, references or raw data.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import pandas as pd

from common import PROJECT_ROOT

PINNED = {"requests": "2.34.2", "pandas": "3.1.0", "pytest": "9.1.1", "PyYAML": "6.0.3", "yfinance": "1.7.0"}
M1_FILES = [
    ".gitattributes", ".gitignore", "README.md", "pytest.ini", "requirements.txt", "requirements-lock.txt",
    "config/project.yaml", "data/clean/.gitkeep", "data/raw/sec/.gitkeep",
    "docs/data_dictionary.md", "docs/decision_log.md", "docs/issue_log.md", "docs/m1_acceptance.md",
    "docs/evidence/m1_check_report_2026-11-02.txt",
    "python/common.py", "python/fetch_sec.py", "python/parse_companyfacts.py", "python/select_facts.py",
    "python/validate_m1.py", "python/run_m1.py", "python/m1_check.py",
    "tests/conftest.py", "tests/fixtures/companyfacts_synthetic.json", "tests/fixtures/reference_values.csv",
    "tests/test_gaps_and_contracts.py", "tests/test_live_sec.py", "tests/test_parse.py", "tests/test_reconciliation.py",
    "tests/test_reproducibility.py", "tests/test_scale_anomalies.py", "tests/test_selection.py",
]
M2_FILES = [
    "config/universe.yaml", "docs/m2_acceptance.md",
    "python/fetch_step2.py", "python/step2_sec.py", "python/step2_market.py", "python/run_step2.py", "python/m2_check.py",
    "tests/step2_fixture.py", "tests/test_step2.py", "tests/test_reconciliation_step2.py",
    "tests/fixtures/reference_values_step2.csv", "tests/fixtures/price_reference_values.csv",
]
EXPECTED_FILES = M1_FILES + M2_FILES
lines: list[str] = []
results: dict[str, str] = {}


def say(t=""):
    print(t)
    lines.append(t)


def section(t):
    say("")
    say("=" * 78)
    say(t)
    say("=" * 78)


def run(cmd, timeout=1800):
    try:
        p = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).rstrip()  # keep leading spaces: git status lines start with them
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, f"could not run {cmd[0]}: {exc}"


def tail(text, n):
    return [x for x in text.splitlines() if x.strip()][-n:]


def mark(k, v):
    results[k] = v


def environment():
    section("1. ENVIRONMENT")
    say(f"Python {sys.version.split()[0]} ({sys.executable})")
    in_venv = os.path.join("venvs", "nvda-stock-analysis").lower() in sys.prefix.lower()
    bad = []
    for pkg, want in PINNED.items():
        try:
            have = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            have = "missing"
        bad += [pkg] if have != want else []
        say(f"  {pkg:<9} pinned {want:<8} installed {have:<8} {'OK' if have == want else 'MISMATCH'}")
    lock = (PROJECT_ROOT / "requirements-lock.txt").read_text(encoding="utf-8", errors="replace").lower() \
        if (PROJECT_ROOT / "requirements-lock.txt").exists() else ""
    lock_missing = [f"{p}=={v}" for p, v in PINNED.items() if f"{p}=={v}".lower() not in lock]
    say(f"Venv {'OK' if in_venv else 'NOT the project venv'}; lock file {'OK' if not lock_missing else 'missing ' + ', '.join(lock_missing)}")
    mark("T_env", "PASS" if in_venv and not bad and not lock_missing else "FAIL")


def files():
    section("2. PROJECT FILES")
    missing = [f for f in EXPECTED_FILES if not (PROJECT_ROOT / f).exists()]
    say(f"Expected files present: {len(EXPECTED_FILES) - len(missing)}/{len(EXPECTED_FILES)}")
    for f in missing:
        say(f"  MISSING  {f}")
    mark("T_files", "PASS" if not missing else "FAIL")


def offline_tests():
    section("3. OFFLINE TESTS (synthetic data, no network)")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 25 if code else 3):
        say("  " + x)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")


def collection_status(coll: Path):
    section("4. COLLECTION")
    m = pd.read_csv(coll / "collection_manifest.csv", dtype=str, keep_default_na=False)
    info = json.loads((coll / "collection_info.json").read_text(encoding="utf-8"))
    say(f"  {coll.name}: started {info['started_new_york']}; {int((m['ok'] == 'true').sum())} files OK")
    failed = m[(m["required"] == "true") & (m["ok"] != "true")]
    superseded = []
    for r in failed.itertuples():
        later = m[(m["source"].isin(["fred", "treasury"])) & (m["ok"] == "true")] if r.source == "fred" else m.iloc[0:0]
        if len(later):
            superseded.append(r.source)
            say(f"  {r.source} {r.ticker}: failed in the main run, superseded by {', '.join(later['source'])} added later")
        else:
            say(f"  REQUIRED FAILED: {r.source} {r.ticker} {r.note}")
    mark("T_collection", "PASS" if len(failed) == len(superseded) else "FAIL")


def pipeline(coll: Path):
    section("5. PIPELINE ON THE SAVED COLLECTION + REPRODUCIBILITY")
    import run_step2
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step2.main(["--collection", coll.name])
    except Exception as exc:  # noqa: BLE001
        say(f"  Pipeline could not run: {type(exc).__name__}: {exc}")
        for k in ("T_pipeline", "T_repro"):
            mark(k, "FAIL")
        return None
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")
    out = PROJECT_ROOT / "data" / "clean" / "step2"
    man = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step2.main(["--collection", coll.name, "--out", tmp])
        again = json.loads((Path(tmp) / "run_manifest.json").read_text(encoding="utf-8"))
    same = [again["output_sha256"].get(k) == v for k, v in man["output_sha256"].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} outputs byte-identical on rerun")
    mark("T_repro", "PASS" if all(same) else "FAIL")
    return man


def data_review(man):
    section("6. DATA REVIEW (for sign-off; nothing here changes data)")
    out = PROJECT_ROOT / "data" / "clean" / "step2"
    if man is None:
        say("  no output")
        return
    v = pd.read_csv(out / "validation_summary.csv", dtype=str, keep_default_na=False)
    f = pd.read_csv(out / "facts_selected.csv", dtype=str, keep_default_na=False)
    g = pd.read_csv(out / "gap_report_all.csv", dtype=str, keep_default_na=False)
    import yaml
    base = yaml.safe_load(open(PROJECT_ROOT / "config" / "project.yaml", encoding="utf-8"))
    for t, s in man["companies"].items():
        latest = s["latest_fiscal_year"]
        x = f[(f["ticker"] == t) & (f["support_item"] == "False")]
        miss = []
        for item, spec in base["line_items"].items():
            per, bases = (("Q4", {"reported_instant", "derived_component"}) if spec["period_type"] == "instant"
                          else ("FY", {"reported_annual", "derived_component"}))
            have = {int(y) for y in x[(x["line_item"] == item) & (x["fiscal_period"] == per) & x["value_basis"].isin(bases)]["fiscal_year"]}
            m = [y for y in range(latest - 9, latest + 1) if y not in have]
            if m:
                miss.append(f"{item} FY{m[0]}-FY{m[-1]} ({len(m)})")
        say(f"  {t:<5} {s['window']:<14} annual coverage: {'complete' if not miss else '; '.join(miss)}")
        say(f"        rows by basis {s['by_basis']}; fallback rows {s['fallback_rows']}; anomalies {s['scale_anomalies']}")
        ltm = v[(v["scope"] == t) & (v["check"] == "C18_ltm_quarters_complete")]
        if len(ltm):
            say(f"        LTM: {ltm.iloc[0]['detail']}")
    say("")
    say("  Remaining gaps (excluding Q4 EPS/shares, not derivable by design):")
    gg = g[g["reason"] != "not_derivable_by_subtraction"].groupby(["ticker", "line_item", "reason"]).agg(
        n=("fiscal_year", "size"), first=("fiscal_year", "min"), last=("fiscal_year", "max"))
    for (t, i, r), row in gg.iterrows():
        say(f"    {t:<5} {i:<20} {row['n']:>3}  FY{row['first']}-FY{row['last']}  {r}")
    say("")
    mi = pd.read_csv(out / "market" / "market_inputs.csv", dtype=str, keep_default_na=False)
    say(f"  Market cutoff {man['market']['cutoff']} ({man['market']['cutoff_note']})")
    for r in mi.itertuples():
        say(f"    {r.ticker:<14} close {r.close_2dp:>9}  shares {r.shares_outstanding or '-':>12} as of {r.shares_as_of or '-'}"
            f"  mcap {r.market_cap_usd or '-'}  yf diff {r.shares_diff_pct or '-'}%")
    say("")
    for r in v[v["level"] == "warning"].itertuples():
        say(f"  {'WARN' if r.passed != 'True' else 'ok  '} {r.scope} {r.check}: {r.detail}")
    fails = v[(v["level"] == "error") & (v["passed"] != "True")]
    for r in fails.itertuples():
        say(f"  FAIL {r.scope} {r.check}: {r.detail}")
    say(f"  Error-level checks passing: {int(((v['level'] == 'error') & (v['passed'] == 'True')).sum())}/{int((v['level'] == 'error').sum())}")
    mark("V_checks", "PASS" if fails.empty else "FAIL")


def reconciliation():
    section("7. RECONCILIATION (SEC reference values, price references, NVIDIA vs M1)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 3):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def git():
    section("8. GIT READINESS (nothing is committed by this script)")
    _, name = run(["git", "config", "user.name"])
    _, email = run(["git", "config", "user.email"])
    _, status = run(["git", "status", "--porcelain", "--untracked-files=all"])
    pending = [x[3:].strip().strip('"') for x in status.splitlines() if x.strip()]
    unexpected = [p for p in pending if p not in EXPECTED_FILES]
    say(f"  identity {'set' if name.strip() and '@' in email else 'NOT SET'}; files to commit: {len(pending)}")
    for p in pending:
        say(f"    {'UNEXPECTED ' if p in unexpected else ''}{p}")
    code, _ = run(["git", "check-ignore", "-q", "data/raw/collections/x"])
    say(f"  collections ignored by Git: {'yes' if code == 0 else 'NO'}")
    mark("S_git", "PASS" if name.strip() and "@" in email and not unexpected and code == 0 else "FAIL")


def summary():
    section("9. STEP 2 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins (incl. yfinance) and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "Offline test suite passes", "T_offline"), ("T", "Collection complete (failures superseded)", "T_collection"),
             ("T", "Pipeline: every error-level check passes", "T_pipeline"), ("T", "Rerun is byte-identical", "T_repro"),
             ("V", "Validation summary has no failing error-level check", "V_checks"),
             ("V", "SEC and price references tie; NVIDIA equals M1", "V_recon"),
             ("V", "Concept additions, derivations, gaps and warnings reviewed", None),
             ("S", "Git identity set, no unexpected files, raw data ignored", "S_git"),
             ("S", "Decisions accepted and Step 2 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    import run_step2
    uni = run_step2.load_universe()
    coll = run_step2.latest_collection(uni)
    say(f"M2 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
    environment()
    files()
    offline_tests()
    collection_status(coll)
    man = pipeline(coll)
    data_review(man)
    reconciliation()
    git()
    summary()
    report = PROJECT_ROOT / "data" / "clean" / "step2" / "m2_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
