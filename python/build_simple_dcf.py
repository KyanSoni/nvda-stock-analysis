"""Build excel/NVDA_Simple_DCF.xlsx: NVIDIA's verified project numbers in a simple three-tab layout styled after a common
free DCF template (Company Comparison, Statements Model, DCF; Calibri 12, navy banners, yellow inputs, green upside).
Base case only. Reads only the project's clean outputs (Steps 3, 5, 6, 7); its implied price must equal the Step 6
Base value (168.42 at the 2026-11-02 cutoff). Separate from NVDA_Forecast.xlsx, which it never touches.

Usage (project folder, project venv):  & $vpy python\\build_simple_dcf.py"""
import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "excel" / "NVDA_Simple_DCF.xlsx"
C = ROOT / "data" / "clean"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731
md, fc, at = rd(C / "step5" / "model_data.csv"), rd(C / "step5" / "forecast.csv"), rd(C / "step5" / "assumptions.csv")
din = rd(C / "step6" / "dcf_inputs.csv").set_index("ticker")
dval = rd(C / "step6" / "dcf_values.csv").set_index("ticker")
comps = rd(C / "step7" / "comps_table.csv").set_index("ticker")
val = rd(C / "step3" / "exports" / "v_valuation_cutoff.csv").set_index("ticker")

NAVY, YELLOW, YELLOW_SOFT, BLUE, GREEN, TAN, ORANGE = "29498D", "FFE699", "FFF2CC", "D9E1F2", "C6EFCE", "BDB293", "FCE4D6"
ACC = '_($* #,##0_);_($* (#,##0);_($* "-"??_);_(@_)'
ACC2 = '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'
NUM = '#,##0_);(#,##0)'
PCT, PCT2 = "0%", "0.00%"
F = lambda **k: Font(name="Calibri", size=k.pop("size", 12), **k)  # noqa: E731
fill = lambda c: PatternFill("solid", fgColor=c)  # noqa: E731
thin = Side(style="thin", color="000000")
TOP = Border(top=thin)
BOX = Border(top=thin, bottom=thin, left=thin, right=thin)

T = "NVDA"
years = sorted(md[md["ticker"] == T]["fiscal_year"].astype(int).unique())[-5:]
H = {(r.line_item, int(r.fiscal_year)): float(r.value_m) * 1e6 for r in md[md["ticker"] == T].itertuples()}
h = lambda k, y: H.get((k, y), 0.0)  # noqa: E731
FC = {r.row: [float(getattr(r, f"y{i}")) for i in range(1, 6)] for r in fc[(fc["ticker"] == T) & (fc["scenario"] == "Base")].itertuples()}
A = {r.driver: [float(getattr(r, f"y{i}")) for i in range(1, 6)] for r in at[(at["ticker"] == T) & (at["scenario"] == "Base")].itertuples()}
d = din.loc[T]
v = val.loc[T]

wb = Workbook()
cc = wb.active
cc.title = "Company Comparison"
sm = wb.create_sheet("Statements Model")
dcf = wb.create_sheet("DCF")
for ws in (cc, sm, dcf):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3

HC, FCc = ["C", "D", "E", "F", "G"], ["H", "I", "J", "K", "L"]
ALL = HC + FCc


def put(ws, ref, value, fmt=None, bold=False, color="000000", bg=None, size=12, indent=0, italic=False, border=None, align=None):
    c = ws[ref]
    c.value = value
    c.font = F(bold=bold, color=color, size=size, italic=italic)
    if fmt:
        c.number_format = fmt
    if bg:
        c.fill = fill(bg)
    if indent or align:
        c.alignment = Alignment(indent=indent, horizontal=align)
    if border:
        c.border = border
    return c


# =============================== Statements Model
put(sm, "B1", "NVIDIA Corporation: statements model (USD; history from SEC filings via the project, forecast = project Base case)",
    size=10, italic=True, color="808080")
hdr = [("Ticker", T, None, YELLOW), ("Currency", "USD", None, YELLOW), ("Current Year", years[-1], "0", YELLOW),
       ("Price", float(v["price"]), ACC2, BLUE), ("Shares Outstanding", float(d["diluted_shares"]) * 1e6, NUM, BLUE),
       ("Estimated Tax Rate", A["tax_rate"][0], PCT, YELLOW)]
