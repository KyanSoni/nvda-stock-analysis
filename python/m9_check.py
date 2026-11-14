"""Step 9 (M9) status check: runs every Step 9 check in one go and writes one report.

Usage (project folder, project venv; Steps 4-7 outputs present):
  & $vpy python\\m9_check.py
Re-renders the memo (into a temporary folder, twice, to prove it is reproducible), checks M1-M7, runs the offline and
reconciliation tests, prints the memo's call and numbers for review, checks Git readiness, and writes
data\\clean\\step9\\m9_check_report.txt. It never edits config, code, tests, the memo or data.
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
import m4_check as m4
import m5_check as m5
import m6_check as m6
import m7_check as m7
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M9_FILES = ["config/memo.yaml", "docs/memo/memo_template.md", "docs/memo/NVDA_investment_memo.md", "docs/memo/NVDA_investment_memo.pdf",
            "docs/memo/exhibits/football_field.svg", "docs/m9_acceptance.md", "python/step9_memo.py", "python/run_step9.py",
            "python/m9_check.py", "python/build_simple_dcf.py", "excel/NVDA_Simple_DCF.xlsx", "tests/test_step9.py", "tests/test_reconciliation_step9.py"]
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + m3.M3_FILES + m4.M4_FILES + m5.M5_FILES + m6.M6_FILES + m7.M7_FILES + M9_FILES + m6.EVIDENCE
OUT = PROJECT_ROOT / "data" / "clean" / "step9"


def pipeline():
    section("4. STEP 9 MEMO: CHECKS + REPRODUCIBILITY")
    import run_step9
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step9.main(["--check"])
            with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
                run_step9.main(["--out", a])
                run_step9.main(["--out", b])
                same = all((Path(a) / f).read_bytes() == (Path(b) / f).read_bytes() for f in ("memo_numbers.csv", "NVDA_investment_memo.md", "football_field.svg"))
    except Exception as exc:  # noqa: BLE001
        say(f"  Step 9 could not run: {type(exc).__name__}: {exc}")
        for k in ("T_pipeline", "T_repro", "V_checks"):
            mark(k, "FAIL")
        return
    lines = [x.strip() for x in buf.getvalue().splitlines() if x.strip()]
    for x in lines[:10]:
        say("  " + x)
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")
    mark("V_checks", "PASS" if code == 0 else "FAIL")
    say(f"  reproducibility: memo, exhibit and numbers file {'byte-identical' if same else 'DIFFER'} on two renders")
    mark("T_repro", "PASS" if same else "FAIL")


def review():
    section("6. THE CALL (for sign-off; nothing here changes data)")
    memo = (PROJECT_ROOT / "docs" / "memo" / "NVDA_investment_memo.md").read_text(encoding="utf-8").splitlines()
    say("  " + memo[0].lstrip("# "))
    n = pd.read_csv(OUT / "memo_numbers.csv", dtype=str, keep_default_na=False).set_index("name")["value"] if (OUT / "memo_numbers.csv").exists() else None
    if n is None:
        say("  memo_numbers.csv missing: run python/run_step9.py")
        return
    f = lambda k: float(n[k])  # noqa: E731
    say(f"  DCF weighted {f('dcf_w'):.2f} -> rolled forward {f('dcf_fwd'):.2f} (Ke {f('ke'):.2%} - dividend yield {f('div_yield'):.2%})")
    say(f"  Comps {f('comps'):.2f} (NTM P/E {f('imp_pe'):.0f}, NTM EV/EBITDA {f('imp_eve'):.0f}; NTM range {f('comps_lo'):.0f}-{f('comps_hi'):.0f})")
    say(f"  Target {f('target_raw'):.2f} -> {f('target'):.0f}; expected return {f('exp_return'):+.1%} -> {n['rating']}")
    say(f"  Market-implied: WACC {f('rev_wacc'):.2%} (ours {f('wacc'):.2%}), g {f('rev_g'):.2%}, FY2028 Data Center growth {f('rev_dc'):.0%}")
    say("  Read docs\\memo\\NVDA_investment_memo.pdf (or the .md) in full before sign-off.")


def reconciliation():
    section("7. RECONCILIATION (all steps)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-rs", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 6):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def summary():
    section("9. STEP 9 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "Offline test suite passes", "T_offline"), ("T", "Memo renders; M1-M7 pass (claims true, sources, target, rating, first line, length, current)", "T_pipeline"),
             ("T", "Memo, exhibit and numbers byte-identical on two renders", "T_repro"),
             ("V", "Target and headline figures tie to Steps 6-7; earlier references tie", "V_recon"),
             ("V", "Memo read in full; rating, target, thesis, risks and catalysts judged", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 9 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M9 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
    m2.environment()
    m2.files()
    section("3. OFFLINE TESTS")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 25 if code else 3):
        say("  " + x)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")
    pipeline()
    review()
    reconciliation()
    m3.git()
    code, _ = run(["git", "check-ignore", "-q", "data/clean/step9/x"])
    if code != 0:
        mark("S_git", "FAIL")
    summary()
    report = OUT / "m9_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
