"""Step 6c: check the workbook's WACC and DCF tabs against the Python DCF (step6_dcf) for every ticker and scenario.

Same method as step5_check: LibreOffice recalculates the workbook for each ticker x scenario; the WACC, unlevered FCF,
present values, value per share and exit cross-check are compared with Python (relative 1e-6), and the live WACC x g
grid for NVIDIA Base is compared with sensitivity_wacc_g.csv. Without LibreOffice the check is SKIPPED: open the
workbook in Excel and confirm the DCF tab shows OK in "live value equals Python" (MANUAL item in m6_acceptance.md).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

import step5_model as m
import step6_dcf as d
from build_model import FC
from step5_check import find_soffice, recalc

YEAR_ROWS = ["ufcf", "counted", "t", "df", "pv"]
CELLS = ["sum_pv", "tv", "pv_tv", "ev", "equity", "per_share", "tv_share", "implied_x", "per_share_exit"]
ENGINE = {"sum_pv": "pv_fcf", "implied_x": "implied_exit_multiple"}


def codes(ws) -> dict[str, int]:
    return {ws[f"A{r}"].value: r for r in range(1, ws.max_row + 1) if ws[f"A{r}"].value}


def compare(workbook: Path, md: pd.DataFrame, at: pd.DataFrame, inp: pd.DataFrame, wacc_g: pd.DataFrame, tol=1e-6) -> list[tuple]:
    soffice = find_soffice()
    if not soffice:
        return [("X3_dcf_excel_matches_python", None, "SKIPPED: LibreOffice not found; open the workbook in Excel, DCF tab must show OK (live value equals Python)")]
    wb0 = load_workbook(workbook)
    dc, wc = codes(wb0["DCF"]), codes(wb0["WACC"])
    worst, cases, fails = 0.0, 0, []
    grid_ok = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for t in sorted(md["ticker"].unique()):
            r = inp[inp["ticker"] == t].iloc[0].to_dict()
            _, h = m.history(md, t)
            for k, s in enumerate(["Bear", "Base", "Bull"], start=1):
                wb = load_workbook(workbook)
                wb["Cover"]["C5"], wb["Cover"]["C6"] = t, k
                src = tmp / "in" / f"dcf_{t}_{s}.xlsx"
                src.parent.mkdir(exist_ok=True)
                wb.save(src)
                calc = load_workbook(recalc(soffice, src, tmp / "out"), data_only=True)
                o = d.dcf(m.forecast(h, m.scenario(at, t, s)), r)
                bad = []

                def cmp(label, xv, ev):
                    nonlocal worst
                    if not isinstance(xv, (int, float)):
                        bad.append(f"{label}: {xv!r}")
                        return
                    err = abs(xv - ev) / max(1.0, abs(ev))
                    worst = max(worst, err)
                    if err > tol:
                        bad.append(f"{label}: Excel {xv} vs Python {ev}")
                cmp("WACC", calc["WACC"][f"C{wc['wacc']}"].value, float(o["wacc"]))
                for key in YEAR_ROWS:
                    for i, col in enumerate(FC):
                        cmp(f"DCF!{col} {key}", calc["DCF"][f"{col}{dc[key]}"].value, float(o[key][i]))
                for key in CELLS:
                    cmp(f"DCF {key}", calc["DCF"][f"C{dc[key]}"].value, float(o[ENGINE.get(key, key)]))
                for key in ("x1", "g_ok"):
                    if calc["DCF"][f"C{dc[key]}"].value != "OK":
                        bad.append(f"DCF {key} shows {calc['DCF'][f'C{dc[key]}'].value!r}")
                if t == "NVDA" and s == "Base":
                    g_row = calc["DCF"]
                    first = next(rr for rr in range(1, g_row.max_row + 1) if g_row[f"C{rr}"].value == "WACC \\ g") + 1
                    gb = []
                    for i, rw in enumerate(wacc_g.to_dict("records")):
                        for j, c in enumerate([c for c in wacc_g.columns if c.startswith("g_")]):
                            xv = g_row[f"{'DEFGH'[j]}{first + i}"].value
                            if not isinstance(xv, (int, float)) or abs(xv - float(rw[c])) / max(1.0, abs(float(rw[c]))) > tol:
                                gb.append(f"{rw['wacc']} {c}: {xv} vs {rw[c]}")
                    grid_ok = not gb
                    bad += gb[:3]
                cases += 1
                if bad:
                    fails.append(f"{t} {s}: {bad[:4]}")
    detail = (f"{cases} ticker x scenario cases; WACC, 5 rows x 5 years and {len(CELLS)} valuation cells each; "
              f"NVDA Base WACC x g grid {'matches' if grid_ok else 'DIFFERS'}; worst relative difference {worst:.2e}")
    return [("X3_dcf_excel_matches_python", not fails and bool(grid_ok), detail + ("; " + "; ".join(fails[:3]) if fails else ""))]


def engine_checks(md, at, inp, values) -> list[tuple]:
    return d.engine_checks(md, at, inp, values)