for i, (lab, val_, fmt, bg) in enumerate(hdr):
    r = 2 + i
    put(sm, f"B{r}", lab, color="FFFFFF", bg=NAVY, border=BOX)
    put(sm, f"C{r}", val_, fmt, bg=bg, border=BOX, align="right")
sm.column_dimensions["B"].width = 52
for c in ALL:
    sm.column_dimensions[c].width = 19
put(sm, "E3", "Yellow cells are to be entered manually or if left blank will be filled with the average of previous years",
    bold=True, size=11)
put(sm, "E4", "Yellow forecast cells are pre-filled with the project's Base-case drivers (config/model.yaml).", size=10, italic=True, color="808080")

ROWS = {}
PENDING = []


def banner(row, title):
    sm.merge_cells(f"B{row}:B{row + 1}")
    put(sm, f"B{row}", title, color="FFFFFF", bg=NAVY, size=14, align="center")
    sm[f"B{row}"].alignment = Alignment(horizontal="center", vertical="center")
    for i, c in enumerate(ALL):
        put(sm, f"{c}{row}", "FY" if i in (0, 5) else None, bold=True, color="FFFFFF", bg=NAVY, align="right")
        lab = f"{years[i]}" if i < 5 else f"{years[-1] + i - 4}E"
        put(sm, f"{c}{row + 1}", lab, bold=True, color="FFFFFF", bg=NAVY, align="right")


def line(code, row, label, hist=None, fcst=None, fmt=ACC, bold=False, total=False, ratio=False, yellow=None):
    """hist: list of 5 values or formulas (by column); fcst: function(col, i) -> formula; yellow: list of 5 input values."""
    ROWS[code] = row
    PENDING.append((code, row, label, hist, fcst, fmt, bold, total, ratio, yellow))


def write_line(code, row, label, hist, fcst, fmt, bold, total, ratio, yellow):
    put(sm, f"B{row}", label, bold=bold, indent=1 if ratio else 0)
    for i, c in enumerate(HC):
        if hist is not None:
            x = hist(c, i) if callable(hist) else hist[i]
            put(sm, f"{c}{row}", x, fmt, bold=bold, border=TOP if total else None, italic=ratio)
    for i, c in enumerate(FCc):
        if yellow is not None:
            put(sm, f"{c}{row}", yellow[i], fmt, bg=YELLOW, italic=ratio)
        elif fcst is not None:
            put(sm, f"{c}{row}", fcst(c, i), fmt, bold=bold, border=TOP if total else None, italic=ratio)


R = lambda code, c: f"{c}{ROWS[code]}"  # noqa: E731
prev = lambda c: chr(ord(c) - 1)  # noqa: E731


def use(code, c):
    """The yellow driver for column c, or the average of the five history ratios when the cell is left blank."""
    return f"IF(ISBLANK({c}{ROWS[code]}),AVERAGE($C${ROWS[code]}:$G${ROWS[code]}),{c}{ROWS[code]})"


banner(9, "Income Statement")
rev_g = [FC["revenue"][0] * 1e6 / h("revenue", years[-1]) - 1] + [FC["revenue"][i] / FC["revenue"][i - 1] - 1 for i in range(1, 5)]
line("rev", 12, "Revenue", [h("revenue", y) for y in years], lambda c, i: f"={prev(c)}{ROWS['rev']}*(1+{use('rev_g', c)})")
line("rev_g", 13, "Revenue Growth", lambda c, i: None if i == 0 else f"={c}12/{prev(c)}12-1", fmt=PCT, ratio=True, yellow=rev_g)
line("cogs", 15, "Cost of Revenue", [h("cost_of_revenue", y) for y in years], lambda c, i: f"={c}12*{use('cogs_r', c)}")
line("cogs_r", 16, "COGS % of Revenue", lambda c, i: f"={c}15/{c}12", fmt=PCT, ratio=True, yellow=[1 - g for g in A["gross_margin"]])
line("gp", 17, "Gross Profit", lambda c, i: f"={c}12-{c}15", lambda c, i: f"={c}12-{c}15", bold=True, total=True)
line("gp_r", 18, "Gross Profit Ratio", lambda c, i: f"={c}17/{c}12", lambda c, i: f"={c}17/{c}12", fmt=PCT, ratio=True)
line("rd", 20, "Research And Development Expenses", [h("rd_expense", y) for y in years], lambda c, i: f"={c}12*{use('rd_r', c)}")
line("rd_r", 21, "Research And Development To Revenue", lambda c, i: f"={c}20/{c}12", fmt=PCT2, ratio=True, yellow=A["rd_pct_revenue"])
line("sga", 22, "Selling General And Administrative Expenses", [h("sga_expense", y) for y in years], lambda c, i: f"={c}12*{use('sga_r', c)}")
line("sga_r", 23, "Sales General And Administrative To Revenue", lambda c, i: f"={c}22/{c}12", fmt=PCT2, ratio=True, yellow=A["sga_pct_revenue"])
line("oth", 24, "Other Expenses", [h("gross_profit", y) - h("rd_expense", y) - h("sga_expense", y) - h("operating_income", y) for y in years],
     lambda c, i: f"={c}12*{use('oth_r', c)}")
