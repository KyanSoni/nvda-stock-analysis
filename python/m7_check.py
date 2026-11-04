"""Step 7 (M7) status check: runs every Step 7 check in one go and writes one report.

Usage (project folder, project venv; Steps 2-6 outputs present):
  & $vpy python\\m7_check.py
Runs the comps (twice, to prove the CSV outputs are reproducible), checks C1-C6, compares the workbook's Comps tab
with Python if LibreOffice is installed, runs the offline and reconciliation tests, prints the comps for review,
checks Git readiness, and writes data\\clean\\step7\\m7_check_report.txt. It never edits config, code, tests or data.
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
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M7_FILES = ["config/comps.yaml", "docs/m7_acceptance.md", "python/step7_comps.py", "python/build_comps.py", "python/step7_check.py",
            "python/run_step7.py", "python/m7_check.py", "tests/test_step7.py", "tests/test_reconciliation_step7.py"]
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + m3.M3_FILES + m4.M4_FILES + m5.M5_FILES + m6.M6_FILES + M7_FILES + m6.EVIDENCE
OUT = PROJECT_ROOT / "data" / "clean" / "step7"
WB = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


def pipeline():
    section("4. STEP 7 COMPS + REPRODUCIBILITY")
    import run_step7
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step7.main([])
    except Exception as exc:  # noqa: BLE001
        say(f"  Step 7 could not run: {type(exc).__name__}: {exc}")
        for k in ("T_pipeline", "T_repro", "V_checks"):
            mark(k, "FAIL")
        return
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")
    man = json.loads((OUT / "manifest_step7.json").read_text(encoding="utf-8"))
    mark("V_checks", "PASS" if all(c["passed"] for c in man["checks"] if c["level"] == "error") else "FAIL")
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step7.main(["--out", tmp, "--workbook", str(Path(tmp) / "wb.xlsx")])
        again = json.loads((Path(tmp) / "manifest_step7.json").read_text(encoding="utf-8"))
    same = [again["output_sha256"].get(k) == v for k, v in man["output_sha256"].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} CSV outputs byte-identical on rerun")
    mark("T_repro", "PASS" if same and all(same) else "FAIL")


def excel_check():
    section("5. WORKBOOK COMPS vs PYTHON (LibreOffice recalculation)")
    import step6_dcf as d
    import step7_check
    import step7_comps as c
    s5 = PROJECT_ROOT / "data" / "clean" / "step5"
    res = c.run(inp=c.read_inputs(d.payload(rd(s5 / "model_data.csv"), rd(s5 / "assumptions.csv"))))
    out = step7_check.compare(WB, res)
    for k, ok, dd in out:
        say(f"  {'MANUAL' if ok is None else 'PASS' if ok else 'FAIL'}  {k}: {dd}")
    mark("V_excel", "MANUAL" if out[0][1] is None else "PASS" if out[0][1] else "FAIL")


def review():
    section("6. COMPS REVIEW (for sign-off; nothing here changes data)")
    tb = rd(OUT / "comps_table.csv")
    say("  " + f"{'':<6}{'NTM wt':>7}{'NTM grw':>9}{'GM LTM':>8}{'EV/Rev N':>9}{'EV/EBITDA N':>12}{'P/E N':>8}{'EV/Rev L':>9}{'EV/EBITDA L':>12}{'P/E L':>8}")
    num = lambda v, p="{:.1f}": "n/m" if v == "" else p.format(float(v))  # noqa: E731
    for r in tb.itertuples():
        flag = lambda k: "" if getattr(r, f"use_{k}") == "1" or r.role == "target" else "*"  # noqa: E731
        say("  " + f"{r.ticker:<6}{num(r.w_fy0, '{:.2f}'):>7}{num(r.growth_ntm, '{:.0%}'):>9}{num(r.gross_margin_ltm, '{:.0%}'):>8}"
            + "".join(f"{num(getattr(r, k)) + flag(k):>{w}}" for k, w in (("ev_revenue_ntm", 9), ("ev_ebitda_ntm", 12), ("pe_ntm", 8),
                                                                          ("ev_revenue_ltm", 9), ("ev_ebitda_ltm", 12), ("pe_ltm", 8))))
    say("  * = left out of the peer statistics (above 100x, not meaningful, or fiscal-year EBITDA); NVIDIA is never in them")
    im = rd(OUT / "comps_implied.csv")
    say("  NVIDIA value per share at peer 25th / median / 75th:")
    for r in im.itertuples():
        say(f"    {r.label:<20} {num(r.p25, '{:.0f}'):>6} / {num(r.p50, '{:.0f}'):>6} / {num(r.p75, '{:.0f}'):>6}   (NVIDIA at {num(r.nvda_multiple)}x)")
    g = rd(OUT / "comps_regression.csv").iloc[0]
    say(f"  Growth vs NTM EV/revenue (5 peers): R2 {float(g['r2']):.3f}; NVIDIA {float(g['nvda_ev_revenue_ntm']):.1f}x vs "
        f"{float(g['fitted_ev_revenue_ntm']):.1f}x on the line -> {float(g['implied_price']):.2f} per share")
    b = rd(OUT / "comps_blend.csv").iloc[0]
    say(f"  Blend: {float(b['w_dcf']):.0%} DCF {float(b['dcf_weighted']):.2f} + {float(b['w_comps']):.0%} comps {float(b['comps_value']):.2f} = "
        f"{float(b['blended_value']):.2f} vs price {float(b['price']):.2f} ({float(b['upside']):+.1%})")
    say("  Football field:")
    for r in rd(OUT / "football_field.csv").itertuples():
        say(f"    {r.method:<28} {float(r.low):>7.0f} - {float(r.high):<7.0f} marker {float(r.point):.0f}")


def reconciliation():
    section("7. RECONCILIATION (all steps)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-rs", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 5):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def summary():
    section("9. STEP 7 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "Offline test suite passes", "T_offline"), ("T", "Step 7 runs: every error-level check passes", "T_pipeline"),
             ("T", "CSV outputs byte-identical on rerun", "T_repro"),
             ("V", "Calendarisation, EV bridge, exclusions, peer counts, blend weights, percentile order (C1-C6)", "V_checks"),
             ("V", "Workbook Comps equals Python (LibreOffice) - or MANUAL: compare in Excel", "V_excel"),
             ("V", "Inputs tie upstream, NTM EPS agrees with the second source, earlier references tie", "V_recon"),
             ("V", "Comps table, implied values, football field and blend reviewed", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 7 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M7 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
    m2.environment()
    m2.files()
    section("3. OFFLINE TESTS")
    code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    for x in tail(out, 25 if code else 3):
        say("  " + x)
    mark("T_offline", "PASS" if code == 0 and " passed" in out else "FAIL")
    pipeline()
    excel_check()
    review()
    reconciliation()
    m3.git()
    code, _ = run(["git", "check-ignore", "-q", "data/clean/step7/x"])
    if code != 0:
        mark("S_git", "FAIL")
    summary()
    report = OUT / "m7_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
