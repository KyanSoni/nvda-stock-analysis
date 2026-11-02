"""M1 status check: runs every remaining M1 check in one go and writes one report.

Usage (from the project folder, with the venv's python):
  python python/m1_check.py            # offline: environment, files, tests, pipeline, reproducibility,
                                       #          data review, reconciliation, Git readiness
  python python/m1_check.py --live     # the same, plus the live SEC test (needs SEC_USER_AGENT)

It regenerates data/clean from the latest saved snapshot (no network), reruns into a temporary
folder to prove the output is reproducible, and writes data/clean/m1_check_report.txt.
It never edits config, code, tests, reference values or raw snapshots.
"""
from __future__ import annotations

import argparse
import csv
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

from common import PROJECT_ROOT, load_config

REPORT = PROJECT_ROOT / "data" / "clean" / "m1_check_report.txt"
VENV_MARKER = os.path.join("venvs", "nvda-stock-analysis")
PINNED = {"requests": "2.34.2", "pandas": "3.1.0", "pytest": "9.1.1", "PyYAML": "6.0.3"}
EXPECTED_FILES = [
    ".gitattributes", ".gitignore", "README.md", "pytest.ini", "requirements.txt", "requirements-lock.txt",
    "config/project.yaml",
    "data/clean/.gitkeep", "data/raw/sec/.gitkeep",
    "docs/data_dictionary.md", "docs/decision_log.md", "docs/issue_log.md", "docs/m1_acceptance.md",
    "python/common.py", "python/fetch_sec.py", "python/parse_companyfacts.py", "python/select_facts.py",
    "python/validate_m1.py", "python/run_m1.py", "python/m1_check.py",
    "tests/conftest.py", "tests/fixtures/companyfacts_synthetic.json", "tests/fixtures/reference_values.csv",
    "tests/test_gaps_and_contracts.py", "tests/test_live_sec.py", "tests/test_parse.py",
    "tests/test_reconciliation.py", "tests/test_reproducibility.py", "tests/test_scale_anomalies.py",
    "tests/test_selection.py",
]
REFERENCE_REQUIRED = ["line_item", "fiscal_year", "fiscal_period", "value_basis", "reference_value", "reference_unit",
                      "source_form", "accession", "source_url", "location_in_filing", "entered_by", "entered_on"]
MIN_REFERENCES = 3

lines: list[str] = []
results: dict[str, str] = {}


def say(text: str = "") -> None:
    print(text)
    lines.append(text)


def section(title: str) -> None:
    say("")
    say("=" * 78)
    say(title)
    say("=" * 78)


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 99, f"could not run {cmd[0]}: {exc}"


def tail(text: str, n: int) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()][-n:]


def mark(key: str, status: str) -> str:
    results[key] = status
    return status


# ---------------------------------------------------------------------------

def check_environment() -> None:
    section("1. ENVIRONMENT")
    say(f"Python      {sys.version.split()[0]}  ({sys.executable})")
    in_venv = VENV_MARKER.lower() in sys.prefix.lower()
    say(f"Venv        {'OK' if in_venv else 'NOT the project venv'}  ({sys.prefix})")
    bad = []
    for pkg, want in PINNED.items():
        try:
            have = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            have = "missing"
        flag = "OK" if have == want else "MISMATCH"
        if have != want:
            bad.append(pkg)
        say(f"  {pkg:<10} pinned {want:<8} installed {have:<8} {flag}")
    lock = PROJECT_ROOT / "requirements-lock.txt"
    lock_ok = False
    if lock.exists():
        text = lock.read_text(encoding="utf-8", errors="replace")
        missing_pins = [f"{p}=={v}" for p, v in PINNED.items() if f"{p}=={v}".lower() not in text.lower()]
        lock_ok = not missing_pins
        say(f"Lock file   {'OK' if lock_ok else 'missing pins: ' + ', '.join(missing_pins)}")
    else:
        say("Lock file   MISSING: run  & $vpy -m pip freeze | Set-Content -Encoding ascii requirements-lock.txt")
    mark("T_env", "PASS" if in_venv and not bad else "FAIL")
    mark("T_lock", "PASS" if lock_ok else "FAIL")


