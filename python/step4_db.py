"""Step 4b: add the scorecard tables and views to the Step 3 PostgreSQL schema, check them and export them.

  1. write load files      data/clean/step4/load/*.csv (rules and assumptions from config/scorecard.yaml; estimates)
  2. sql/step4_schema.sql  (re)create the Step 4 tables inside the Step 3 schema
  3. load                  psql \\copy, row counts and hashes added to load_manifest
  4. sql/scorecard.sql     beta, WACC, PEG and scorecard views
  5. sql/step4_checks.sql  in-database checks SC1-SC5
  6. export                every Step 4 view to data/clean/step4/exports/*.csv
Requires the Step 3 schema (run_step3.py db), which it never changes.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step3_db as db
import step4_estimates as est
from common import write_csv, sha256_file

SQL = db.SQL
TABLE_COLUMNS = {
    "scorecard_rules": ["test_no", "name", "metric", "direction", "pass_value", "near_value", "fail_when_null"],
    "scorecard_params": ["key", "value", "note"],
    "estimates": est.COLUMNS,
}
EXPORTS = {"v_beta": "ticker, benchmark", "v_wacc": "ticker", "v_peg": "ticker",
           "v_scorecard_detail": "ticker, test_no", "v_scorecard": "ticker"}


def write_load_files(load: Path, sc: dict, estimates_csv: Path) -> dict[str, Path]:
    load.mkdir(parents=True, exist_ok=True)
    rules = [{"test_no": n, "name": t["name"], "metric": t["metric"], "direction": t["direction"],
              "pass_value": t["pass"], "near_value": t["near"], "fail_when_null": t.get("fail_when_null", "")}
             for n, t in sc["tests"].items()]
    params = [{"key": "equity_risk_premium", "value": sc["wacc"]["equity_risk_premium"], "note": "analyst assumption (S4-D5)"},
              {"key": "beta_months", "value": sc["wacc"]["months"], "note": "monthly returns in the beta window (S4-D4)"}]
    files = {"scorecard_rules": load / "scorecard_rules.csv", "scorecard_params": load / "scorecard_params.csv",
             "estimates": load / "estimates.csv"}
    write_csv(pd.DataFrame(rules, columns=TABLE_COLUMNS["scorecard_rules"]), files["scorecard_rules"], ["test_no"])
    write_csv(pd.DataFrame(params, columns=TABLE_COLUMNS["scorecard_params"]), files["scorecard_params"], ["key"])
    e = pd.read_csv(estimates_csv, dtype=str, keep_default_na=False)
    write_csv(e[TABLE_COLUMNS["estimates"]], files["estimates"], ["ticker", "kind", "period"])
    return files


def load_script(cfg: dict, files: dict[str, Path]) -> str:
    schema = cfg["schema"]
    lines = ["\\set ON_ERROR_STOP on", f'SET search_path = "{schema}";']
    for table, path in files.items():
        cols = ", ".join(TABLE_COLUMNS[table])
        lines.append(f"\\copy \"{schema}\".{table} ({cols}) FROM '{path.resolve().as_posix()}' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')")
    for table, path in files.items():
        with open(path, encoding="utf-8", newline="") as fh:
            n = sum(1 for _ in csv.reader(fh)) - 1
        lines.append(f"INSERT INTO load_manifest VALUES ('{table}', '{path.name}', '{sha256_file(path)}', {n});")
    return "\n".join(lines) + "\n"


def build(out: Path, sc: dict) -> bool:
    cfg = db.load_db_config()
    load, exports = out / "load", out / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    code, has, err = db.run_psql(cfg, ["-tA", "-c", f"SELECT to_regclass('\"{cfg['schema']}\".v_valuation_cutoff') IS NOT NULL"])
    if code or has.strip() != "t":
        print(f"  Step 3 schema not found ({err.strip() or 'v_valuation_cutoff missing'}): run  python python/run_step3.py db  first")
        return False
    files = write_load_files(load, sc, out / "estimates.csv")
    for name, args, stdin in [("schema", ["-f", str(SQL / "step4_schema.sql")], None),
                              ("load", [], load_script(cfg, files)),
                              ("views", ["-f", str(SQL / "scorecard.sql")], None)]:
        code, _, err = db.run_psql(cfg, args, stdin)
        if code:
            print(f"  FAILED at {name}: {err.strip()}")
            return False
        print(f"  {name}: ok")
    code, text, err = db.run_psql(cfg, ["--csv", "-f", str(SQL / "step4_checks.sql")])
    if code:
        print(f"  FAILED at checks: {err.strip()}")
        return False
    checks = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    checks["passed"] = checks["passed"].map({"t": "True", "f": "False"}).fillna(checks["passed"])
    write_csv(checks, out / "db_checks_step4.csv", ["check"])
    for view, order in EXPORTS.items():
        path = (exports / f"{view}.csv").resolve().as_posix()
        code, _, err = db.run_psql(cfg, ["-c", f"\\copy (SELECT * FROM \"{cfg['schema']}\".{view} ORDER BY {order}) TO '{path}' WITH (FORMAT csv, HEADER true)"])
        if code:
            print(f"  FAILED exporting {view}: {err.strip()}")
            return False
    print(f"  exports: {len(EXPORTS)} views -> {exports}")
    for r in checks.itertuples():
        print(f"  {'PASS' if r.passed == 'True' else 'FAIL'}  {r.check}: {r.detail}")
    ok = bool((checks["passed"] == "True").all())
    manifest = {"stage": "db", "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "load_files_sha256": {k: sha256_file(v) for k, v in files.items()},
                "exports_sha256": {p.name: sha256_file(p) for p in sorted(exports.glob("*.csv"))}, "checks_passed": ok}
    (out / "db_manifest_step4.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return ok
