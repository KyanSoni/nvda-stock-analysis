"""Step 5c: check the Excel workbook against the Python model (step5_model) for every ticker and scenario.

Excel files written by openpyxl carry no calculated values, so the workbook is recalculated by LibreOffice
(headless) for each ticker x scenario, then every key row in every forecast year is compared with the Python engine
(relative 1e-6). If LibreOffice is not installed the check reports SKIPPED; open the workbook in Excel instead and
confirm Cover shows "OK" (MANUAL item in docs/m5_acceptance.md).
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import build_model as b
import step5_model as m


def find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    hits = glob.glob(r"C:\Program Files\LibreOffice\program\soffice.exe") + glob.glob(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe")
    return hits[0] if hits else None


def recalc(soffice: str, src: Path, dst_dir: Path) -> Path:
    """Open and re-save the workbook in LibreOffice, which calculates every formula."""
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    cmd = [soffice, f"-env:UserInstallation=file:///{profile.as_posix().lstrip('/')}", "--headless", "--calc",
           "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(dst_dir), str(src)]
    subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    out = dst_dir / src.name
    if not out.exists():
        raise RuntimeError(f"LibreOffice did not write {out}")
    return out


def row_numbers(path: Path) -> dict[tuple[str, str], int]:
    wb = load_workbook(path, read_only=False)
    rows = {}
    for sh in ("IS", "CF", "BS"):
        for r in range(1, wb[sh].max_row + 1):
            code = wb[sh][f"A{r}"].value
            if code:
                rows[(sh, code)] = r
    return rows


def compare(workbook: Path, md: pd.DataFrame, at: pd.DataFrame, tickers: list[str] | None = None, tol=1e-6) -> list[tuple]:
    soffice = find_soffice()
    if not soffice:
        return [("X1_excel_matches_python", None, "SKIPPED: LibreOffice not found; open the workbook in Excel and check Cover shows OK")]
    rows = row_numbers(workbook)
    results, worst, cases = [], 0.0, 0
    tickers = tickers or sorted(md["ticker"].unique())
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for t in tickers:
            years, h = m.history(md, t)
            for k, s in enumerate(["Bear", "Base", "Bull"], start=1):
                wb = load_workbook(workbook)
                wb["Cover"]["C5"], wb["Cover"]["C6"] = t, k
                src = tmp / "in" / f"case_{t}_{s}.xlsx"
                src.parent.mkdir(exist_ok=True)
                wb.save(src)
                calc = load_workbook(recalc(soffice, src, tmp / "out"), data_only=True)
                eng = m.forecast(h, m.scenario(at, t, s))
                bad = []
                for key, (sh, code) in b.ROW_MAP.items():
                    for i, col in enumerate(b.FC):
                        xv = calc[sh][f"{col}{rows[(sh, code)]}"].value
                        ev = float(eng[key][i])
                        if xv is None or isinstance(xv, str):
                            bad.append(f"{sh}!{col} {code}: {xv!r}")
                            continue
                        err = abs(xv - ev) / max(1.0, abs(ev)) if key != "balance_check" else abs(xv)
                        worst = max(worst, err)
                        if (key == "balance_check" and abs(xv) >= 0.5) or (key != "balance_check" and err > tol):
                            bad.append(f"{sh}!{col} {code}: Excel {xv} vs Python {ev}")
                status = calc["Cover"]["C24"].value if calc["Cover"]["B24"].value and "balances" in str(calc["Cover"]["B24"].value) else None
                cases += 1
                results.append((t, s, not bad, bad[:5], status))
    ok = all(r[2] for r in results)
    detail = f"{cases} ticker x scenario cases, {len(b.ROW_MAP)} rows x 5 years each; worst relative difference {worst:.2e}"
    fails = [f"{t} {s}: {bad}" for t, s, o, bad, _ in results if not o]
    return [("X1_excel_matches_python", ok, detail + ("; " + "; ".join(fails[:3]) if fails else ""))]


def engine_checks(md: pd.DataFrame, at: pd.DataFrame) -> list[tuple]:
    """Python engine only (no LibreOffice): balance in every year for every ticker and scenario; Base NVIDIA vs consensus."""
    worst, bad = Decimal(0), []
    for t in sorted(md["ticker"].unique()):
        _, h = m.history(md, t)
        for s in ("Bear", "Base", "Bull"):
            f = m.forecast(h, m.scenario(at, t, s))
            w = max(abs(x) for x in f["balance_check"])
            worst = max(worst, w)
            if w >= Decimal("0.5"):
                bad.append(f"{t} {s}")
    return [("X2_engine_balances_every_year", not bad, f"18 cases x 5 years; largest |assets - (liabilities + equity)| = {float(worst):.2e}; failing {bad or 'none'}")]
