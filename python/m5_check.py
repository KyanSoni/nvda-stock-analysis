"""Step 5 (M5) status check: runs every Step 5 check in one go and writes one report.

Usage (project folder, project venv; Steps 3 and 4 outputs present):
  & $vpy python\\m5_check.py
Rebuilds the model line items and the model (twice, to prove the CSV outputs are reproducible), checks the balance
sheet in every year for every company and scenario, compares the workbook with the Python model if LibreOffice is
installed, runs the offline and reconciliation tests, prints the NVIDIA forecast for review, checks Git readiness,
and writes data\\clean\\step5\\m5_check_report.txt. It never edits config, code, tests, references or raw data.
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
from common import PROJECT_ROOT

say, section, run, tail, mark = m2.say, m2.section, m2.run, m2.tail, m2.mark
M5_FILES = ["config/step5.yaml", "config/manual_facts_step5.csv", "config/model.yaml", "docs/m5_acceptance.md",
            "docs/evidence/m4_check_report_2026-11-03.txt", "excel/NVDA_Model.xlsx", "excel/NVDA_Forecast.xlsx",
            "python/step5_facts.py", "python/step5_model.py", "python/build_model.py", "python/step5_check.py",
            "python/run_step5.py", "python/m5_check.py",
            "tests/test_step5.py", "tests/test_reconciliation_step5.py", "tests/fixtures/reference_values_step5.csv"]
m2.PINNED["openpyxl"] = "3.1.5"      # added in Step 5 (I-56)
m2.EXPECTED_FILES = m2.M1_FILES + m2.M2_FILES + m3.M3_FILES + m4.M4_FILES + M5_FILES
OUT = PROJECT_ROOT / "data" / "clean" / "step5"
WB = PROJECT_ROOT / "excel" / "NVDA_Forecast.xlsx"


def pipeline():
    section("4. STEP 5 PIPELINE + REPRODUCIBILITY")
    import run_step5
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = run_step5.main(["all"])
    except Exception as exc:  # noqa: BLE001
        say(f"  Step 5 could not run: {type(exc).__name__}: {exc}")
        for k in ("T_pipeline", "T_repro"):
            mark(k, "FAIL")
        return
    for x in buf.getvalue().splitlines():
        if x.strip():
            say("  " + x.strip())
    mark("T_pipeline", "PASS" if code == 0 else "FAIL")
    man = json.loads((OUT / "manifest_all.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        with redirect_stdout(io.StringIO()):
            run_step5.main(["all", "--out", tmp, "--workbook", str(Path(tmp) / "wb.xlsx")])
        again = json.loads((Path(tmp) / "manifest_all.json").read_text(encoding="utf-8"))
    same = [again["output_sha256"].get(k) == v for k, v in man["output_sha256"].items()]
    say(f"  reproducibility: {sum(same)}/{len(same)} CSV outputs byte-identical on rerun (the workbook carries a save time, so it is checked by content below)")
    mark("T_repro", "PASS" if same and all(same) else "FAIL")


def excel_check():
    section("5. WORKBOOK vs PYTHON MODEL (LibreOffice recalculation, all tickers x scenarios)")
    import step5_check
    md = pd.read_csv(OUT / "model_data.csv", dtype=str, keep_default_na=False)
    at = pd.read_csv(OUT / "assumptions.csv", dtype=str, keep_default_na=False)
    res = step5_check.compare(WB, md, at)
    for c, ok, d in res:
        say(f"  {'MANUAL' if ok is None else 'PASS' if ok else 'FAIL'}  {c}: {d}")
    mark("V_excel", "MANUAL" if res[0][1] is None else "PASS" if res[0][1] else "FAIL")


def review():
    section("6. NVIDIA FORECAST REVIEW (for sign-off; nothing here changes data)")
    fc = pd.read_csv(OUT / "forecast.csv", dtype=str, keep_default_na=False)
    md = pd.read_csv(OUT / "model_data.csv", dtype=str, keep_default_na=False)
    last = md[(md["ticker"] == "NVDA")]["fiscal_year"].astype(int).max()
    yrs = [f"FY{last + k}E" for k in range(1, 6)]
    for s in ("Bear", "Base", "Bull"):
        x = fc[(fc["ticker"] == "NVDA") & (fc["scenario"] == s)].set_index("row")
        say(f"  {s}:")
        say("    " + f"{'':<22}" + "".join(f"{y:>12}" for y in yrs))
        for row, label, fmt in (("revenue", "Revenue $m", "{:,.0f}"), ("operating_income", "Operating income $m", "{:,.0f}"),
                                ("net_income", "Net income $m", "{:,.0f}"), ("eps", "Diluted EPS $", "{:,.2f}"),
                                ("fcf", "Free cash flow $m", "{:,.0f}"), ("balance_check", "Balance check", "{:,.6f}")):
            say("    " + f"{label:<22}" + "".join(f"{fmt.format(float(x.loc[row, f'y{k}'])):>12}" for k in range(1, 6)))
    est = pd.read_csv(PROJECT_ROOT / "data" / "clean" / "step4" / "estimates.csv", dtype=str, keep_default_na=False)
    e = est[est["ticker"] == "NVDA"].set_index(["kind", "period"])["avg"]
    b = fc[(fc["ticker"] == "NVDA") & (fc["scenario"] == "Base")].set_index("row")
    say("  Base vs consensus (Step 4 snapshot):")
    for k, p in ((1, "0y"), (2, "+1y")):
        say(f"    {yrs[k - 1]}: revenue {float(b.loc['revenue', f'y{k}']):,.0f} vs {float(e[('revenue', p)]) / 1e6:,.0f}; "
            f"EPS {float(b.loc['eps', f'y{k}']):.2f} vs {float(e[('eps', p)]):.2f} (consensus EPS is usually adjusted, I-47)")
    v = pd.read_csv(OUT / "validation_step5.csv", dtype=str, keep_default_na=False)
    say("  Warnings (peer history gaps, treated as 0 in the model and shown on the Cover tab):")
    for r in v[(v["level"] == "warning") & (v["passed"] != "True")].itertuples():
        say(f"    WARN {r.scope:<5} {r.detail[:150]}")
    errs = v[(v["level"] == "error") & (v["passed"] != "True")]
    mark("V_checks", "PASS" if errs.empty else "FAIL")


def reconciliation():
    section("7. RECONCILIATION (all steps: filing references, consensus anchor, workbook vs model)")
    code, out = run([sys.executable, "-m", "pytest", "-m", "reconciliation", "-q", "-rs", "-p", "no:cacheprovider"])
    for x in tail(out, 30 if code else 4):
        say("  " + x)
    mark("V_recon", "PASS" if code == 0 and " passed" in out else "FAIL")


def summary():
    section("9. STEP 5 ACCEPTANCE SUMMARY")
    items = [("T", "Environment, pins and lock file", "T_env"), ("T", "All expected files present", "T_files"),
             ("T", "Offline test suite passes", "T_offline"), ("T", "Step 5 pipeline: every error-level check passes", "T_pipeline"),
             ("T", "CSV outputs byte-identical on rerun", "T_repro"),
             ("V", "Balance sheet balances, 6 companies x 3 scenarios x 5 years (X2)", "V_checks"),
             ("V", "Workbook equals the Python model (LibreOffice) - or MANUAL: open in Excel", "V_excel"),
             ("V", "Filing references, consensus anchor and earlier references tie", "V_recon"),
             ("V", "Assumptions and forecast reviewed; workbook opened, ticker and scenario flipped", None),
             ("S", "Git identity set, no unexpected files, outputs ignored, no secrets", "S_git"),
             ("S", "Decisions accepted and Step 5 commit made", None)]
    for gate, label, key in items:
        say(f"  [{gate}] {m2.results.get(key, 'MANUAL') if key else 'MANUAL':<7} {label}")
    blocking = [label for _, label, key in items if key and m2.results.get(key) == "FAIL"]
    say("")
    say("  Outstanding before sign-off: " + ("; ".join(blocking) if blocking else "only the MANUAL items"))


def main() -> int:
    say(f"M5 CHECK REPORT {datetime.now(timezone.utc).isoformat(timespec='seconds')} project {PROJECT_ROOT}")
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
    code, _ = run(["git", "check-ignore", "-q", "data/raw/estimates/x"])
    if code != 0:
        mark("S_git", "FAIL")
    summary()
    report = OUT / "m5_check_report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(m2.lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {report}")
    return 0 if "FAIL" not in m2.results.values() else 1


if __name__ == "__main__":
    sys.exit(main())