line("oth_r", 25, "Other Expenses To Revenue", lambda c, i: f"={c}24/{c}12", fmt=PCT2, ratio=True, yellow=A["other_opex_pct_revenue"])
line("opex", 26, "Operating Expenses", lambda c, i: f"={c}20+{c}22+{c}24", lambda c, i: f"={c}20+{c}22+{c}24", bold=True, total=True)
line("oi", 28, "Operating Income", lambda c, i: f"={c}17-{c}26", lambda c, i: f"={c}17-{c}26", bold=True, total=True)
line("oi_r", 29, "Operating Income Ratio", lambda c, i: f"={c}28/{c}12", lambda c, i: f"={c}28/{c}12", fmt=PCT2, ratio=True)
line("da", 30, "Depreciation And Amortization", [h("depreciation_amortization", y) for y in years], lambda c, i: f"={c}12*{use('da_r', c)}")
line("da_r", 31, "D&A % of Revenue", lambda c, i: f"={c}30/{c}12", fmt=PCT2, ratio=True, yellow=A["da_pct_revenue"])
line("ebitda", 32, "EBITDA", lambda c, i: f"={c}28+{c}30", lambda c, i: f"={c}28+{c}30")
line("ebitda_r", 33, "EBITDA Ratio", lambda c, i: f"={c}32/{c}12", lambda c, i: f"={c}32/{c}12", fmt=PCT2, ratio=True)
nonop = [FC["interest_income"][i] * 1e6 - FC["interest_expense"][i] * 1e6 for i in range(5)]
line("other", 35, "Total Other Income Expenses Net", [h("pretax_income", y) - h("operating_income", y) for y in years], yellow=nonop)
line("pbt", 36, "Income Before Tax", lambda c, i: f"={c}28+{c}35", lambda c, i: f"={c}28+{c}35")
line("pbt_r", 37, "Income Before Tax Ratio", lambda c, i: f"={c}36/{c}12", lambda c, i: f"={c}36/{c}12", fmt=PCT2, ratio=True)
line("tax", 38, "Income Tax Expense", [h("income_tax", y) for y in years], lambda c, i: f"={c}36*{use('tax_r', c)}")
line("tax_r", 39, "Effective Tax Rate", lambda c, i: f"={c}38/{c}36", fmt=PCT2, ratio=True, yellow=A["tax_rate"])
line("ni", 40, "Net Income", lambda c, i: f"={c}36-{c}38", lambda c, i: f"={c}36-{c}38", bold=True, total=True)
line("sh", 42, "Diluted Shares Outstanding", [h("shares_diluted_adj", y) for y in years], fmt=NUM, yellow=[x * 1e6 for x in FC["shares"]])
line("eps", 43, "EPS (diluted)", lambda c, i: f"={c}40/{c}42", lambda c, i: f"={c}40/{c}42", fmt=ACC2)
put(sm, "B44", "Other Expenses and Total Other Income are derived (history: the gap between reported lines; forecast: net interest from the project model).",
    size=10, italic=True, color="808080")

