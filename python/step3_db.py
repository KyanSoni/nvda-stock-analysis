"""Step 3b: build the PostgreSQL database from the Step 2 and Step 3a outputs, using psql (no Python driver).

  1. write load files      data/clean/step3/load/*.csv   (exact table column order, deterministic)
  2. sql/schema.sql        drop and recreate the schema (config/database.yaml: schema)
  3. load                  psql \\copy every load file, record row counts and hashes in load_manifest
  4. sql/views.sql         create the analytical views
  5. sql/checks.sql        in-database integrity checks
  6. export                every view and saved query to data/clean/step3/exports/*.csv (ordered, deterministic)
"""
from __future__ import annotations

import csv
import glob
import io
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from common import PROJECT_ROOT, load_config, sha256_file, write_csv

DB_CFG = PROJECT_ROOT / "config" / "database.yaml"
SQL = PROJECT_ROOT / "sql"
TABLE_COLUMNS = {
    "companies": ["ticker", "cik", "role", "fy_end_month", "sec_name"],
    "line_items": ["line_item", "statement", "period_type", "unit", "introduced_in", "support_item"],
    "facts": ["ticker", "line_item", "fiscal_year", "fiscal_period", "value_basis", "period_start", "period_end", "value",
              "unit", "display_value", "display_unit", "concept", "accn", "form", "filed", "restated", "original_value",
              "original_accn", "derived_from_accns", "transformation", "entity_cik", "support_item", "split_factor",
              "value_split_adjusted", "display_split_adjusted", "snapshot_sha256"],
    "split_factors": ["ticker", "split_date", "ratio"],
    "prices": ["ticker", "price_date", "open", "high", "low", "close", "adj_close", "volume", "dividend", "split_ratio",
               "close_as_traded", "source_file", "source_sha256"],
    "market_inputs": ["ticker", "cutoff_date", "close", "close_2dp", "shares_outstanding", "shares_as_of", "shares_accn",
                      "shares_form", "shares_filed", "market_cap_usd", "market_cap_basis", "price_source",
                      "yfinance_shares_crosscheck", "shares_diff_pct"],
}
EXPORTS = {   # view -> ORDER BY
    "v_annual": "ticker, fiscal_year",
    "v_quarterly": "ticker, period_end",
    "v_ltm": "ticker, period_end",
    "v_ratios_annual": "ticker, fiscal_year",
    "v_ratios_ltm": "ticker, period_end",
    "v_valuation_cutoff": "ticker",
    "v_peer_summary": "ticker",
}
QUERIES = ["q1_highest_3y_avg_roe", "q2_gross_margin_vs_peer_median", "q3_nvda_fcf_vs_net_income"]


# ---------------------------------------------------------------- connection

