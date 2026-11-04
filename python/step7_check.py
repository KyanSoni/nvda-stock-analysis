"""Step 7c: check the workbook's Comps tab against python/step7_comps.py.

LibreOffice recalculates the workbook once (the Comps tab is always NVIDIA, so there is no ticker loop); then every
company's EV, NTM figures, multiples and in-statistics flags, the peer statistics, NVIDIA's implied values, the
regression and the blend are compared with Python (relative 1e-6). Without LibreOffice the check is SKIPPED: open the
workbook in Excel and compare the Comps tab's blended value with comps_blend.csv (MANUAL item in m7_acceptance.md).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from openpyxl import load_workbook

import step7_comps as c
from step5_check import find_soffice, recalc

ROW_ITEMS = ["ev", "w_fy0", "revenue_ntm", "growth_ntm", "ebitda_ntm", "eps_ntm", "eps_ltm"] + list(c.MULTIPLES)


def compare(workbook: Path, res: dict, tol=1e-6) -> list[tuple]:
    soffice = find_soffice()
    if not soffice:
        return [("X4_comps_excel_matches_python", None, "SKIPPED: LibreOffice not found; open the workbook in Excel and check the Comps tab's blended value")]
    wb0 = load_workbook(workbook)
    ws0 = wb0["Comps"]
    head = {ws0.cell(3, j).value: ws0.cell(3, j).column_letter for j in range(1, ws0.max_column + 1) if ws0.cell(3, j).value}
    rows = {ws0[f"A{r}"].value: r for r in range(5, 12) if ws0[f"A{r}"].value}
    codes = {ws0[f"A{r}"].value: r for r in range(1, ws0.max_row + 1) if ws0[f"A{r}"].value}
    with tempfile.TemporaryDirectory() as tmp:
        calc = load_workbook(recalc(soffice, workbook, Path(tmp)), data_only=True)["Comps"]
    bad, worst, n = [], 0.0, 0

    def cmp(label, xv, ev):
        nonlocal worst, n
        n += 1
        if ev is None or ev != ev:
            if xv not in ("n/m", "n/a", None, ""):
                bad.append(f"{label}: Excel {xv!r} vs Python none")
            return
        if not isinstance(xv, (int, float)):
            bad.append(f"{label}: Excel {xv!r} vs Python {ev}")
            return
        err = abs(xv - ev) / max(1.0, abs(ev))
        worst = max(worst, err)
        if err > tol:
            bad.append(f"{label}: Excel {xv} vs Python {ev}")
    tb = res["table"].set_index("ticker")
    for t, r in rows.items():
        for k in ROW_ITEMS:
            cmp(f"{t} {k}", calc[f"{head[k]}{r}"].value, tb.loc[t, k])
        for k in c.MULTIPLES:
            xv = calc[f"{head['use_' + k]}{r}"].value
            if int(xv or 0) != int(tb.loc[t, f"use_{k}"]):
                bad.append(f"{t} use_{k}: Excel {xv} vs Python {tb.loc[t, 'use_' + k]}")
    st = res["stats"].set_index("multiple")
    im = res["implied"].set_index("multiple")
    for k in c.MULTIPLES:
        for s in ("min", "p25", "p50", "p75", "max"):
            cmp(f"stat {k} {s}", calc[f"{head[k]}{codes['stat_' + s]}"].value, st.loc[k, s])
            cmp(f"implied {k} {s}", calc[f"{head[k]}{codes['imp_' + s]}"].value, im.loc[k, s])
    reg, bl = res["regression"], res["blend"]
    for code, ev in (("reg_slope", reg["slope"]), ("reg_intercept", reg["intercept"]), ("reg_r2", reg["r2"]),
                     ("reg_fit", reg["fitted_ev_revenue_ntm"]), ("reg_price", reg["implied_price"]), ("dcf_value", bl["dcf_weighted"]),
                     ("comps_value", bl["comps_value"]), ("blended", bl["blended_value"]), ("upside", bl["upside"])):
        cmp(code, calc[f"C{codes[code]}"].value, ev)
    detail = f"{n} values (6 companies x {len(ROW_ITEMS)} items, 6 multiples x 5 statistics and implied values, regression, blend); worst relative difference {worst:.2e}"
    return [("X4_comps_excel_matches_python", not bad, detail + ("; " + "; ".join(bad[:4]) if bad else ""))]