banner(46, "Balance Sheet")
line("cash", 49, "Cash And Cash Equivalents", [h("cash_and_equivalents", y) for y in years])
line("sti", 50, "Short Term Investments", [h("st_investments", y) for y in years])
line("ar", 51, "Accounts Receivable", [h("accounts_receivable", y) for y in years], lambda c, i: f"={c}12*{use('dso', c)}/365")
line("dso", 52, "Receivable Days (DSO)", lambda c, i: f"={c}51/{c}12*365", fmt="0", ratio=True, yellow=A["dso_days"])
line("inv", 53, "Inventory", [h("inventory", y) for y in years], lambda c, i: f"={c}15*{use('dio', c)}/365")
line("dio", 54, "Inventory Days (DIO, of COGS)", lambda c, i: f"={c}53/{c}15*365", fmt="0", ratio=True, yellow=A["dio_days"])
line("oca", 55, "Other Current Assets", [h("current_assets", y) - h("cash_and_equivalents", y) - h("st_investments", y) - h("accounts_receivable", y) - h("inventory", y) for y in years])
line("tca", 56, "Total Current Assets", [h("current_assets", y) for y in years], bold=True, total=True)
line("ppe", 57, "Property Plant Equipment Net", [h("ppe_net", y) for y in years])
line("onca", 58, "Other Non Current Assets", [h("total_assets", y) - h("current_assets", y) - h("ppe_net", y) for y in years])
line("ta", 59, "Total Assets", [h("total_assets", y) for y in years], bold=True, total=True)
line("ap", 61, "Accounts Payable", [h("accounts_payable", y) for y in years], lambda c, i: f"={c}15*{use('dpo', c)}/365")
line("dpo", 62, "Payable Days (DPO, of COGS)", lambda c, i: f"={c}61/{c}15*365", fmt="0", ratio=True, yellow=A["dpo_days"])
line("debt", 63, "Total Debt", [h("total_debt", y) for y in years])
line("ol", 64, "Other Liabilities", [h("total_liabilities", y) - h("accounts_payable", y) - h("total_debt", y) for y in years])
line("tl", 65, "Total Liabilities", [h("total_liabilities", y) for y in years], bold=True, total=True)
line("eq", 66, "Total Stockholders Equity", [h("total_assets", y) - h("total_liabilities", y) for y in years])
line("tle", 67, "Total Liabilities And Stockholders Equity", lambda c, i: f"={c}65+{c}66", bold=True, total=True)
put(sm, "B68", "Forecast columns carry only the working-capital lines the DCF needs; the full forecast balance sheet is in NVDA_Forecast.xlsx.",
    size=10, italic=True, color="808080")

banner(70, "Cash Flows")
line("cf_ni", 73, "Net Income", lambda c, i: f"={c}40", lambda c, i: f"={c}40")
line("cf_da", 74, "Depreciation And Amortization", lambda c, i: f"={c}30", lambda c, i: f"={c}30")
line("sbc", 75, "Stock Based Compensation", [h("sbc", y) for y in years], lambda c, i: f"={c}12*{use('sbc_r', c)}")
line("sbc_r", 76, "SBC % of Revenue", lambda c, i: f"={c}75/{c}12", fmt=PCT2, ratio=True, yellow=A["sbc_pct_revenue"])
line("wc", 77, "Change In Working Capital (history: includes other items)",
     [h("operating_cash_flow", y) - h("net_income", y) - h("depreciation_amortization", y) - h("sbc", y) for y in years],
     lambda c, i: f"=-(({c}51-{prev(c)}51)+({c}53-{prev(c)}53)-({c}61-{prev(c)}61))")
line("cfo", 78, "Net Cash Provided By Operating Activities", [h("operating_cash_flow", y) for y in years],
     lambda c, i: f"={c}73+{c}74+{c}75+{c}77", bold=True, total=True)
line("capex", 79, "Capital Expenditure", [-h("capex", y) for y in years], lambda c, i: f"=-{c}12*{use('capex_r', c)}")
line("capex_r", 80, "Capex % of Revenue", lambda c, i: f"=-{c}79/{c}12", fmt=PCT2, ratio=True, yellow=A["capex_pct_revenue"])
line("fcf", 81, "Free Cash Flow", lambda c, i: f"={c}78+{c}79", lambda c, i: f"={c}78+{c}79", bold=True, total=True)
line("bb", 83, "Common Stock Repurchased", [-h("buybacks", y) for y in years])
line("div", 84, "Dividends Paid", [-h("dividends", y) for y in years])
for p_ in PENDING:
    write_line(*p_)
