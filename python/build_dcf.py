"""Step 6b: add the WACC, DCF and DcfData tabs to excel/NVDA_Forecast.xlsx (called by build_model.build).

WACC and DCF are live formulas on the selected ticker and scenario, linked to the IS and Schedules tabs; the WACC x
terminal-growth grid is live too. The only typed numbers are on DcfData (blue, written from dcf_inputs.csv). Three
blocks are static and labelled as computed by python/step6_dcf.py: the Bear / Base / Bull / weighted values (with a
check that the live value equals the Python value for the selected scenario), the growth x margin grid and the
reverse DCF (both re-run the whole forecast, which a formula grid cannot do).
"""
from __future__ import annotations

from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill

from build_model import EPS, FC, GREEN, GREY, BLUE, HEAD_FILL, KEY_FILL, MONEY, PCT, Sheet, f

DATA_FIELDS = ["price", "market_cap", "cash", "st_investments", "debt", "stakes", "diluted_shares", "t_first", "stub_fraction",
               "beta_raw", "blume_weight", "blume_constant", "risk_free", "erp", "terminal_growth", "exit_multiple",
               "w_bear", "w_base", "w_bull", "py_bear", "py_base", "py_bull", "py_weighted"]
X = "0.00x"
SUMMARY = {}   # code -> row on the DCF tab (filled by add; read by step6_check)
WACC_ROWS = {}