def load_db_config(path: Path = DB_CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def find_psql(cfg: dict) -> str:
    if cfg.get("psql") and cfg["psql"] != "auto":
        return cfg["psql"]
    found = shutil.which("psql")
    if found:
        return found
    candidates = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\psql.exe")
    if candidates:
        def version(p):
            m = re.search(r"PostgreSQL\\(\d+)", p)
            return int(m.group(1)) if m else 0
        return max(candidates, key=version)
    raise FileNotFoundError("psql not found: add PostgreSQL's bin folder to PATH or set psql: in config/database.yaml")


def psql_env(cfg: dict) -> dict:
    env = dict(os.environ)
    for key, var in (("host", "PGHOST"), ("port", "PGPORT"), ("dbname", "PGDATABASE"), ("user", "PGUSER")):
        env.setdefault(var, str(cfg[key]))
    env["PGCLIENTENCODING"] = "UTF8"
    return env


def run_psql(cfg: dict, args: list[str], stdin: str | None = None, timeout: int = 1800) -> tuple[int, str, str]:
    cmd = [find_psql(cfg), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-v", f"schema={cfg['schema']}"] + args
    p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=psql_env(cfg), timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def query_csv(cfg: dict, sql: str) -> pd.DataFrame:
    code, out, err = run_psql(cfg, ["--csv", "-c", sql])
    if code:
        raise RuntimeError(err.strip())
    return pd.read_csv(io.StringIO(out), dtype=str, keep_default_na=False)


# ---------------------------------------------------------------- load files

def write_load_files(load: Path) -> dict[str, Path]:
    import step3_facts as s3f
    from run_step2 import load_universe
    uni, base, s3 = load_universe(), load_config(), s3f.load_step3()
    step2 = PROJECT_ROOT / uni["paths"]["step2_out"]
    step3 = PROJECT_ROOT / s3["paths"]["step3_out"]
    load.mkdir(parents=True, exist_ok=True)
    files = {}

    ident = pd.read_csv(step2 / "identity_report.csv", dtype=str, keep_default_na=False)
    names = dict(zip(ident.loc[ident["role"] == "current", "ticker"], ident.loc[ident["role"] == "current", "sec_name"]))
    rows = [{"ticker": t, "cik": s["cik"], "role": s["role"], "fy_end_month": s["fy_end_month"], "sec_name": names.get(t, "")}
            for t, s in uni["companies"].items()]
    rows += [{"ticker": b, "cik": "", "role": "benchmark", "fy_end_month": "", "sec_name": ""} for b in uni["benchmarks"]]
    files["companies"] = load / "companies.csv"
    write_csv(pd.DataFrame(rows, columns=TABLE_COLUMNS["companies"]), files["companies"], ["ticker"])

    li = []
    for name, spec in base["line_items"].items():
        li.append([name, spec["statement"], spec["period_type"], spec["unit"], "M1", False])
    for name, spec in uni["support_items"].items():
        li.append([name, spec["statement"], spec["period_type"], spec["unit"], "Step2", True])
    for name, spec in s3["line_items"].items():
        li.append([name, spec["statement"], spec["period_type"], spec["unit"], "Step3", False])
    for name, spec in s3["support_items"].items():
        li.append([name, spec["statement"], spec["period_type"], spec["unit"], "Step3", True])
    files["line_items"] = load / "line_items.csv"
    write_csv(pd.DataFrame(li, columns=TABLE_COLUMNS["line_items"]), files["line_items"], ["line_item"])

    facts = pd.read_csv(step3 / "facts_extended.csv", dtype=str, keep_default_na=False)
    files["facts"] = load / "facts.csv"
    write_csv(facts[TABLE_COLUMNS["facts"]], files["facts"], ["ticker", "line_item", "period_end", "period_start", "value_basis"])

    sf = pd.read_csv(step3 / "split_factors.csv", dtype=str, keep_default_na=False).rename(columns={"date": "split_date"})
    files["split_factors"] = load / "split_factors.csv"
    write_csv(sf[TABLE_COLUMNS["split_factors"]], files["split_factors"], ["ticker", "split_date"])

    pr = pd.read_csv(step2 / "market" / "prices.csv", dtype=str, keep_default_na=False).rename(columns={"date": "price_date"})
    files["prices"] = load / "prices.csv"
    write_csv(pr[TABLE_COLUMNS["prices"]], files["prices"], ["ticker", "price_date"])

    mi = pd.read_csv(step2 / "market" / "market_inputs.csv", dtype=str, keep_default_na=False)
    for c in TABLE_COLUMNS["market_inputs"]:
        if c not in mi.columns:
            mi[c] = ""
    mi.loc[mi["ticker"] == "RISK_FREE_10Y", "shares_as_of"] = ""   # that column holds the observation date there
    files["market_inputs"] = load / "market_inputs.csv"
    write_csv(mi[TABLE_COLUMNS["market_inputs"]], files["market_inputs"], ["ticker"])
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


# ---------------------------------------------------------------- build

def build(out: Path) -> bool:
    cfg = load_db_config()
    load, exports = out / "load", out / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    print(f"Step 3b database: {cfg['user']}@{psql_env(cfg)['PGHOST']}:{psql_env(cfg)['PGPORT']}/{psql_env(cfg)['PGDATABASE']} schema {cfg['schema']}")
    code, ver, err = run_psql(cfg, ["-tA", "-c", "SHOW server_version_num"])
    if code:
        print(f"  Cannot connect: {err.strip()}")
        return False
    server = int(ver.strip())
    if server < cfg["min_server_version"] * 10000:
        print(f"  PostgreSQL server {server} is older than {cfg['min_server_version']}")
        return False
    files = write_load_files(load)
    steps = [("schema", ["-f", str(SQL / "schema.sql")], None),
             ("load", [], load_script(cfg, files)),
             ("views", ["-f", str(SQL / "views.sql")], None)]
    for name, args, stdin in steps:
        code, _, err = run_psql(cfg, args, stdin)
        if code:
            print(f"  FAILED at {name}: {err.strip()}")
            return False
        print(f"  {name}: ok")
    code, out_checks, err = run_psql(cfg, ["--csv", "-f", str(SQL / "checks.sql")])
    if code:
        print(f"  FAILED at checks: {err.strip()}")
        return False
    checks = pd.read_csv(io.StringIO(out_checks), dtype=str, keep_default_na=False)
    checks["passed"] = checks["passed"].map({"t": "True", "f": "False"}).fillna(checks["passed"])
    write_csv(checks, out / "db_checks.csv", ["check"])
    for view, order in EXPORTS.items():
        path = (exports / f"{view}.csv").resolve().as_posix()
        code, _, err = run_psql(cfg, ["-c", f"\\copy (SELECT * FROM \"{cfg['schema']}\".{view} ORDER BY {order}) TO '{path}' WITH (FORMAT csv, HEADER true)"])
        if code:
            print(f"  FAILED exporting {view}: {err.strip()}")
            return False
    for q in QUERIES:
        code, text, err = run_psql(cfg, ["--csv", "-f", str(SQL / "queries" / f"{q}.sql")])
        if code:
            print(f"  FAILED running {q}: {err.strip()}")
            return False
        (exports / f"{q}.csv").write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(f"  exports: {len(EXPORTS)} views and {len(QUERIES)} queries -> {exports}")
    ok = (checks["passed"] == "True").all()
    for r in checks.itertuples():
        print(f"  {'PASS' if r.passed == 'True' else 'FAIL'}  {r.check}: {r.detail}")
    _, psql_ver, _ = run_psql(cfg, ["--version"])
    manifest = {"stage": "db", "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "server_version_num": server, "psql": psql_ver.strip(), "schema": cfg["schema"],
                "load_files_sha256": {k: sha256_file(v) for k, v in files.items()},
                "exports_sha256": {p.name: sha256_file(p) for p in sorted(exports.glob("*.csv"))},
                "checks_passed": bool(ok)}
    (out / "db_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return bool(ok)