sm.freeze_panes = "C12"

# =============================== DCF
put(dcf, "B2", "Discounted Cash Flow Analysis", bold=True, size=16)
put(dcf, "E2", "NVIDIA Corporation", bold=True, size=16)
put(dcf, "E3", T)
put(dcf, "H3", "Yellow cells are to be entered manually; the model reads the Statements Model", bold=True, size=11)
dcf.column_dimensions["B"].width = 30
for c in "CDEFGH":
    dcf.column_dimensions[c].width = 20
dcf.column_dimensions["I"].width = 3
dcf.column_dimensions["J"].width = 3
dcf.column_dimensions["K"].width = 30
dcf.column_dimensions["L"].width = 4
dcf.column_dimensions["M"].width = 24
dcf.column_dimensions["N"].width = 3
dcf.column_dimensions["O"].width = 28
dcf.column_dimensions["P"].width = 24

for c in "BCDEFGH":
    put(dcf, f"{c}5", "Cash Flow Projections" if c == "B" else None, bold=True, color="FFFFFF", bg=NAVY)
put(dcf, "C6", f"{years[-1]}", bold=True, align="right")
for i, c in enumerate("DEFGH"):
    put(dcf, f"{c}6", f"{years[-1] + 1 + i}E", bold=True, align="right")
smc = dict(zip("CDEFGH", ["G"] + FCc))     # DCF column -> Statements Model column
put(dcf, "B8", "EBITDA")
put(dcf, "B9", "Unlevered Free Cash Flow", bold=True)
put(dcf, "B10", "Share of Year Counted")
put(dcf, "B11", "Discount Period (mid-year)")
put(dcf, "B12", "Present Value of FCF", bold=True)
for c, s in smc.items():
    put(dcf, f"{c}8", f"='Statements Model'!{s}32", ACC)
    if c == "C":
        continue
    put(dcf, f"{c}9", f"='Statements Model'!{s}28*(1-'Statements Model'!{s}38/'Statements Model'!{s}36)+'Statements Model'!{s}30+'Statements Model'!{s}79+'Statements Model'!{s}77", ACC, bold=True)
put(dcf, "D10", float(d["stub_fraction"]), PCT, bg=YELLOW_SOFT)
for c in "EFGH":
    put(dcf, f"{c}10", 1, PCT)
put(dcf, "D11", f"=MAX(0,{float(d['t_first'])}-D10/2)", "0.00")
for k, c in enumerate("EFGH", start=1):
    put(dcf, f"{c}11", f"={float(d['t_first'])}+{k}-0.5", "0.00")
for c in "DEFGH":
    put(dcf, f"{c}12", f"={c}9*{c}10/(1+$M$7)^{c}11", ACC, bold=True)
for c in "BCDEFGH":
    dcf[f"{c}12"].border = Border(bottom=thin)
put(dcf, "B13", "Year 1 counts only the part after the 26 Jul 2026 balance sheet (H1 is already in cash); SBC is a cost, not added back.",
    size=10, italic=True, color="808080")

put(dcf, "B16", "Market Value vs Intrinsic Value", bold=True, color="FFFFFF", bg=NAVY)
for c in "CD":
    put(dcf, f"{c}16", None, bg=NAVY)
for r, lab, fx in ((18, "MarketValue", "=M20"), (19, "Upside", "=M22"), (20, "Intrinsic Value", "=M19")):
    put(dcf, f"B{r}", lab)
    put(dcf, f"D{r}", fx, ACC2)
for r in range(16, 21):
    dcf[f"B{r}"].border = Border(left=thin)
    dcf[f"D{r}"].border = Border(right=thin)
for c in "BCD":
    dcf[f"{c}20"].border = Border(bottom=thin, left=thin if c == "B" else None, right=thin if c == "D" else None)

for c in "KLM":
    put(dcf, f"{c}5", "DCF Assumptions" if c == "K" else None, bold=True, color="FFFFFF", bg=NAVY)