def add(wb, payload: dict, IS, S, sel: dict) -> None:
    inp, values, gm, rev = payload["inputs"], payload["values"], payload["gm_sensitivity"], payload["reverse"]
    names = wb.sheetnames
    ws_w = wb.create_sheet("WACC", names.index("Data"))
    ws_d = wb.create_sheet("DCF", names.index("Data") + 1)
    dd = wb.create_sheet("DcfData")

    # ---------------- DcfData
    dd.append(["ticker"] + DATA_FIELDS + ["stakes_source", "quality_flag"])
    v = values.set_index("ticker")
    for r in inp.to_dict("records"):
        t = r["ticker"]
        py = [float(v.loc[t, f"{s}_per_share"]) for s in ("bear", "base", "bull")] + [float(v.loc[t, "weighted_per_share"])]
        dd.append([t] + [float(r[k]) for k in DATA_FIELDS[:-4]] + py + [r["stakes_source"], v.loc[t, "quality_flag"]])
    n = dd.max_row
    for row in dd.iter_rows(min_row=2, min_col=2, max_col=1 + len(DATA_FIELDS)):
        for c in row:
            c.font = f(BLUE)
    dd["AA1"] = ("Source: data/clean/step6/dcf_inputs.csv and peer_dcf.csv (python/step6_dcf.py; Step 3 v_valuation_cutoff, "
                 "Step 4 v_beta, Step 3 quarterly facts, config/dcf.yaml). py_* = values computed in Python. Do not edit.")
    dd["AA1"].font = f(GREY, italic=True, size=9)
    col = {k: i + 2 for i, k in enumerate(DATA_FIELDS)}
    lk = lambda k: f"INDEX(DcfData!$A$2:$Z${n},MATCH(Ticker,DcfData!$A$2:$A${n},0),{col[k]})"  # noqa: E731
    lk_txt = lambda k: f'IFERROR(INDEX(DcfData!$A$2:$Z${n},MATCH(Ticker,DcfData!$A$2:$A${n},0),{k}),"")'  # noqa: E731

    # ---------------- WACC
    ws_w["A1"], ws_w["A1"].font = "WACC: selected ticker (CAPM with Blume-adjusted beta, S6-D1/D2)", f(bold=True, size=12)
    ws_w["A2"] = '="Ticker "&Ticker&" | the same WACC is used in all three scenarios"'
    ws_w["A2"].font = f(GREY, italic=True, size=9)
    ws_w.column_dimensions["A"].width = 16
    ws_w.column_dimensions["B"].width = 62
    ws_w.column_dimensions["C"].width = 14
    ws_w.column_dimensions["D"].width = 90
    kd_base = f"Assumptions!D{sel['cost_of_debt'] - 2}"
    tax_base = f"Assumptions!D{sel['tax_rate'] - 2}"
    lines = [("beta_raw", "Raw beta vs SPY (60 monthly returns, Step 4)", f"={lk('beta_raw')}", "0.000", "DcfData; Step 4 v_beta"),
             ("blume_w", "Blume weight on raw beta", f"={lk('blume_weight')}", "0.00", "config/dcf.yaml"),
             ("blume_c", "Blume constant (weight on 1.0)", f"={lk('blume_constant')}", "0.00", "config/dcf.yaml"),
             ("beta_adj", "Adjusted beta", "=C{blume_w}*C{beta_raw}+C{blume_c}", "0.000", "formula"),
             ("rf", "Risk-free rate (US 10-year Treasury at the cutoff)", f"={lk('risk_free')}", "0.00%", "Step 3 v_valuation_cutoff"),
             ("erp", "Equity risk premium", f"={lk('erp')}", "0.00%", "config/dcf.yaml (S4-D5)"),
             ("ke", "Cost of equity = rf + beta x ERP", "=C{rf}+C{beta_adj}*C{erp}", "0.00%", "formula"),
             ("kd", "Pre-tax cost of debt (Base, forecast year 1)", f"={kd_base}", "0.00%", "Assumptions tab, Base row"),
             ("tax", "Tax rate (Base, forecast year 1)", f"={tax_base}", "0.00%", "Assumptions tab, Base row"),
             ("kd_at", "After-tax cost of debt", "=C{kd}*(1-C{tax})", "0.00%", "formula"),
             ("mcap", "Market value of equity ($m, cutoff price x shares)", f"={lk('market_cap')}", MONEY, "Step 3 v_valuation_cutoff"),
             ("debt", "Debt ($m, book, latest balance sheet)", f"={lk('debt')}", MONEY, "Step 3 v_valuation_cutoff"),
             ("wd", "Debt weight = debt / (debt + equity)", "=C{debt}/(C{debt}+C{mcap})", "0.00%", "formula"),
             ("wacc", "WACC = (1 - wd) x Ke + wd x Kd x (1 - t)", "=(1-C{wd})*C{ke}+C{wd}*C{kd_at}", "0.00%", "formula")]
    r = 4
    for code, *_ in lines:
        WACC_ROWS[code] = r
        r += 1
    for code, label, formula, fmt, src in lines:
        rr = WACC_ROWS[code]
        ws_w[f"A{rr}"], ws_w[f"B{rr}"], ws_w[f"D{rr}"] = code, label, src
        ws_w[f"A{rr}"].font, ws_w[f"D{rr}"].font = f(GREY, size=8), f(GREY, italic=True, size=9)
        ws_w[f"C{rr}"] = formula.format(**WACC_ROWS)
        ws_w[f"C{rr}"].number_format = fmt
        ws_w[f"C{rr}"].font = f(GREEN if src.startswith(("DcfData", "Step", "config", "Assumptions")) else "000000", bold=code == "wacc")
    ws_w[f"C{WACC_ROWS['wacc']}"].fill = KEY_FILL
    wacc = f"WACC!$C${WACC_ROWS['wacc']}"

    # ---------------- DCF (forecast columns H-L, like IS)
    D_ = Sheet(ws_d, "DCF: unlevered free cash flow, selected ticker and scenario (mid-year discounting)")
    ws_d["A2"] = '="Ticker "&Ticker&" | scenario "&Cover!C7&" | valuation date = Step 2 cutoff; first year counts only the part after the latest balance sheet"'
    ir, sr = IS.rows, S.rows
    D_.section("Unlevered free cash flow (SBC is a cost and is not added back, D6)")
    D_.row("ebit", "Operating income (EBIT)", None, lambda c, i: f"=IS!{c}{ir['operating_income']}")
    D_.row("tax_rate", "Tax rate (income tax / pre-tax income)", None, lambda c, i: f"=IFERROR(IS!{c}{ir['income_tax']}/IS!{c}{ir['pretax_income']},0)", PCT)
    D_.row("nopat", "NOPAT = EBIT x (1 - tax)", None, lambda c, i: f"={c}{D_.rows['ebit']}*(1-{c}{D_.rows['tax_rate']})")
    D_.row("da", "Add: D&A", None, lambda c, i: f"=Schedules!{c}{sr['da']}")
    D_.row("capex", "Less: capex", None, lambda c, i: f"=Schedules!{c}{sr['capex']}")
    D_.row("dnwc", "Less: increase in working capital (receivables + inventory - payables)", None,
           lambda c, i: f"=Schedules!{c}{sr['d_ar']}+Schedules!{c}{sr['d_inv']}-Schedules!{c}{sr['d_ap']}")
    D_.row("ufcf", "Unlevered free cash flow", None,
           lambda c, i: f"={c}{D_.rows['nopat']}+{c}{D_.rows['da']}-{c}{D_.rows['capex']}-{c}{D_.rows['dnwc']}", bold=True)
    D_.section("Discounting")
    D_.row("fraction", "Share of the year still to come (year 1: 1 - quarters already reported / forecast revenue)", None,
           lambda c, i: f"={lk('stub_fraction')}" if i == 0 else "=1", PCT)
    D_.row("counted", "Cash flow counted", None, lambda c, i: f"={c}{D_.rows['ufcf']}*{c}{D_.rows['fraction']}")
    D_.row("t", "Years from valuation date (mid-point of the counted period)", None,
           lambda c, i: f"=MAX(0,{lk('t_first')}-{c}{D_.rows['fraction']}/2)" if i == 0 else f"={lk('t_first')}+{i}-0.5", "0.000")
    D_.row("df", "Discount factor = 1 / (1 + WACC) ^ t", None, lambda c, i: f"=1/(1+{wacc})^{c}{D_.rows['t']}", "0.0000")
    D_.row("pv", "Present value", None, lambda c, i: f"={c}{D_.rows['counted']}*{c}{D_.rows['df']}", bold=True)
    rows = D_.rows
    L = FC[-1]
    rng = lambda code: f"$H${rows[code]}:$L${rows[code]}"  # noqa: E731

    # valuation summary in B / C
    s0 = D_.next + 1
    items = [("sec", "Valuation (selected scenario)", None, None),
             ("wacc", "WACC (WACC tab)", f"={wacc}", PCT),
             ("g", "Terminal growth (perpetuity, S6-D3)", f"={lk('terminal_growth')}", PCT),
             ("g_ok", "Check: terminal growth below WACC", '=IF(C{g}<C{wacc},"OK","CHECK")', None),
             ("sum_pv", "Sum of PV of forecast cash flows", f"=SUM({rng('pv')})", MONEY),
             ("tv", "Terminal value at end of year 5 = UFCF5 x (1 + g) / (WACC - g)", f"={L}{rows['ufcf']}*(1+C{{g}})/(C{{wacc}}-C{{g}})", MONEY),
             ("t_tv", "Years to end of year 5", f"={lk('t_first')}+4", "0.000"),
             ("pv_tv", "PV of terminal value", "=C{tv}/(1+C{wacc})^C{t_tv}", MONEY),
             ("ev", "Enterprise value", "=C{sum_pv}+C{pv_tv}", MONEY),
             ("tv_share", "  terminal value share of EV", "=IFERROR(C{pv_tv}/C{ev},0)", PCT),
             ("cash", "Add: cash and equivalents (latest balance sheet)", f"={lk('cash')}", MONEY),
             ("sti", "Add: short-term investments (debt securities)", f"={lk('st_investments')}", MONEY),
             ("stakes", "Add: listed equity stakes at fair value (S6-D5; DcfData source column)", f"={lk('stakes')}", MONEY),
             ("debt", "Less: debt", f"={lk('debt')}", MONEY),
             ("equity", "Equity value", "=C{ev}+C{cash}+C{sti}+C{stakes}-C{debt}", MONEY),
             ("shares", "Diluted shares (m, latest quarter)", f"={lk('diluted_shares')}", "#,##0.0"),
             ("per_share", "Value per share (USD)", "=C{equity}/C{shares}", EPS),
             ("price", "Share price at the cutoff (USD)", f"={lk('price')}", EPS),
             ("upside", "Upside / (downside)", "=C{per_share}/C{price}-1", PCT),
             ("sec2", "Exit-multiple cross-check (not the headline, S6-D3)", None, None),
             ("implied_x", "EV / EBITDA implied by the perpetuity terminal value (year 5)", f"=IFERROR(C{{tv}}/({L}{rows['ebit']}+{L}{rows['da']}),0)", X),
             ("exit_x", "Peer median LTM EV / EBITDA at the cutoff (excl. this company and AMD)", f"={lk('exit_multiple')}", X),
             ("tv_exit", "Terminal value at the peer multiple", f"=C{{exit_x}}*({L}{rows['ebit']}+{L}{rows['da']})", MONEY),
             ("per_share_exit", "Value per share at the peer multiple (USD)",
              "=(C{sum_pv}+C{tv_exit}/(1+C{wacc})^C{t_tv}+C{cash}+C{sti}+C{stakes}-C{debt})/C{shares}", EPS),
             ("sec3", "Scenario values (computed by python/step6_dcf.py; static, refreshed by run_step6)", None, None),
             ("py_bear", "Bear value per share (25%)", f"={lk('py_bear')}", EPS),
             ("py_base", "Base value per share (50%)", f"={lk('py_base')}", EPS),
             ("py_bull", "Bull value per share (25%)", f"={lk('py_bull')}", EPS),
             ("py_weighted", "Probability-weighted value per share", f"={lk('py_weighted')}", EPS),
             ("py_upside", "  vs price", "=C{py_weighted}/C{price}-1", PCT),
             ("x1", "Check: live value above equals Python for this scenario (within $0.01)",
              '=IF(ABS(C{per_share}-CHOOSE(Scenario,C{py_bear},C{py_base},C{py_bull}))<0.01,"OK","CHECK")', None),
             ("flag", "Data flag for this company (peers are mechanical, S6-D7)", f'={lk_txt(len(DATA_FIELDS) + 3)}', None)]
    for k, (code, *_rest) in enumerate(items):
        SUMMARY[code] = s0 + k
    for code, label, formula, fmt in items:
        rr = SUMMARY[code]
        ws_d[f"A{rr}"], ws_d[f"B{rr}"] = (None if code.startswith("sec") else code), label
        ws_d[f"A{rr}"].font = f(GREY, size=8)
        ws_d[f"B{rr}"].font = f(bold=code.startswith("sec") or code in ("ev", "equity", "per_share", "py_weighted"))
        if formula:
            ws_d[f"C{rr}"] = formula.format(**SUMMARY)
            if fmt:
                ws_d[f"C{rr}"].number_format = fmt
            ws_d[f"C{rr}"].font = f(GREEN if "DcfData" in formula or "WACC!" in formula else "000000",
                                    bold=code in ("per_share", "py_weighted", "x1", "g_ok"))
    for code in ("per_share", "py_weighted"):
        ws_d[f"C{SUMMARY[code]}"].fill = KEY_FILL
    bad = PatternFill("solid", fgColor="FFC7CE")
    for code in ("x1", "g_ok"):
        c = f"C{SUMMARY[code]}"
        ws_d.conditional_formatting.add(c, FormulaRule(formula=[f'{c}<>"OK"'], fill=bad, font=Font(color="9C0006")))

    # live WACC x g grid
    g0 = SUMMARY["flag"] + 2
    ws_d[f"B{g0}"], ws_d[f"B{g0}"].font = "Sensitivity: value per share, WACC (rows) x terminal growth (columns); live formulas", f(bold=True)
    waccs, gs = payload["wacc_grid"], payload["g_grid"]
    cols = ["D", "E", "F", "G", "H"]
    ws_d[f"C{g0 + 1}"] = "WACC \\ g"
    for j, g in enumerate(gs):
        ws_d[f"{cols[j]}{g0 + 1}"] = g
        ws_d[f"{cols[j]}{g0 + 1}"].number_format = "0.0%"
        ws_d[f"{cols[j]}{g0 + 1}"].font = f(BLUE, bold=True)
        ws_d[f"{cols[j]}{g0 + 1}"].fill = HEAD_FILL
    S_ = {k: f"$C${v}" for k, v in SUMMARY.items()}
    for i, w in enumerate(waccs):
        rr = g0 + 2 + i
        ws_d[f"C{rr}"] = w
        ws_d[f"C{rr}"].number_format = "0.0%"
        ws_d[f"C{rr}"].font = f(BLUE, bold=True)
        ws_d[f"C{rr}"].fill = HEAD_FILL
        for j, _ in enumerate(gs):
            wc, gc = f"$C{rr}", f"{cols[j]}${g0 + 1}"
            ws_d[f"{cols[j]}{rr}"] = (f"=(SUMPRODUCT({rng('counted')},1/(1+{wc})^{rng('t')})"
                                      f"+$L${rows['ufcf']}*(1+{gc})/({wc}-{gc})/(1+{wc})^{S_['t_tv']}"
                                      f"+{S_['cash']}+{S_['sti']}+{S_['stakes']}-{S_['debt']})/{S_['shares']}")
            ws_d[f"{cols[j]}{rr}"].number_format = EPS
    SUMMARY["grid_first_row"] = g0 + 2

    # static growth x margin grid and reverse DCF (NVIDIA Base)
    q0 = g0 + 3 + len(waccs)
    ws_d[f"B{q0}"], ws_d[f"B{q0}"].font = ("NVIDIA Base: value per share, FY2028 Data Center growth (rows) x gross-margin shift in every year "
                                            "(columns); static, computed by python/step6_dcf.py"), f(bold=True)
    ws_d[f"C{q0 + 1}"] = "growth \\ margin"
    shifts = [c for c in gm.columns if c.startswith("gm_shift_")]
    for j, c in enumerate(shifts):
        ws_d[f"{cols[j]}{q0 + 1}"] = float(c.replace("gm_shift_", ""))
        ws_d[f"{cols[j]}{q0 + 1}"].number_format = "+0.0%;-0.0%;0.0%"
        ws_d[f"{cols[j]}{q0 + 1}"].fill = HEAD_FILL
    for i, rw in enumerate(gm.to_dict("records")):
        rr = q0 + 2 + i
        ws_d[f"C{rr}"] = float(rw["fy2_segment_a_growth"])
        ws_d[f"C{rr}"].number_format = "0.0%"
        ws_d[f"C{rr}"].fill = HEAD_FILL
        for j, c in enumerate(shifts):
            ws_d[f"{cols[j]}{rr}"] = float(rw[c])
            ws_d[f"{cols[j]}{rr}"].number_format = EPS
            ws_d[f"{cols[j]}{rr}"].font = f(BLUE)
    r0 = q0 + 3 + len(gm)
    ws_d[f"B{r0}"], ws_d[f"B{r0}"].font = "NVIDIA Base reverse DCF: what the price implies, one lever at a time (static)", f(bold=True)
    for j, h in enumerate(["lever", "model", "implied", "note"]):
        ws_d[f"{'BCDE'[j]}{r0 + 1}"] = h
        ws_d[f"{'BCDE'[j]}{r0 + 1}"].font = f(bold=True)
    labels = {"fy2_segment_a_growth": "FY2028 Data Center growth", "wacc": "WACC", "terminal_growth": "Terminal growth"}
    for i, rw in enumerate(rev.to_dict("records")):
        rr = r0 + 2 + i
        ws_d[f"B{rr}"] = labels.get(rw["lever"], rw["lever"])
        ws_d[f"C{rr}"] = float(rw["model_value"])
        ws_d[f"D{rr}"] = float(rw["implied_value"]) if rw["implied_value"] else rw["status"]
        ws_d[f"E{rr}"] = rw["note"]
        for c in ("C", "D"):
            ws_d[f"{c}{rr}"].number_format = "0.0%"
            ws_d[f"{c}{rr}"].font = f(BLUE)
        ws_d[f"E{rr}"].font = f(GREY, italic=True, size=9)
    ws_d.column_dimensions["B"].width = 78