def check_files() -> None:
    section("2. PROJECT FILES")
    missing = [f for f in EXPECTED_FILES if not (PROJECT_ROOT / f).exists()]
    say(f"Expected files present: {len(EXPECTED_FILES) - len(missing)}/{len(EXPECTED_FILES)}")
    for f in missing:
        say(f"  MISSING  {f}")
    mark("T_files", "PASS" if not missing else "FAIL")


def check_offline_tests() -> None:
    section("3. OFFLINE TESTS (synthetic snapshot, no network)")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for ln in tail(out, 25 if code else 3):
        say("  " + ln)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")


def check_pipeline(cfg: dict) -> dict | None:
    section("4. PIPELINE ON THE SAVED SNAPSHOT + REPRODUCIBILITY")
    import run_m1  # imported here so a broken module is reported, not fatal
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_m1.main(["--source", "snapshot"])
    except Exception as exc:  # report and stop this section
        say(f"  Pipeline could not run: {type(exc).__name__}: {exc}")
        for key in ("T_pipeline", "T_repro", "V_C1", "V_C3", "V_C4C9", "V_C11"):
            mark(key, "FAIL")
        return None
    for ln in buf.getvalue().splitlines():
        if ln.strip().startswith(("PASS", "FAIL", "WARN")) or '"snapshot_file"' in ln or '"scale_anomalies' in ln:
            say("  " + ln.strip())
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")

    clean = PROJECT_ROOT / cfg["paths"]["clean_dir"]
    manifest = json.loads((clean / "run_manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_m1.main(["--source", "snapshot", "--out", tmp])
        rerun = json.loads((Path(tmp) / "run_manifest.json").read_text(encoding="utf-8"))
    same = []
    for name, digest in manifest["output_sha256"].items():
        ok = rerun["output_sha256"].get(name) == digest
        same.append(ok)
        say(f"  reproducibility  {name:<13} {'MATCH' if ok else 'DIFFERENT'}")
    mark("T_repro", "PASS" if all(same) else "FAIL")

    v = pd.read_csv(clean / "validation_report.csv", dtype=str, keep_default_na=False).set_index("check")["passed"]
    def ok(*ids): return "PASS" if all(v.get(i) == "True" for i in ids) else "FAIL"
    mark("V_C1", ok("C1_all_observations_kept"))
    mark("V_C3", ok("C3_reported_rows_have_provenance"))
    mark("V_C4C9", ok("C4_derived_rows_labelled", "C9_derived_q4_arithmetic"))
    mark("V_C11", ok("C11_no_scale_anomalies_in_target_window"))
    return manifest


def check_data_review(cfg: dict, manifest: dict | None) -> None:
    section("5. DATA REVIEW (for sign-off; nothing here changes data)")
    clean = PROJECT_ROOT / cfg["paths"]["clean_dir"]
    if manifest is None or not (clean / "nvda_facts_selected.csv").exists():
        say("  No pipeline output to review.")
        return
    sel = pd.read_csv(clean / "nvda_facts_selected.csv", dtype=str, keep_default_na=False)
    gaps = pd.read_csv(clean / "gap_report.csv", dtype=str, keep_default_na=False)
    anom = pd.read_csv(clean / "anomalies.csv", dtype=str, keep_default_na=False)
    say(f"  Snapshot {manifest['snapshot_file']}  sha256 {manifest['snapshot_sha256'][:16]}...")
    say(f"  Window {manifest['target_window']}   selected rows {len(sel)}   restated {manifest['restated_rows']}")

    latest = int(manifest["latest_fiscal_year"])
    years = list(range(latest - cfg["history"]["target_fiscal_years"] + 1, latest + 1))
    say("")
    say("  Annual coverage in the window (reported_annual or reported_instant at year end):")
    for item, spec in cfg["line_items"].items():
        basis, period = ("reported_instant", "Q4") if spec["period_type"] == "instant" else ("reported_annual", "FY")
        have = set(sel[(sel["line_item"] == item) & (sel["value_basis"] == basis)
                       & (sel["fiscal_period"] == period)]["fiscal_year"].astype(int))
        missing = [y for y in years if y not in have]
        say(f"    {item:<22} {len(years) - len(missing):>2}/{len(years)}" + (f"   missing FY{', FY'.join(map(str, missing))}" if missing else ""))

    say("")
    say("  Gaps by line item and reason:")
    for (item, reason), n in gaps.groupby(["line_item", "reason"]).size().items():
        say(f"    {n:>3}  {item:<22} {reason}")

    say("")
    inside = anom[anom["in_target_window"] == "True"]
    say(f"  Scale anomalies: {len(anom)} total, {len(inside)} inside the window")
    for r in anom.itertuples():
        say(f"    FY{r.fiscal_year} {r.fiscal_period:<3} {r.line_item:<15} {r.anomaly_type:<18} ratio {r.ratio}  window={r.in_target_window}")

    say("")
    say("  Restated rows by line item:")
    for item, n in sel[sel["restated"] == "True"].groupby("line_item").size().sort_values(ascending=False).items():
        say(f"    {n:>3}  {item}")


def check_references(cfg: dict) -> None:
    section("6. RECONCILIATION AGAINST YOUR REFERENCE VALUES")
    path = PROJECT_ROOT / "tests" / "fixtures" / "reference_values.csv"
    if not path.exists():
        say("  reference_values.csv is missing.")
        mark("V_refs", "FAIL"); mark("V_recon", "FAIL")
        return
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    problems = [f"missing column '{c}'" for c in REFERENCE_REQUIRED if c not in header]
    for i, r in enumerate(rows, start=2):
        blanks = [c for c in REFERENCE_REQUIRED if not (r.get(c) or "").strip()]
        if blanks:
            problems.append(f"row {i}: blank {', '.join(blanks)}")
        val = (r.get("reference_value") or "").replace(",", "").strip()
        try:
            float(val)
        except ValueError:
            problems.append(f"row {i}: reference_value '{r.get('reference_value')}' is not a number")
        if "<" in ",".join(str(x) for x in r.values()):
            problems.append(f"row {i}: still contains a <placeholder>")
    say(f"  Reference rows: {len(rows)} (need at least {MIN_REFERENCES})")
    for r in rows:
        say(f"    {r.get('line_item')} FY{r.get('fiscal_year')} {r.get('fiscal_period')} = {r.get('reference_value')} {r.get('reference_unit')}")
    for p in problems:
        say(f"  PROBLEM  {p}")
    refs_ok = len(rows) >= MIN_REFERENCES and not problems
    mark("V_refs", "PASS" if refs_ok else ("TODO" if not rows else "FAIL"))
    if not rows:
        say("  Reconciliation not run: add the reference rows first (see docs/m1_acceptance.md).")
        mark("V_recon", "TODO")
        return
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-p", "no:cacheprovider"])
    for ln in tail(out, 30 if code else 3):
        say("  " + ln)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def check_live(enabled: bool) -> None:
    section("7. LIVE SEC TEST")
    if not enabled:
        say("  Not run (offline mode). It passed on 2026-11-02; rerun with --live to confirm today.")
        mark("T_live", "NOT RUN")
        return
    ua = os.environ.get("SEC_USER_AGENT", "")
    if "@" not in ua or '"' in ua:
        say(f"  SEC_USER_AGENT looks wrong: '{ua}'. Set it to: Your Name your-email@example.com")
        mark("T_live", "FAIL")
        return
    code, out = run([sys.executable, "-m", "pytest", "-m", "live", "-q", "-p", "no:cacheprovider"])
    for ln in tail(out, 20 if code else 3):
        say("  " + ln)
    mark("T_live", "PASS" if code == 0 and " passed" in out else "FAIL")


def check_git() -> None:
    section("8. GIT READINESS (nothing is committed by this script)")
    code, top = run(["git", "rev-parse", "--show-toplevel"])
    is_root = code == 0 and Path(top).resolve() == PROJECT_ROOT.resolve()
    say(f"  Repo root   {'OK' if is_root else 'PROBLEM: ' + top}")
    _, name = run(["git", "config", "user.name"])
    _, email = run(["git", "config", "user.email"])
    ident_ok = bool(name.strip()) and "@" in email
    say(f"  user.name   {name or 'NOT SET'}")
    say(f"  user.email  {'set' if '@' in email else 'NOT SET'}")
    _, branch = run(["git", "symbolic-ref", "--short", "HEAD"])
    code, count = run(["git", "rev-list", "--count", "HEAD"])
    say(f"  Branch      {branch}   commits: {count if code == 0 else 0}")
    _, status = run(["git", "status", "--porcelain", "--untracked-files=all"])
    pending = [ln[3:].strip().strip('"') for ln in status.splitlines() if ln.strip()]
    unexpected = [p for p in pending if p not in EXPECTED_FILES]
    say(f"  Files ready to add: {len(pending)}")
    for p in unexpected:
        say(f"  UNEXPECTED  {p}   (not part of M1: move it out of the project folder or explain it)")
    raw_files = sorted((PROJECT_ROOT / "data" / "raw" / "sec").glob("*.json"))
    ignored = all(run(["git", "check-ignore", "-q", str(p.relative_to(PROJECT_ROOT))])[0] == 0 for p in raw_files)
    say(f"  Raw snapshots ignored by Git: {'yes' if ignored else 'NO'} ({len(raw_files)} files)")
    mark("S_git", "PASS" if is_root and ident_ok and not unexpected and ignored else "FAIL")
    if not ident_ok:
        say('  Fix: git config --global user.name "Kyan Soni"; git config --global user.email "<your email>"')


def summary() -> None:
    section("9. M1 ACCEPTANCE SUMMARY")
    items = [
        ("T", "Environment and pinned packages", "T_env"),
        ("T", "requirements-lock.txt generated", "T_lock"),
        ("T", "All expected files present", "T_files"),
        ("T", "Offline test suite passes", "T_offline"),
        ("T", "Live SEC test passes", "T_live"),
        ("T", "Pipeline run on saved snapshot: all error-level checks pass", "T_pipeline"),
        ("T", "Rerun reproduces byte-identical outputs", "T_repro"),
        ("V", "C1 every observation kept", "V_C1"),
        ("V", "C3 full provenance on reported rows", "V_C3"),
        ("V", "C4/C9 derived Q4 labelled and recomputes", "V_C4C9"),
        ("V", "C11 no scale anomalies inside the window", "V_C11"),
        ("V", "At least 3 reference values with full provenance", "V_refs"),
        ("V", "Reference values tie exactly", "V_recon"),
        ("V", "Capex concepts, gaps and restatements reviewed", None),
        ("S", "Git identity set, no unexpected files, raw data ignored", "S_git"),
        ("S", "Proposed decisions accepted in decision_log.md", None),
        ("S", "Kyan's sign-off and first commit", None),
    ]
    for gate, label, key in items:
        status = results.get(key, "MANUAL") if key else "MANUAL"
        say(f"  [{gate}] {status:<8} {label}")
    blocking = [label for _, label, key in items if key and results.get(key) in ("FAIL", "TODO")]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also run the live SEC test")
    args = ap.parse_args(argv)
    cfg = load_config()
    say(f"M1 CHECK REPORT  {datetime.now(timezone.utc).isoformat(timespec='seconds')}  project {PROJECT_ROOT}")
    check_environment()
    check_files()
    check_offline_tests()
    manifest = check_pipeline(cfg)
    check_data_review(cfg, manifest)
    check_references(cfg)
    check_live(args.live)
    check_git()
    summary()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {REPORT}")
    return 0 if not any(v == "FAIL" for v in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