assump = [(7, "Discount Rate:", "=P22", PCT2, YELLOW_SOFT, False), (9, "Terminal Growth Rate:", 0.03, PCT2, YELLOW_SOFT, False),
          (10, "Terminal Value:", "=H9*(1+M9)/(M7-M9)", ACC, None, False),
          (12, "PV of Terminal Value:", f"=M10/(1+M7)^({float(d['t_first'])}+4)", ACC, None, False),
          (13, "Sum of PV of Cash Flows:", "=SUM(D12:H12)", ACC, None, False), (14, "Enterprise Value:", "=M12+M13", ACC, None, True),
          (16, "Balance Sheet Adjustments:", "=P14+P15+P16-P17", ACC, None, False), (17, "Implied Equity Value:", "=M14+M16", ACC, None, True),
          (19, "Implied Price per Share:", "=M17/P18", ACC2, None, True), (20, "Current Price:", float(v["price"]), ACC2, "D9D9D9", True),
          (22, "Potential Upside ($)", "=M19-M20", ACC2, GREEN, False), (23, "Potential Upside (%)", "=M19/M20-1", PCT, GREEN, False)]
for r, lab, fx, fmt, bg, b in assump:
    put(dcf, f"K{r}", lab, bold=b)
    put(dcf, f"M{r}", fx, fmt, bold=b, bg=bg)
for r in range(5, 24):
    dcf[f"K{r}"].border = Border(left=thin, bottom=thin if r == 23 else None)
    dcf[f"M{r}"].border = Border(right=thin, bottom=thin if r == 23 else None)
dcf["L23"].border = Border(bottom=thin)
for r in (19, 20):
    dcf[f"M{r}"].border = BOX
put(dcf, "K25", "Balance sheet adjustments = cash + short-term investments + listed equity stakes - debt (Q2 FY2027 10-Q).",
    size=10, italic=True, color="808080")
put(dcf, "K26", f"Project check (Step 6 Base value per share): {float(dval.loc[T, 'base_per_share']):.2f}", size=10, italic=True, color="808080")

for c in "OP":
    put(dcf, f"{c}5", "WACC Calculation" if c == "O" else None, bold=True, color="FFFFFF", bg=NAVY)
rows_w = [(6, "US Treasury 10Y yield", float(d["risk_free"]), PCT2), (8, "Rf", "=P6", PCT2),
          (9, "Beta (raw, 60m vs SPY)", float(d["beta_raw"]), "0.000"), (10, "Beta (Blume-adjusted)", "=0.67*P9+0.33", "0.000"),
          (11, "Rm (Rf + 5% risk premium)", f"=P8+{float(d['erp'])}", PCT2), (12, "Ke", "=P8+P10*(P11-P8)", PCT2),
          (13, "Tax Rate", float(d["tax_rate"]), PCT2), (14, "Cash And Cash Equivalents", float(d["cash"]) * 1e6, ACC),
          (15, "Short Term Investments", float(d["st_investments"]) * 1e6, ACC), (16, "Listed Equity Stakes", float(d["stakes"]) * 1e6, ACC),
          (17, "Total Debt", float(d["debt"]) * 1e6, ACC), (18, "Diluted Shares", float(d["diluted_shares"]) * 1e6, NUM),
          (19, "Market Cap", float(v["market_cap"]) * 1e6, ACC), (20, "Ve / Vd (weights)", "=P19/(P19+P17)", PCT2),
          (21, "Kd (pre-tax)", float(d["cost_of_debt"]), PCT2), (22, "WACC", "=P20*P12+(1-P20)*P21*(1-P13)", PCT2)]
for r, lab, fx, fmt in rows_w:
    put(dcf, f"O{r}", lab, bold=r in (12, 22))
    put(dcf, f"P{r}", fx, fmt, bold=r in (12, 22), bg=YELLOW_SOFT if r in (6, 9, 13, 21) else None)
for r in range(5, 23):
    dcf[f"O{r}"].border = Border(left=thin, bottom=thin if r == 22 else None)
    dcf[f"P{r}"].border = Border(right=thin, bottom=thin if r == 22 else None)

