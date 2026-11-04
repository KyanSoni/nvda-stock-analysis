"""Step 6 (M6) status check: runs every Step 6 check in one go and writes one report.

Usage (project folder, project venv; Steps 3, 4 and 5 outputs present):
  & $vpy python\\m6_check.py
Runs the DCF (twice, to prove the CSV outputs are reproducible), checks g < WACC, the scenario weights and the
unlevered FCF, compares the workbook's DCF with Python if LibreOffice is installed, runs the offline and
reconciliation tests, prints the NVIDIA valuation for review, checks Git readiness, and writes
data\\clean\\step6\\m6_check_report.txt. It never edits config, code, tests, references or raw data.
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
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M6_FILES = ["config/dcf.yaml", "docs/m6_acceptance.md", "python/step6_dcf.py", "python/build_dcf.py", "python/step6_check.py",
            "python/run_step6.py", "python/m6_check.py", "tests/test_step6.py", "tests/test_reconciliation_step6.py",
            "tests/fixtures/reference_values_step6.csv"]
EVIDENCE = sorted(p.relative_to(PROJECT_ROOT).as_posix() for p in (PROJECT_ROOT / "docs" / "evidence").glob("m*_check_report_*.txt"))
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + m3.M3_FILES + m4.M4_FILES + m5.M5_FILES + M6_FILES + EVIDENCE
OUT = PROJECT_ROOT / "data" / "clean" / "step6"
S5 = PROJECT_ROOT / "data" / "clean" / "step5"
WB = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


def pipeline():
    section("4. STEP 6 DCF + REPRODUCIBILITY")
    import run_step6
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step6.main([])
    except Exception as exc:  # noqa: BLE001
        say(f"  Step 6 could not run: {type(exc).__name__}: {exc}")
        for k in ("T_pipeline", "T_repro", "V_checks"):
            mark(k, "FAIL")
        return
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")
    man = json.loads((OUT / "manifest_step6.json").read_text(encoding="utf-8"))
    errs = [c for c in man["checks"] if c["level"] == "error" and not c["passed"]]
    mark("V_checks", "PASS" if not errs else "FAIL")
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step6.main(["--out", tmp, "--workbook", str(Path(tmp) / "wb.xlsx")])
        again = json.loads((Path(tmp) / "manifest_step6.json").read_text(encoding="utf-8"))
    same = [again["output_sha256"].get(k) == v for k, v in man["output_sha256"].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} CSV outputs byte-identical on rerun")
    mark("T_repro", "PASS" if same and all(same) else "FAIL")


def excel_check():
    section("5. WORKBOOK DCF vs PYTHON (LibreOffice recalculation, all tickers x scenarios)")
    import step6_check
    res = step6_check.compare(WB, rd(S5 / "model_data.csv"), rd(S5 / "assumptions.csv"), rd(OUT / "dcf_inputs.csv"),
                              rd(OUT / "sensitivity_wacc_g.csv"))
    for c, ok, dd in res:
        say(f"  {'MANUAL' if ok is None else 'PASS' if ok else 'FAIL'}  {c}: {dd}")
    mark("V_excel", "MANUAL" if res[0][1] is None else "PASS" if res[0][1] else "FAIL")


def review():
    section("6. NVIDIA VALUATION REVIEW (for sign-off; nothing here changes data)")
    i = rd(OUT / "dcf_inputs.csv").set_index("ticker")
    v = rd(OUT / "dcf_values.csv").set_index("ticker")
    n = i.loc["NVDA"]
    say(f"  WACC {float(n['wacc']):.2%} = cost of equity {float(n['cost_of_equity']):.2%} (rf {float(n['risk_free']):.2%} + beta "
        f"{float(n['beta_adjusted']):.3f} [raw {float(n['beta_raw']):.3f}] x ERP {float(n['erp']):.1%}); debt weight {float(n['debt_weight']):.2%}")
    say(f"  Valuation date {n['valuation_date']}; balance sheet {n['bs_date']}; year-1 share still to come {float(n['stub_fraction']):.1%}; "
        f"listed stakes {float(n['stakes']):,.0f}; diluted shares {float(n['diluted_shares']):,.0f}m")
    x = v.loc["NVDA"]
    for s in ("bear", "base", "bull"):
        say(f"    {s.title():<5} value/share {float(x[f'{s}_per_share']):>8.2f}  upside {float(x[f'{s}_upside']):>+7.1%}  TV share of EV "
            f"{float(x[f'{s}_tv_share']):.0%}  implied exit EV/EBITDA {float(x[f'{s}_implied_exit_multiple']):.1f}x  at peer multiple "
            f"{float(x[f'{s}_per_share_exit']):.2f}")
    say(f"    Weighted (25/50/25) {float(x['weighted_per_share']):.2f} vs price {float(x['price']):.2f} ({float(x['weighted_upside']):+.1%})")
    say("  Reverse DCF (Base, one lever at a time):")
    for r in rd(OUT / "reverse_dcf.csv").itertuples():
        say(f"    {r.lever:<22} model {float(r.model_value):.2%}  implied {(f'{float(r.implied_value):.2%}' if r.implied_value else r.status)}  {r.note}")
    say("  WACC x terminal growth (Base, value per share):")
    g = rd(OUT / "sensitivity_wacc_g.csv")
    say("    " + f"{'WACC':<8}" + "".join(f"{c.replace('g_', 'g '):>10}" for c in g.columns[1:]))
    for r in g.itertuples(index=False):
        say("    " + f"{float(r[0]):<8.1%}" + "".join(f"{float(c):>10.2f}" for c in r[1:]))
    say("  Peers (mechanical cases, S5-D6 / S6-D7; cross-check only):")
    for t, r in v.iterrows():
        say(f"    {t:<5} WACC {float(r['wacc']):.2%}  weighted {float(r['weighted_per_share']):>8.2f} vs {float(r['price']):>7.2f} "
            f"({float(r['weighted_upside']):+.0%})  {r['quality_flag']}")


def reconciliation():
    section("7. RECONCILIATION (all steps: filing references, consensus anchor, workbook vs model and DCF)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-rs", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 4):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def summary():
    section("9. STEP 6 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "Offline test suite passes", "T_offline"), ("T", "Step 6 runs: every error-level check passes", "T_pipeline"),
             ("T", "CSV outputs byte-identical on rerun", "T_repro"),
             ("V", "g < WACC, weights sum to 1, unlevered FCF recomputed, weighted within Bear-Bull (D1-D4)", "V_checks"),
             ("V", "Workbook DCF equals Python (LibreOffice) - or MANUAL: DCF tab shows OK in Excel", "V_excel"),
             ("V", "10-Q references, beta inputs and earlier references tie", "V_recon"),
             ("V", "WACC, valuation, sensitivities and reverse DCF reviewed", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 6 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M6 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
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
    code, _ = run(["git", "check-ignore", "-q", "data/clean/step6/x"])
    if code != 0:
        mark("S_git", "FAIL")
    summary()
    report = OUT / "m6_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
