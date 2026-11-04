"""Step 7b: add the Comps and CompsData tabs to excel/NVDA_Forecast.xlsx (called by build_model.build).

Comps is always about NVIDIA (the target), whatever ticker the Cover switch shows. Every multiple, statistic, implied
value, the regression and the blend are live formulas; the only typed numbers are on CompsData (blue, written from
data/clean/step7/comps_table.csv). Two charts: the football field and NTM growth vs NTM EV/revenue.
"""
from __future__ import annotations

from datetime import date

from openpyxl.chart import BarChart, Reference, ScatterChart, Series
from openpyxl.chart.trendline import Trendline

from build_model import BLUE, EPS, GREEN, GREY, HEAD_FILL, KEY_FILL, MONEY, PCT, f

X = '0.0"x"'
INPUTS = ["price", "diluted_shares", "market_cap", "debt", "cash", "st_investments", "stakes", "fy0_end", "revenue_fy0", "revenue_fy1",
          "revenue_ltm", "gross_margin_ltm", "ebitda_ltm", "eps_fy0", "eps_fy1", "net_income_ltm", "low_52w", "high_52w"]
CELLS: dict[str, str] = {}   # code -> cell address on the Comps tab (read by step7_check)


def add(wb, payload: dict) -> None:
    tb, cfg, foot = payload["table"], payload["cfg"], payload["football"]
    names = wb.sheetnames
    ws = wb.create_sheet("Comps", names.index("Data"))
    cd = wb.create_sheet("CompsData")
    order = [cfg["target"]] + sorted(t for t in tb["ticker"] if t != cfg["target"])
    rows = {r["ticker"]: r for r in tb.to_dict("records")}

    # ---------------- CompsData (inputs)
    cd.append(["ticker", "role"] + INPUTS + ["ebitda_basis"])
    for t in order:
        r = rows[t]
        vals = []
        for k in INPUTS:
            v = r[k]
            vals.append(date.fromisoformat(v) if k == "fy0_end" else ("n/a" if v is None or v != v else float(v)))
        cd.append([t, r["role"]] + vals + [r["ebitda_basis"]])
    for row in cd.iter_rows(min_row=2, min_col=3, max_col=2 + len(INPUTS)):
        for c in row:
            c.font = f(BLUE)
            if c.column == 3 + INPUTS.index("fy0_end"):
                c.number_format = "yyyy-mm-dd"
    vd = 2 + len(order) + 2
    cd[f"A{vd}"], cd[f"C{vd}"] = "valuation_date", date.fromisoformat(payload["valuation_date"])
    cd[f"C{vd}"].number_format = "yyyy-mm-dd"
    cd[f"C{vd}"].font = f(BLUE)
    cd[f"A{vd + 1}"], cd[f"C{vd + 1}"] = "year_days", float(cfg["ntm"]["year_days"])
    cd[f"A{vd + 2}"], cd[f"C{vd + 2}"] = "max_multiple", float(cfg["exclusions"]["max_multiple"])
    cd[f"A{vd + 3}"], cd[f"C{vd + 3}"] = "w_dcf", float(cfg["blend"]["dcf"])
    cd[f"A{vd + 4}"], cd[f"C{vd + 4}"] = "w_comps", float(cfg["blend"]["comps"])
    for k in range(5):
        cd[f"C{vd + k}"].font = f(BLUE)
    cd["X1"] = ("Source: data/clean/step7/comps_table.csv (python/step7_comps.py from Step 3 v_valuation_cutoff and v_ratios_ltm, "
                "Step 4 consensus, Step 6 dcf_inputs, Step 2 prices) and config/comps.yaml. Do not edit.")
    cd["X1"].font = f(GREY, italic=True, size=9)
    ic = {k: 3 + i for i, k in enumerate(INPUTS)}
    from openpyxl.utils import get_column_letter as L
    src = lambda k, i: f"=CompsData!{L(ic[k])}{i + 2}"  # noqa: E731
    VDATE, YDAYS, MAXM, WD, WC = (f"CompsData!$C${vd + k}" for k in range(5))

    # ---------------- Comps table
    ws["A1"], ws["A1"].font = "Comparable companies: NVIDIA against its five peers at the valuation cutoff (USD millions; NTM calendarised)", f(bold=True, size=12)
    ws["A2"] = ("Always NVIDIA, whatever the Cover ticker. Peer statistics exclude NVIDIA and any multiple above 100x, with a zero or negative "
                "denominator, or on a fiscal-year EBITDA (AMD, S3-D11); excluded values stay visible, marked 0 in the 'in stats' columns.")
    ws["A2"].font = f(GREY, italic=True, size=9)
    cols = [("ticker", "Ticker", None, None), ("role", "Role", None, None),
            ("price", "Price", "in", EPS), ("diluted_shares", "Diluted shares (m)", "in", MONEY), ("market_cap", "Market cap", "in", MONEY),
            ("debt", "Debt", "in", MONEY), ("cash", "Cash", "in", MONEY), ("st_investments", "Short-term investments", "in", MONEY),
            ("stakes", "Listed stakes", "in", MONEY), ("net_debt", "Net debt", "=F{r}-G{r}-H{r}", MONEY),
            ("ev", "Enterprise value (mcap + net debt - stakes)", "=E{r}+J{r}-I{r}", MONEY),
            ("fy0_end", "Current fiscal year ends", "in", "yyyy-mm-dd"),
            ("w_fy0", "Weight on current year (NTM)", f"=MAX(0,MIN(1,(L{{r}}-{VDATE})/{YDAYS}))", "0.000"),
            ("revenue_fy0", "Revenue, current FY (consensus)", "in", MONEY), ("revenue_fy1", "Revenue, next FY (consensus)", "in", MONEY),
            ("revenue_ntm", "Revenue, NTM", "=M{r}*N{r}+(1-M{r})*O{r}", MONEY), ("revenue_ltm", "Revenue, LTM", "in", MONEY),
            ("growth_ntm", "Revenue growth, NTM vs LTM", "=P{r}/Q{r}-1", PCT), ("gross_margin_ltm", "Gross margin, LTM", "in", PCT),
            ("ebitda_ltm", "EBITDA, LTM", "in", MONEY), ("ebitda_margin_ltm", "EBITDA margin, LTM", '=IF(ISNUMBER(T{r}),T{r}/Q{r},"n/a")', PCT),
            ("ebitda_ntm", "EBITDA, NTM (NTM revenue x LTM margin)", '=IF(ISNUMBER(U{r}),P{r}*U{r},"n/a")', MONEY),
            ("eps_fy0", "EPS, current FY (consensus)", "in", EPS), ("eps_fy1", "EPS, next FY (consensus)", "in", EPS),
            ("eps_ntm", "EPS, NTM", "=M{r}*W{r}+(1-M{r})*X{r}", EPS), ("net_income_ltm", "Net income, LTM (GAAP)", "in", MONEY),
            ("eps_ltm", "EPS, LTM (GAAP, net income / diluted shares)", "=Z{r}/D{r}", EPS),
            ("low_52w", "52-week low (close)", "in", EPS), ("high_52w", "52-week high (close)", "in", EPS)]
    mult = [("ev_revenue_ntm", "EV / revenue NTM", "K", "P"), ("ev_ebitda_ntm", "EV / EBITDA NTM", "K", "V"),
            ("pe_ntm", "P / E NTM", "C", "Y"), ("ev_revenue_ltm", "EV / revenue LTM", "K", "Q"),
            ("ev_ebitda_ltm", "EV / EBITDA LTM", "K", "T"), ("pe_ltm", "P / E LTM", "C", "AA")]
    hdr, first = 4, 5
    last = first + len(order) - 1
    letters = {}
    for j, (code, label, _, _) in enumerate(cols):
        letters[code] = L(1 + j)
    base = len(cols)
    for j, (code, *_r) in enumerate(mult):
        letters[code] = L(base + 1 + j)
        letters["use_" + code] = L(base + 1 + len(mult) + j)
        letters["stat_" + code] = L(base + 1 + 2 * len(mult) + j)
    for code, label, *_ in cols:
        ws[f"{letters[code]}{hdr}"] = label
    for code, label, *_ in mult:
        ws[f"{letters[code]}{hdr}"] = label
        ws[f"{letters['use_' + code]}{hdr}"] = f"In stats: {label}"
        ws[f"{letters['stat_' + code]}{hdr}"] = f"Stats value: {label}"
    for c in ws[hdr]:
        if c.value:
            c.font = f(bold=True, size=9)
            c.fill = HEAD_FILL
    ws["A3"] = "code"
    ws["A3"].font = f(GREY, size=8)
    for code in [c[0] for c in cols + mult] + [f"{p}_{m[0]}" for p in ("use", "stat") for m in mult]:
        ws[f"{letters[code]}3"] = code
        ws[f"{letters[code]}3"].font = f(GREY, size=8)
    for i, t in enumerate(order):
        r = first + i
        for code, label, how, fmt in cols:
            cell = ws[f"{letters[code]}{r}"]
            if code in ("ticker", "role"):
                cell.value = t if code == "ticker" else rows[t]["role"]
                cell.font = f(bold=t == cfg["target"])
                continue
            if how == "in":
                cell.value = src(code, i)
                cell.font = f(GREEN)
            else:
                cell.value = how.format(r=r)
            cell.number_format = fmt
        for code, label, num, den in mult:
            ws[f"{letters[code]}{r}"] = f'=IF(AND(ISNUMBER({den}{r}),N({den}{r})>0),{num}{r}/{den}{r},"n/m")'
            ws[f"{letters[code]}{r}"].number_format = X
            ws[f"{letters[code]}{r}"].font = f(bold=True)
            ws[f"{letters['use_' + code]}{r}"] = (f'=IF(AND(B{r}<>"target",ISNUMBER({letters[code]}{r})),'
                                                  f'IF(N({letters[code]}{r})<={MAXM},1,0),0)')
            ws[f"{letters['stat_' + code]}{r}"] = f'=IF({letters["use_" + code]}{r}=1,{letters[code]}{r},"")'
            ws[f"{letters['stat_' + code]}{r}"].number_format = X
        if t == cfg["target"]:
            for c in ws[r]:
                if c.value is not None:
                    c.fill = KEY_FILL
    for code in letters:
        CELLS[code] = letters[code]
    CELLS["first_row"], CELLS["last_row"] = str(first), str(last)

    # ---------------- statistics
    s0 = last + 2
    ws[f"B{s0}"], ws[f"B{s0}"].font = "Peer statistics (NVIDIA and excluded values left out)", f(bold=True)
    stat_rows = [("min", "Minimum", "MIN({rng})"), ("p25", "25th percentile", "PERCENTILE({rng},0.25)"), ("p50", "Median", "MEDIAN({rng})"),
                 ("p75", "75th percentile", "PERCENTILE({rng},0.75)"), ("max", "Maximum", "MAX({rng})"), ("n", "Peers in the statistic", "COUNT({rng})")]
    for k, (code, label, fx) in enumerate(stat_rows):
        r = s0 + 1 + k
        ws[f"A{r}"], ws[f"B{r}"] = f"stat_{code}", label
        ws[f"A{r}"].font = f(GREY, size=8)
        for mcode, *_ in mult:
            sl = letters["stat_" + mcode]
            cell = ws[f"{letters[mcode]}{r}"]
            cell.value = "=" + fx.format(rng=f"{sl}${first}:{sl}${last}")
            cell.number_format = "0" if code == "n" else X
        CELLS[f"stat_{code}"] = str(r)
    nv = first   # NVIDIA's row

    # ---------------- implied values for NVIDIA
    i0 = s0 + len(stat_rows) + 2
    ws[f"B{i0}"], ws[f"B{i0}"].font = "NVIDIA value per share implied by the peer statistics (EV multiples via the Step 6 bridge)", f(bold=True)
    ws[f"B{i0 + 1}"], ws[f"B{i0 + 2}"] = "NVIDIA metric the multiple is applied to", "NVIDIA's own multiple"
    bridge = f"($G${nv}+$H${nv}+$I${nv}-$F${nv})"
    for mcode, label, num, den in mult:
        col = letters[mcode]
        ws[f"{col}{i0 + 1}"] = f"={den}{nv}"
        ws[f"{col}{i0 + 1}"].number_format = EPS if num == "C" else MONEY
        ws[f"{col}{i0 + 2}"] = f"={col}{nv}"
        ws[f"{col}{i0 + 2}"].number_format = X
    for k, (code, label, _) in enumerate(stat_rows[:5]):
        r = i0 + 3 + k
        ws[f"A{r}"], ws[f"B{r}"] = f"imp_{code}", f"Value per share at the peer {label.lower()}"
        ws[f"A{r}"].font = f(GREY, size=8)
        for mcode, label2, num, den in mult:
            col = letters[mcode]
            st = f"{col}{CELLS['stat_' + code]}"
            ws[f"{col}{r}"] = f"={st}*{col}{i0 + 1}" if num == "C" else f"=({st}*{col}{i0 + 1}+{bridge})/$D${nv}"
            ws[f"{col}{r}"].number_format = EPS
            if code == "p50":
                ws[f"{col}{r}"].font = f(bold=True)
        CELLS[f"imp_{code}"] = str(r)

    # ---------------- regression, blend, football field (columns B-F)
    g0 = i0 + 9
    gx, gy = letters["growth_ntm"], letters["ev_revenue_ntm"]
    pr = lambda c: f"{c}{first + 1}:{c}{last}"  # noqa: E731  peers only (NVIDIA is the first row)
    items = [("sec", "Growth vs multiple: peers' NTM EV/revenue on NTM revenue growth (least squares, 5 points: indicative only)", None, None),
             ("reg_slope", "Slope (x per 100% growth)", f"=SLOPE({pr(gy)},{pr(gx)})", "0.00"),
             ("reg_intercept", "Intercept", f"=INTERCEPT({pr(gy)},{pr(gx)})", "0.00"),
             ("reg_r2", "R squared", f"=RSQ({pr(gy)},{pr(gx)})", "0.000"),
             ("reg_fit", "NVIDIA's multiple on the line", f"=C{{reg_intercept}}+C{{reg_slope}}*{gx}{nv}", X),
             ("reg_actual", "NVIDIA's actual NTM EV/revenue", f"={gy}{nv}", X),
             ("reg_price", "Value per share at the line", f"=(C{{reg_fit}}*P{nv}+{bridge})/D{nv}", EPS),
             ("sec2", "Blend (S7-D6): the value Step 9 turns into a 12-month target", None, None),
             ("dcf_value", "DCF: probability-weighted value per share (Step 6)",
              '=INDEX(DcfData!$A:$Z,MATCH("NVDA",DcfData!$A:$A,0),MATCH("py_weighted",DcfData!$1:$1,0))', EPS),
             ("comps_value", "Comps: mean of values at the peer median NTM P/E and NTM EV/EBITDA",
              f"=AVERAGE({letters['pe_ntm']}{CELLS['imp_p50']},{letters['ev_ebitda_ntm']}{CELLS['imp_p50']})", EPS),
             ("w_dcf", "Weight on DCF", f"={WD}", PCT), ("w_comps", "Weight on comps", f"={WC}", PCT),
             ("blended", "Blended value per share", "=C{w_dcf}*C{dcf_value}+C{w_comps}*C{comps_value}", EPS),
             ("price", "Price at the cutoff", f"=C{nv}", EPS), ("upside", "Upside / (downside) to the blended value", "=C{blended}/C{price}-1", PCT)]
    for k, (code, *_r) in enumerate(items):
        CELLS[code] = str(g0 + k)
    for code, label, fx, fmt in items:
        r = int(CELLS[code])
        ws[f"B{r}"] = label
        ws[f"B{r}"].font = f(bold=code.startswith("sec") or code in ("blended", "comps_value"))
        if fx:
            ws[f"A{r}"] = code
            ws[f"A{r}"].font = f(GREY, size=8)
            ws[f"C{r}"] = fx.format(**{k: v for k, v in CELLS.items()})
            ws[f"C{r}"].number_format = fmt
            ws[f"C{r}"].font = f(GREEN if "DcfData" in fx or "CompsData" in fx else "000000", bold=code == "blended")
    ws[f"C{CELLS['blended']}"].fill = KEY_FILL

    f0 = int(CELLS["upside"]) + 2
    ws[f"B{f0}"], ws[f"B{f0}"].font = "Football field (USD per share; low, high, marker)", f(bold=True)
    for j, h in enumerate(["Method", "Low", "High", "Marker", "Bar length", "Source"]):
        ws[f"{'BCDEFG'[j]}{f0 + 1}"] = h
        ws[f"{'BCDEFG'[j]}{f0 + 1}"].font = f(bold=True)
        ws[f"{'BCDEFG'[j]}{f0 + 1}"].fill = HEAD_FILL
    dd = lambda k: f'INDEX(DcfData!$A:$Z,MATCH("NVDA",DcfData!$A:$A,0),MATCH("{k}",DcfData!$1:$1,0))'  # noqa: E731
    live = {0: (f"={letters['low_52w']}{nv}", f"={letters['high_52w']}{nv}", f"=C{nv}"),
            1: (f"={dd('py_bear')}", f"={dd('py_bull')}", f"={dd('py_base')}")}
    for k, (mcode, rr) in enumerate((("pe_ntm", 3), ("ev_ebitda_ntm", 4), ("ev_revenue_ntm", 5), ("ev_ebitda_ltm", 6))):
        c = letters[mcode]
        live[rr] = (f"={c}{CELLS['imp_p25']}", f"={c}{CELLS['imp_p75']}", f"={c}{CELLS['imp_p50']}")
    for k, fr in enumerate(foot.to_dict("records")):
        r = f0 + 2 + k
        ws[f"B{r}"] = fr["method"]
        lo, hi, pt = live.get(k, (float(fr["low"]), float(fr["high"]), float(fr["point"])))
        for col, v in zip("CDE", (lo, hi, pt)):
            ws[f"{col}{r}"] = v
            ws[f"{col}{r}"].number_format = EPS
            ws[f"{col}{r}"].font = f(BLUE if isinstance(v, float) else "000000")
        ws[f"F{r}"] = f"=D{r}-C{r}"
        ws[f"F{r}"].number_format = EPS
        ws[f"G{r}"] = fr["note"] + ("" if k in live else " (static, from Python)")
        ws[f"G{r}"].font = f(GREY, italic=True, size=9)
    fl = f0 + 1 + len(foot)
    CELLS["football_first"], CELLS["football_last"] = str(f0 + 2), str(fl)

    ch = BarChart()
    ch.type, ch.grouping, ch.overlap = "bar", "stacked", 100
    ch.title = f"NVIDIA football field: value per share (USD); price at cutoff {float(rows[cfg['target']]['price']):.2f}"
    ch.y_axis.title = "USD per share"
    ch.add_data(Reference(ws, min_col=3, min_row=f0 + 1, max_row=fl), titles_from_data=True)
    ch.add_data(Reference(ws, min_col=6, min_row=f0 + 1, max_row=fl), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=2, min_row=f0 + 2, max_row=fl))
    ch.series[0].graphicalProperties.noFill = True
    ch.series[0].graphicalProperties.line.noFill = True
    ch.series[1].graphicalProperties.solidFill = "76B900"
    ch.legend = None
    ch.height, ch.width = 9, 22
    ws.add_chart(ch, f"I{g0}")

    sc = ScatterChart()
    sc.title, sc.style = "NTM revenue growth (x) vs NTM EV / revenue (y); line fitted to peers", 13
    sc.x_axis.title, sc.y_axis.title = "NTM revenue growth", "NTM EV / revenue"
    xs = Reference(ws, min_col=ws[f"{gx}1"].column, min_row=first + 1, max_row=last)
    ys = Reference(ws, min_col=ws[f"{gy}1"].column, min_row=first + 1, max_row=last)
    s1 = Series(ys, xs, title="Peers")
    s1.marker.symbol, s1.marker.size, s1.graphicalProperties.line.noFill = "circle", 8, True
    s1.marker.graphicalProperties.solidFill = s1.marker.graphicalProperties.line.solidFill = "808080"
    s1.trendline = Trendline(trendlineType="linear", dispRSqr=True)
    s2 = Series(Reference(ws, min_col=ws[f"{gy}1"].column, min_row=first), Reference(ws, min_col=ws[f"{gx}1"].column, min_row=first), title="NVIDIA")
    s2.marker.symbol, s2.marker.size, s2.graphicalProperties.line.noFill = "diamond", 11, True
    s2.marker.graphicalProperties.solidFill = s2.marker.graphicalProperties.line.solidFill = "76B900"
    sc.series += [s1, s2]
    sc.height, sc.width = 9, 16
    ws.add_chart(sc, f"I{g0 + 20}")
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 58
    for c in range(3, base + 1 + 3 * len(mult)):
        ws.column_dimensions[L(c)].width = 13
    ws.freeze_panes = "C5"