ch = BarChart()
ch.type, ch.title, ch.legend = "col", "Market Value vs Intrinsic Value", None
ch.add_data(Reference(dcf, min_col=4, min_row=18, max_row=20))
ch.set_categories(Reference(dcf, min_col=2, min_row=18, max_row=20))
ch.varyColors = True
ch.y_axis.numFmt = '"$"#,##0'
ch.height, ch.width = 8, 14
dcf.add_chart(ch, "E15")

# =============================== Company Comparison
NAMES = {"NVDA": "NVIDIA Corporation", "AMD": "Advanced Micro Devices, Inc.", "AVGO": "Broadcom Inc.", "INTC": "Intel Corporation",
         "MRVL": "Marvell Technology, Inc.", "QCOM": "QUALCOMM Incorporated"}
order = ["NVDA", "AMD", "AVGO", "INTC", "MRVL", "QCOM"]
cc.column_dimensions["B"].width = 26
put(cc, "B2", "Year", bg=ORANGE, border=BOX)
put(cc, "C2", years[-1] + 0, "0", bg=ORANGE, border=BOX, align="right")
put(cc, "B3", "Data as of", bg=ORANGE, border=BOX)
put(cc, "C3", v["cutoff_date"], bg=ORANGE, border=BOX, align="right")
labels = ["Ticker", "Name", "Price", "P/E (LTM, GAAP)", "Market Cap ($m)", "EPS (LTM, diluted)", "Net Margin (LTM)", "P/E (NTM, consensus)",
          "Dividends per Share (FY)", "Dividend Yield"]
for k, lab in enumerate(labels):
    put(cc, f"B{5 + k}", lab, bg=TAN if k == 0 else None)
for j, t in enumerate(order):
    col = chr(ord("C") + j)
    cc.column_dimensions[col].width = 26
    r = comps.loc[t]
    fy = max(int(y) for y in md[md["ticker"] == t]["fiscal_year"])
    divs = float(md[(md["ticker"] == t) & (md["line_item"] == "dividends") & (md["fiscal_year"] == str(fy))]["value_m"].iloc[0] or 0) \
        if not md[(md["ticker"] == t) & (md["line_item"] == "dividends") & (md["fiscal_year"] == str(fy))].empty else 0.0
    dps = divs / float(r["diluted_shares"])
    put(cc, f"{col}5", t, bg=ORANGE if t == T else TAN)
    put(cc, f"{col}6", NAMES[t])
    put(cc, f"{col}7", float(r["price"]), ACC2)
    put(cc, f"{col}8", float(r["pe_ltm"]) if r["pe_ltm"] else "Unavailable", ACC2 if r["pe_ltm"] else None, align=None if r["pe_ltm"] else "right")
    put(cc, f"{col}9", float(r["market_cap"]), ACC2)
    put(cc, f"{col}10", float(r["eps_ltm"]), ACC2)
    put(cc, f"{col}11", float(r["net_income_ltm"]) / float(r["revenue_ltm"]), PCT2)
    put(cc, f"{col}12", float(r["pe_ntm"]), ACC2)
    put(cc, f"{col}13", dps if dps > 0 else "Unavailable", ACC2 if dps > 0 else None)
    put(cc, f"{col}14", dps / float(r["price"]) if dps > 0 else "Unavailable", PCT2 if dps > 0 else None)
for k in range(10):
    for j in range(len(order) + 1):
        col = chr(ord("B") + j)
        b = Border(top=thin if k == 0 else None, bottom=thin if k in (0, 9) else None, left=thin if j == 0 else None,
                   right=thin if j == len(order) else None)
        cc[f"{col}{5 + k}"].border = b
put(cc, "B16", "Yellow cells are to be entered manually; peers' figures come from the project's verified Step 3 and Step 7 outputs.",
    bold=True, size=11)
put(cc, "B17", "LTM = last four reported quarters (own fiscal calendar). NTM = consensus, calendarised to Nov 2026-Oct 2027 (Step 7). "
    "Dividends: latest fiscal year paid / diluted shares.", size=10, italic=True, color="808080")

wb.active = 2
wb.calculation.fullCalcOnLoad = True
OUT.parent.mkdir(parents=True, exist_ok=True)
wb.save(OUT)
print("saved", OUT)
