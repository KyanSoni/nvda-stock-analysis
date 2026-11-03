"""Step 5b: write the 3-statement forecast workbook excel/NVDA_Forecast.xlsx (live Excel formulas).

Tabs: Cover (ticker + scenario switch, key outputs, balance check), Assumptions (Bear/Base/Bull/Selected per driver,
with reasons), Historicals, IS, BS, CF, Schedules (working capital, PP&E, debt, equity, shares, cash), Data and
AssumptionsData (the inputs, written by this script from model_data.csv and assumptions.csv).
Every forecast cell is a formula; the only typed numbers are the inputs on Data and AssumptionsData (blue).
The equations are exactly those of step5_model.forecast, which the checks compare against.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

import step5_model as m

HIST = ["C", "D", "E", "F", "G"]
FC = ["H", "I", "J", "K", "L"]
ACOL = {f: a for f, a in zip(FC, ["D", "E", "F", "G", "H"])}      # forecast column -> Assumptions column
FONT = "Arial"
BLUE, GREEN, BLACK, GREY = "0000FF", "008000", "000000", "808080"
MONEY, PCT, DAYS, EPS, SHR = '#,##0;(#,##0);"-"', '0.0%;(0.0%);"-"', '0', '0.00;(0.00);"-"', '#,##0'
HEAD_FILL = PatternFill("solid", fgColor="DDEBF7")
KEY_FILL = PatternFill("solid", fgColor="FFFF00")


def f(color=BLACK, bold=False, italic=False, size=10):
    return Font(name=FONT, color=color, bold=bold, italic=italic, size=size)


class Sheet:
    """Rows addressed by code; columns C-G history (oldest to latest), H-L forecast."""

    def __init__(self, ws, title: str, first_row: int = 6):
        self.ws, self.rows, self.next = ws, {}, first_row
        ws["A1"], ws["A1"].font = title, f(bold=True, size=12)
        ws["A2"] = "USD millions unless stated; history = latest five fiscal years of the selected company, forecast = five years after"
        ws["A2"].font = f(GREY, italic=True, size=9)
        ws["B4"], ws["B4"].font = "Fiscal year", f(bold=True)
        for c in HIST + FC:
            ws[f"{c}4"] = f"=Historicals!{c}4"
            ws[f"{c}4"].font = f(bold=True)
            ws[f"{c}4"].alignment = Alignment(horizontal="right")
            ws[f"{c}4"].fill = HEAD_FILL
        ws["C3"], ws["H3"] = "History", "Forecast"
        ws["C3"].font = ws["H3"].font = f(GREY, italic=True, size=9)
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 46
        for c in HIST + FC:
            ws.column_dimensions[c].width = 12
        ws.freeze_panes = "C5"

    def ref(self, code: str, col: str, sheet: str | None = None) -> str:
        r = self.rows[code]
        return f"{sheet}!{col}{r}" if sheet else f"{col}{r}"

    def section(self, label: str):
        self.ws[f"B{self.next}"], self.ws[f"B{self.next}"].font = label, f(bold=True)
        self.next += 1

    def row(self, code: str, label: str, hist, fc, fmt=MONEY, bold=False):
        """hist / fc: None, or a function(col) -> formula string."""
        r = self.next
        self.rows[code] = r
        self.ws[f"A{r}"], self.ws[f"A{r}"].font = code, f(GREY, size=8)
        self.ws[f"B{r}"], self.ws[f"B{r}"].font = label, f(bold=bold)
        for i, c in enumerate(HIST):
            if hist is not None:
                v = hist(c, i)
                if v is not None:
                    self.ws[f"{c}{r}"] = v
                    self.ws[f"{c}{r}"].font = f(GREEN if "!" in v and v.count("!") == 1 and v.startswith("=Historicals") else BLACK, bold)
                    self.ws[f"{c}{r}"].number_format = fmt
        for i, c in enumerate(FC):
            if fc is not None:
                self.ws[f"{c}{r}"] = fc(c, i)
                self.ws[f"{c}{r}"].font = f(BLACK, bold)
                self.ws[f"{c}{r}"].number_format = fmt
        self.next += 1
        return r


def prev(col: str) -> str:
    return get_column_letter(ord(col) - ord("A"))  # previous column letter (H -> G)


def build(md: pd.DataFrame, at: pd.DataFrame, estimates: pd.DataFrame, out: Path, meta: dict) -> Path:
    wb = Workbook()
    cover = wb.active
    cover.title = "Cover"
    ws_a = wb.create_sheet("Assumptions")
    ws_h = wb.create_sheet("Historicals")
    ws_is, ws_bs, ws_cf, ws_s = (wb.create_sheet(n) for n in ("IS", "BS", "CF", "Schedules"))
    data, adata = wb.create_sheet("Data"), wb.create_sheet("AssumptionsData")
    tickers = sorted(md["ticker"].unique())

    # ---------------- Data (history inputs)
    data.append(["key", "ticker", "line_item", "H1", "H2", "H3", "H4", "H5", "missing_years"])
    for t in tickers:
        years, h = m.history(md, t)
        g = md[md["ticker"] == t]
        have = set(zip(g["line_item"], g["fiscal_year"].astype(int)))
        data.append([f"{t}|fiscal_year", t, "fiscal_year"] + [f"FY{y}" for y in years] + [0])
        for item in m.HIST_ITEMS:
            vals = [float(v) for v in h[item]]
            miss = sum((item, y) not in have for y in years)
            if item in ("datacenter_revenue", "edge_revenue") and t != "NVDA":
                miss = 0          # single revenue line for the peers (S5-D2)
            data.append([f"{t}|{item}", t, item] + vals + [miss])
        e = estimates[(estimates["ticker"] == t) & (estimates["period"].isin(["0y", "+1y"]))].set_index(["kind", "period"])["avg"]
        get = lambda k, p, d=1.0: float(e[(k, p)]) / d if (k, p) in e.index and e[(k, p)] else None  # noqa: E731
        data.append([f"{t}|consensus_revenue", t, "consensus_revenue", get("revenue", "0y", 1e6), get("revenue", "+1y", 1e6), None, None, None, 0])
        data.append([f"{t}|consensus_eps", t, "consensus_eps", get("eps", "0y"), get("eps", "+1y"), None, None, None, 0])
    n_data = data.max_row
    for row in data.iter_rows(min_row=2, min_col=4, max_col=8):
        for c in row:
            c.font = f(BLUE)
            c.number_format = "#,##0.00"
    data["K1"] = f"Source: data/clean/step5/model_data.csv (Step 3 annual view + Step 5 items, cutoff {meta['cutoff']}); consensus: Step 4 snapshot {meta['snapshot']}. Written by python/build_model.py; do not edit."
    data["K1"].font = f(GREY, italic=True, size=9)
    data.column_dimensions["A"].width = 30

    # ---------------- AssumptionsData (driver inputs)
    adata.append(["key", "ticker", "driver", "Y1", "Y2", "Y3", "Y4", "Y5", "reason", "source"])
    for r in at.itertuples():
        adata.append([f"{r.ticker}|{r.driver}|{r.scenario}", r.ticker, r.driver] +
                     [float(getattr(r, f"y{k}")) for k in range(1, 6)] + [r.reason, r.source])
    n_ad = adata.max_row
    for row in adata.iter_rows(min_row=2, min_col=4, max_col=8):
        for c in row:
            c.font = f(BLUE)
    adata["L1"] = "Source: config/model.yaml (NVDA, argued) and generated peer defaults (S5-D6). Edit config/model.yaml and rerun  python python/run_step5.py model ; edits made here are overwritten."
    adata["L1"].font = f(GREY, italic=True, size=9)
    adata.column_dimensions["A"].width = 40

    look = lambda key_expr, k: f'IFERROR(INDEX(Data!$D$2:$H${n_data},MATCH({key_expr},Data!$A$2:$A${n_data},0),{k}),0)'  # noqa: E731

    # ---------------- Cover inputs (named Ticker, Scenario)
    cover["B2"], cover["B2"].font = "NVIDIA Stock Analysis: 3-statement forecast model", f(bold=True, size=14)
    cover["B3"] = f"Built {meta['built']} from verified SEC data (cutoff {meta['cutoff']}); consensus snapshot {meta['snapshot']}"
    cover["B3"].font = f(GREY, italic=True, size=9)
    cover["B5"], cover["C5"] = "Ticker", "NVDA"
    cover["B6"], cover["C6"] = "Scenario (1 Bear, 2 Base, 3 Bull)", 2
    cover["B7"], cover["C7"] = "Scenario name", "=CHOOSE(Scenario,\"Bear\",\"Base\",\"Bull\")"
    for c in ("C5", "C6"):
        cover[c].font = f(BLUE, bold=True)
        cover[c].fill = KEY_FILL
    wb.defined_names["Ticker"] = DefinedName("Ticker", attr_text="Cover!$C$5")
    wb.defined_names["Scenario"] = DefinedName("Scenario", attr_text="Cover!$C$6")
    dv1 = DataValidation(type="list", formula1='"' + ",".join(tickers) + '"', allow_blank=False)
    dv2 = DataValidation(type="whole", operator="between", formula1="1", formula2="3")
    cover.add_data_validation(dv1)
    cover.add_data_validation(dv2)
    dv1.add("C5")
    dv2.add("C6")

    # ---------------- Historicals
    H = Sheet(ws_h, "Historicals (from Data; ratios calculated)")
    for i, c in enumerate(HIST):
        ws_h[f"{c}4"] = "=" + look('Ticker&"|fiscal_year"', i + 1)
    for i, c in enumerate(FC):
        ws_h[f"{c}4"] = f'="FY"&(VALUE(MID({HIST[-1]}4,3,4))+{i + 1})&"E"'
    labels = {"revenue": "Revenue", "datacenter_revenue": "Data Center revenue (NVDA; manual from 10-K)",
              "edge_revenue": "Edge Computing revenue (NVDA; revenue less Data Center)", "cost_of_revenue": "Cost of revenue",
              "gross_profit": "Gross profit", "rd_expense": "Research and development", "sga_expense": "Sales, general and administrative",
              "operating_income": "Operating income", "interest_income": "Interest income", "interest_expense": "Interest expense",
              "pretax_income": "Income before income tax", "income_tax": "Income tax", "net_income": "Net income",
              "shares_diluted_adj": "Diluted shares (m, split-adjusted)", "eps_diluted_adj": "Diluted EPS (USD, split-adjusted)",
              "depreciation_amortization": "Depreciation and amortisation", "sbc": "Stock-based compensation",
              "operating_cash_flow": "Cash from operations", "capex": "Capital expenditure", "buybacks": "Share repurchases",
              "dividends": "Dividends paid", "cash_and_equivalents": "Cash and cash equivalents",
              "st_investments": "Short-term investments (debt securities)", "accounts_receivable": "Accounts receivable",
              "inventory": "Inventory", "current_assets": "Total current assets", "ppe_net": "Property and equipment, net",
              "total_assets": "Total assets", "accounts_payable": "Accounts payable", "total_debt": "Total debt",
              "total_liabilities": "Total liabilities", "stockholders_equity": "Shareholders' equity"}
    H.section("Reported (Step 3 / Step 5 data)")
    for item in m.HIST_ITEMS:
        fmt = EPS if item == "eps_diluted_adj" else SHR if item == "shares_diluted_adj" else MONEY
        H.row(item, labels[item], lambda c, i, it=item: "=" + look(f'Ticker&"|{it}"', i + 1), None, fmt)
    hr = lambda code, c: f"{c}{H.rows[code]}"  # noqa: E731
    H.section("Derived (formulas)")
    H.row("segment_a", "Segment A: Data Center (NVDA) / total revenue (others)",
          lambda c, i: f"=IF({hr('datacenter_revenue', c)}>0,{hr('datacenter_revenue', c)},{hr('revenue', c)})", None)
    H.row("segment_b", "Segment B: Edge Computing (NVDA) / none (others)", lambda c, i: f"={hr('revenue', c)}-{hr('segment_a', c)}", None)
    H.row("other_opex", "Other operating expense (gross profit - R&D - SG&A - operating income)",
          lambda c, i: f"={hr('gross_profit', c)}-{hr('rd_expense', c)}-{hr('sga_expense', c)}-{hr('operating_income', c)}", None)
    H.row("other_nonoperating", "Other non-operating income (pre-tax - operating income - interest)",
          lambda c, i: f"={hr('pretax_income', c)}-{hr('operating_income', c)}-{hr('interest_income', c)}+{hr('interest_expense', c)}", None)
    H.row("cash_inv", "Cash and short-term investments", lambda c, i: f"={hr('cash_and_equivalents', c)}+{hr('st_investments', c)}", None)
    H.row("other_current_assets", "Other current assets", lambda c, i:
          f"={hr('current_assets', c)}-{hr('cash_inv', c)}-{hr('accounts_receivable', c)}-{hr('inventory', c)}", None)
    H.row("other_noncurrent_assets", "Other non-current assets", lambda c, i: f"={hr('total_assets', c)}-{hr('current_assets', c)}-{hr('ppe_net', c)}", None)
    H.row("other_liabilities", "Other liabilities (incl. minority interest)", lambda c, i:
          f"={hr('total_assets', c)}-{hr('stockholders_equity', c)}-{hr('accounts_payable', c)}-{hr('total_debt', c)}", None)
    H.row("fcf", "Free cash flow (CFO - capex)", lambda c, i: f"={hr('operating_cash_flow', c)}-{hr('capex', c)}", None)
    H.section("Drivers in history (for setting assumptions)")
    sd = lambda a, b: f"=IFERROR({a}/{b},0)"  # noqa: E731
    H.row("r_growth", "Revenue growth", lambda c, i: None if i == 0 else f"=IFERROR({hr('revenue', c)}/{hr('revenue', HIST[i - 1])}-1,0)", None, PCT)
    H.row("r_gm", "Gross margin", lambda c, i: sd(hr("gross_profit", c), hr("revenue", c)), None, PCT)
    H.row("r_rd", "R&D, % of revenue", lambda c, i: sd(hr("rd_expense", c), hr("revenue", c)), None, PCT)
    H.row("r_sga", "SG&A, % of revenue", lambda c, i: sd(hr("sga_expense", c), hr("revenue", c)), None, PCT)
    H.row("r_tax", "Effective tax rate", lambda c, i: sd(hr("income_tax", c), hr("pretax_income", c)), None, PCT)
    H.row("r_dso", "Receivable days", lambda c, i: f"=IFERROR({hr('accounts_receivable', c)}/{hr('revenue', c)}*365,0)", None, DAYS)
    H.row("r_dio", "Inventory days", lambda c, i: f"=IFERROR({hr('inventory', c)}/{hr('cost_of_revenue', c)}*365,0)", None, DAYS)
    H.row("r_dpo", "Payable days", lambda c, i: f"=IFERROR({hr('accounts_payable', c)}/{hr('cost_of_revenue', c)}*365,0)", None, DAYS)
    H.row("r_capex", "Capex, % of revenue", lambda c, i: sd(hr("capex", c), hr("revenue", c)), None, PCT)
    H.row("r_bb", "Buybacks, % of FCF", lambda c, i: sd(hr("buybacks", c), hr("fcf", c)), None, PCT)
    ws_h[f"B{H.next + 1}"] = "Missing history values for this ticker (treated as 0; see validation_step5.csv):"
    ws_h[f"C{H.next + 1}"] = f"=SUMPRODUCT((Data!$B$2:$B${n_data}=Ticker)*Data!$I$2:$I${n_data})"
    missing_cell = f"Historicals!C{H.next + 1}"

    # ---------------- Assumptions (Bear / Base / Bull / Selected)
    ws_a["A1"], ws_a["A1"].font = "Assumptions: selected ticker, all scenarios (edit config/model.yaml, then rebuild)", f(bold=True, size=12)
    ws_a["A2"] = "=\"Ticker \"&Ticker&\" | scenario \"&Cover!C7&\" | Selected = CHOOSE(Scenario, Bear, Base, Bull)\""
    ws_a["A2"].font = f(GREY, italic=True, size=9)
    for i, c in enumerate(["D", "E", "F", "G", "H"]):
        ws_a[f"{c}4"] = f"=Historicals!{FC[i]}4"
        ws_a[f"{c}4"].font = f(bold=True)
        ws_a[f"{c}4"].fill = HEAD_FILL
    ws_a["B4"], ws_a["C4"], ws_a["I4"] = "Driver / scenario", "Unit", "Reason (base case)"
    for c in ("B4", "C4", "I4"):
        ws_a[c].font = f(bold=True)
    ws_a.column_dimensions["A"].width = 22
    ws_a.column_dimensions["B"].width = 52
    ws_a.column_dimensions["I"].width = 110
    sel = {}
    r = 6
    for d in m.DRIVERS:
        label, unit = m.DRIVER_LABELS[d]
        fmt = PCT if unit == "%" else DAYS if unit == "days" else MONEY
        ws_a[f"A{r}"], ws_a[f"B{r}"], ws_a[f"C{r}"] = d, label, unit
        ws_a[f"A{r}"].font, ws_a[f"B{r}"].font = f(GREY, size=8), f(bold=True)
        ws_a[f"I{r}"] = f'=IFERROR(INDEX(AssumptionsData!$I$2:$I${n_ad},MATCH(Ticker&"|{d}|Base",AssumptionsData!$A$2:$A${n_ad},0)),"")'
        ws_a[f"I{r}"].font = f(size=9)
        ws_a[f"I{r}"].alignment = Alignment(wrap_text=False)
        for j, s in enumerate(["Bear", "Base", "Bull"]):
            rr = r + 1 + j
            ws_a[f"B{rr}"] = f"  {s}"
            for k, c in enumerate(["D", "E", "F", "G", "H"]):
                ws_a[f"{c}{rr}"] = f'=IFERROR(INDEX(AssumptionsData!$D$2:$H${n_ad},MATCH(Ticker&"|{d}|{s}",AssumptionsData!$A$2:$A${n_ad},0),{k + 1}),0)'
                ws_a[f"{c}{rr}"].font = f(GREEN)
                ws_a[f"{c}{rr}"].number_format = fmt
        rs = r + 4
        ws_a[f"B{rs}"] = "  Selected"
        ws_a[f"B{rs}"].font = f(bold=True)
        for c in ["D", "E", "F", "G", "H"]:
            ws_a[f"{c}{rs}"] = f"=CHOOSE(Scenario,{c}{r + 1},{c}{r + 2},{c}{r + 3})"
            ws_a[f"{c}{rs}"].font = f(bold=True)
            ws_a[f"{c}{rs}"].number_format = fmt
            ws_a[f"{c}{rs}"].fill = KEY_FILL
        sel[d] = rs
        r += 6
    A = lambda d, c: f"Assumptions!{ACOL[c]}{sel[d]}"  # noqa: E731

    S, IS, BS, CF = (Sheet(ws, t) for ws, t in ((ws_s, "Schedules"), (ws_is, "Income statement"),
                                                  (ws_bs, "Balance sheet"), (ws_cf, "Cash flow statement")))
    hist = lambda code: (lambda c, i: f"=Historicals!{c}{H.rows[code]}")  # noqa: E731
    Hd = lambda code, c: f"Historicals!{c}{H.rows[code]}"  # noqa: E731
    # rows are created in dependency-free order; formulas only reference row numbers, so forward references are fine
    # Income statement
    IS.section("Revenue")
    IS.row("segment_a", "Segment A: Data Center (NVDA) / total (others)", hist("segment_a"), lambda c, i: f"={prev(c)}{IS.rows['segment_a']}*(1+{A('datacenter_growth', c)})")
    IS.row("segment_b", "Segment B: Edge Computing (NVDA)", hist("segment_b"), lambda c, i: f"={prev(c)}{IS.rows['segment_b']}*(1+{A('edge_growth', c)})")
    IS.row("revenue", "Revenue", hist("revenue"), lambda c, i: f"={c}{IS.rows['segment_a']}+{c}{IS.rows['segment_b']}", bold=True)
    IS.row("growth", "  growth", lambda c, i: None if i == 0 else f"=IFERROR({c}{IS.rows['revenue']}/{HIST[i - 1]}{IS.rows['revenue']}-1,0)",
           lambda c, i: f"=IFERROR({c}{IS.rows['revenue']}/{prev(c)}{IS.rows['revenue']}-1,0)", PCT)
    IS.row("cost_of_revenue", "Cost of revenue", hist("cost_of_revenue"), lambda c, i: f"={c}{IS.rows['revenue']}*(1-{A('gross_margin', c)})")
    IS.row("gross_profit", "Gross profit", hist("gross_profit"), lambda c, i: f"={c}{IS.rows['revenue']}-{c}{IS.rows['cost_of_revenue']}", bold=True)
    IS.row("gm", "  gross margin", lambda c, i: f"=IFERROR({c}{IS.rows['gross_profit']}/{c}{IS.rows['revenue']},0)",
           lambda c, i: f"=IFERROR({c}{IS.rows['gross_profit']}/{c}{IS.rows['revenue']},0)", PCT)
    IS.row("rd_expense", "Research and development", hist("rd_expense"), lambda c, i: f"={c}{IS.rows['revenue']}*{A('rd_pct_revenue', c)}")
    IS.row("sga_expense", "Sales, general and administrative", hist("sga_expense"), lambda c, i: f"={c}{IS.rows['revenue']}*{A('sga_pct_revenue', c)}")
    IS.row("other_opex", "Other operating expense", hist("other_opex"), lambda c, i: f"={c}{IS.rows['revenue']}*{A('other_opex_pct_revenue', c)}")
    IS.row("operating_income", "Operating income (EBIT)", hist("operating_income"),
           lambda c, i: f"={c}{IS.rows['gross_profit']}-{c}{IS.rows['rd_expense']}-{c}{IS.rows['sga_expense']}-{c}{IS.rows['other_opex']}", bold=True)
    IS.row("interest_income", "Interest income (yield x opening cash and investments)", hist("interest_income"), lambda c, i: f"={A('yield_on_cash', c)}*Schedules!{c}{{cash_open}}")
    IS.row("interest_expense", "Interest expense (rate x opening debt)", hist("interest_expense"), lambda c, i: f"={A('cost_of_debt', c)}*Schedules!{c}{{debt_open}}")
    IS.row("other_nonoperating", "Other non-operating income (history only; not forecast)", hist("other_nonoperating"), None)
    IS.row("pretax_income", "Income before income tax", hist("pretax_income"),
           lambda c, i: f"={c}{IS.rows['operating_income']}+{c}{IS.rows['interest_income']}-{c}{IS.rows['interest_expense']}", bold=True)
    IS.row("income_tax", "Income tax", hist("income_tax"), lambda c, i: f"={c}{IS.rows['pretax_income']}*{A('tax_rate', c)}")
    IS.row("net_income", "Net income", hist("net_income"), lambda c, i: f"={c}{IS.rows['pretax_income']}-{c}{IS.rows['income_tax']}", bold=True)
    IS.row("shares", "Diluted shares (m)", hist("shares_diluted_adj"), lambda c, i: f"=Schedules!{c}{{shares_close}}", SHR)
    IS.row("eps", "Diluted EPS (USD; history as reported, split-adjusted)", hist("eps_diluted_adj"),
           lambda c, i: f"=IFERROR({c}{IS.rows['net_income']}/{c}{IS.rows['shares']},0)", EPS, bold=True)

    # Schedules
    S.section("Working capital")
    S.row("ar", "Accounts receivable (revenue x DSO / 365)", hist("accounts_receivable"), lambda c, i: f"=IS!{c}{IS.rows['revenue']}*{A('dso_days', c)}/365")
    S.row("inv", "Inventory (cost of revenue x DIO / 365)", hist("inventory"), lambda c, i: f"=IS!{c}{IS.rows['cost_of_revenue']}*{A('dio_days', c)}/365")
    S.row("ap", "Accounts payable (cost of revenue x DPO / 365)", hist("accounts_payable"), lambda c, i: f"=IS!{c}{IS.rows['cost_of_revenue']}*{A('dpo_days', c)}/365")
    S.row("d_ar", "Increase in receivables", None, lambda c, i: f"={c}{S.rows['ar']}-{prev(c)}{S.rows['ar']}")
    S.row("d_inv", "Increase in inventory", None, lambda c, i: f"={c}{S.rows['inv']}-{prev(c)}{S.rows['inv']}")
    S.row("d_ap", "Increase in payables", None, lambda c, i: f"={c}{S.rows['ap']}-{prev(c)}{S.rows['ap']}")
    S.section("Property and equipment")
    S.row("ppe_open", "Opening PP&E", None, lambda c, i: f"={prev(c)}{{ppe_close}}")
    S.row("capex", "Capex (revenue x capex %)", hist("capex"), lambda c, i: f"=IS!{c}{IS.rows['revenue']}*{A('capex_pct_revenue', c)}")
    S.row("da", "D&A (revenue x D&A %)", hist("depreciation_amortization"), lambda c, i: f"=IS!{c}{IS.rows['revenue']}*{A('da_pct_revenue', c)}")
    S.row("ppe_close", "Closing PP&E", hist("ppe_net"), lambda c, i: f"={c}{S.rows['ppe_open']}+{c}{S.rows['capex']}-{c}{S.rows['da']}", bold=True)
    S.section("Debt")
    S.row("debt_open", "Opening debt", None, lambda c, i: f"={prev(c)}{{debt_close}}")
    S.row("issuance", "Net debt issuance (assumption)", None, lambda c, i: f"={A('net_debt_issuance', c)}")
    S.row("debt_close", "Closing debt", hist("total_debt"), lambda c, i: f"={c}{S.rows['debt_open']}+{c}{S.rows['issuance']}", bold=True)
    S.section("Shareholders' equity")
    S.row("eq_open", "Opening equity", None, lambda c, i: f"={prev(c)}{{eq_close}}")
    S.row("eq_ni", "Net income", None, lambda c, i: f"=IS!{c}{IS.rows['net_income']}")
    S.row("sbc", "Stock-based compensation (revenue x SBC %)", hist("sbc"), lambda c, i: f"=IS!{c}{IS.rows['revenue']}*{A('sbc_pct_revenue', c)}")
    S.row("eq_bb", "Share repurchases", None, lambda c, i: f"=CF!{c}{{cf_bb}}")
    S.row("eq_div", "Dividends", None, lambda c, i: f"=CF!{c}{{cf_div}}")
    S.row("eq_close", "Closing equity", hist("stockholders_equity"),
          lambda c, i: f"={c}{S.rows['eq_open']}+{c}{S.rows['eq_ni']}+{c}{S.rows['sbc']}-{c}{S.rows['eq_bb']}-{c}{S.rows['eq_div']}", bold=True)
    S.section("Diluted shares (m)")
    S.row("shares_close", "Closing diluted shares", hist("shares_diluted_adj"), lambda c, i: f"={prev(c)}{{shares_close}}*(1+{A('share_change', c)})", SHR, bold=True)
    S.section("Cash and short-term investments")
    S.row("cash_open", "Opening cash and investments", None, lambda c, i: f"={prev(c)}{{cash_close}}")
    S.row("cash_change", "Net change in cash (cash flow statement)", None, lambda c, i: f"=CF!{c}{{cf_net}}")
    S.row("cash_close", "Closing cash and investments", hist("cash_inv"), lambda c, i: f"={c}{S.rows['cash_open']}+{c}{S.rows['cash_change']}", bold=True)

    # Cash flow
    CF.section("Operating")
    CF.row("cf_ni", "Net income", hist("net_income"), lambda c, i: f"=IS!{c}{IS.rows['net_income']}")
    CF.row("cf_da", "Depreciation and amortisation", hist("depreciation_amortization"), lambda c, i: f"=Schedules!{c}{S.rows['da']}")
    CF.row("cf_sbc", "Stock-based compensation", hist("sbc"), lambda c, i: f"=Schedules!{c}{S.rows['sbc']}")
    CF.row("cf_ar", "Less: increase in receivables", None, lambda c, i: f"=-Schedules!{c}{S.rows['d_ar']}")
    CF.row("cf_inv", "Less: increase in inventory", None, lambda c, i: f"=-Schedules!{c}{S.rows['d_inv']}")
    CF.row("cf_ap", "Add: increase in payables", None, lambda c, i: f"=Schedules!{c}{S.rows['d_ap']}")
    CF.row("cf_cfo", "Cash from operations (history as reported)", hist("operating_cash_flow"),
           lambda c, i: f"=SUM({c}{CF.rows['cf_ni']}:{c}{CF.rows['cf_ap']})", bold=True)
    CF.row("cf_capex", "Capital expenditure", hist("capex"), lambda c, i: f"=Schedules!{c}{S.rows['capex']}")
    CF.row("cf_fcf", "Free cash flow", lambda c, i: f"={c}{CF.rows['cf_cfo']}-{c}{CF.rows['cf_capex']}",
           lambda c, i: f"={c}{CF.rows['cf_cfo']}-{c}{CF.rows['cf_capex']}", bold=True)
    CF.section("Financing")
    CF.row("cf_bb", "Share repurchases (FCF x buyback %, if FCF > 0)", hist("buybacks"), lambda c, i: f"=MAX({c}{CF.rows['cf_fcf']},0)*{A('buyback_pct_fcf', c)}")
    CF.row("cf_div", "Dividends (net income x payout, if > 0)", hist("dividends"), lambda c, i: f"=MAX({c}{CF.rows['cf_ni']},0)*{A('dividend_payout', c)}")
    CF.row("cf_iss", "Net debt issuance", None, lambda c, i: f"=Schedules!{c}{S.rows['issuance']}")
    CF.row("cf_net", "Net change in cash and investments", None,
           lambda c, i: f"={c}{CF.rows['cf_fcf']}-{c}{CF.rows['cf_bb']}-{c}{CF.rows['cf_div']}+{c}{CF.rows['cf_iss']}", bold=True)

    # Balance sheet
    BS.section("Assets")
    BS.row("bs_cash", "Cash and short-term investments", hist("cash_inv"), lambda c, i: f"=Schedules!{c}{S.rows['cash_close']}")
    BS.row("bs_ar", "Accounts receivable", hist("accounts_receivable"), lambda c, i: f"=Schedules!{c}{S.rows['ar']}")
    BS.row("bs_inv", "Inventory", hist("inventory"), lambda c, i: f"=Schedules!{c}{S.rows['inv']}")
    BS.row("bs_oca", "Other current assets (held flat)", hist("other_current_assets"), lambda c, i: f"={prev(c)}{BS.rows['bs_oca']}")
    BS.row("bs_ppe", "Property and equipment, net", hist("ppe_net"), lambda c, i: f"=Schedules!{c}{S.rows['ppe_close']}")
    BS.row("bs_onca", "Other non-current assets (held flat)", hist("other_noncurrent_assets"), lambda c, i: f"={prev(c)}{BS.rows['bs_onca']}")
    BS.row("bs_ta", "Total assets", lambda c, i: f"=SUM({c}{BS.rows['bs_cash']}:{c}{BS.rows['bs_onca']})",
           lambda c, i: f"=SUM({c}{BS.rows['bs_cash']}:{c}{BS.rows['bs_onca']})", bold=True)
    BS.section("Liabilities and equity")
    BS.row("bs_ap", "Accounts payable", hist("accounts_payable"), lambda c, i: f"=Schedules!{c}{S.rows['ap']}")
    BS.row("bs_debt", "Total debt", hist("total_debt"), lambda c, i: f"=Schedules!{c}{S.rows['debt_close']}")
    BS.row("bs_ol", "Other liabilities (held flat)", hist("other_liabilities"), lambda c, i: f"={prev(c)}{BS.rows['bs_ol']}")
    BS.row("bs_eq", "Shareholders' equity", hist("stockholders_equity"), lambda c, i: f"=Schedules!{c}{S.rows['eq_close']}")
    BS.row("bs_tle", "Total liabilities and equity", lambda c, i: f"=SUM({c}{BS.rows['bs_ap']}:{c}{BS.rows['bs_eq']})",
           lambda c, i: f"=SUM({c}{BS.rows['bs_ap']}:{c}{BS.rows['bs_eq']})", bold=True)
    BS.row("bs_check", "Balance check: assets - (liabilities + equity), must be 0",
           lambda c, i: f"={c}{BS.rows['bs_ta']}-{c}{BS.rows['bs_tle']}", lambda c, i: f"={c}{BS.rows['bs_ta']}-{c}{BS.rows['bs_tle']}")
    BS.row("bs_netcash", "Net cash (cash and investments - debt)", lambda c, i: f"={c}{BS.rows['bs_cash']}-{c}{BS.rows['bs_debt']}",
           lambda c, i: f"={c}{BS.rows['bs_cash']}-{c}{BS.rows['bs_debt']}")

    # resolve forward references written as {name}
    fwd = {"cash_open": S.rows["cash_open"], "debt_open": S.rows["debt_open"], "shares_close": S.rows["shares_close"],
           "ppe_close": S.rows["ppe_close"], "debt_close": S.rows["debt_close"], "eq_close": S.rows["eq_close"],
           "cash_close": S.rows["cash_close"], "cf_bb": CF.rows["cf_bb"], "cf_div": CF.rows["cf_div"], "cf_net": CF.rows["cf_net"]}
    for ws in (ws_is, ws_s, ws_cf, ws_bs):
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and "{" in c.value:
                    c.value = c.value.format(**fwd)
    from openpyxl.formatting.rule import FormulaRule
    chk = BS.rows["bs_check"]
    ws_bs.conditional_formatting.add(f"C{chk}:L{chk}", FormulaRule(formula=[f"ABS(C{chk})>=0.5"], fill=PatternFill("solid", fgColor="FFC7CE"), font=Font(color="9C0006")))

    # ---------------- Cover outputs
    cover["B9"], cover["B9"].font = "Key outputs (selected ticker and scenario)", f(bold=True)
    for i, c in enumerate(["C", "D", "E", "F", "G", "H"]):
        src = HIST[-1] if i == 0 else FC[i - 1]
        cover[f"{c}10"] = f"=Historicals!{src}4"
        cover[f"{c}10"].font = f(bold=True)
        cover[f"{c}10"].fill = HEAD_FILL
    outs = [("Revenue ($m)", "IS", IS.rows["revenue"], MONEY), ("  growth", "IS", IS.rows["growth"], PCT),
            ("Gross margin", "IS", IS.rows["gm"], PCT), ("Operating income ($m)", "IS", IS.rows["operating_income"], MONEY),
            ("Net income ($m)", "IS", IS.rows["net_income"], MONEY), ("Diluted EPS (USD)", "IS", IS.rows["eps"], EPS),
            ("Free cash flow ($m)", "CF", CF.rows["cf_fcf"], MONEY), ("Net cash ($m)", "BS", BS.rows["bs_netcash"], MONEY)]
    for k, (label, sh, row, fmt) in enumerate(outs):
        rr = 11 + k
        cover[f"B{rr}"] = label
        for i, c in enumerate(["C", "D", "E", "F", "G", "H"]):
            src = HIST[-1] if i == 0 else FC[i - 1]
            cover[f"{c}{rr}"] = f"={sh}!{src}{row}"
            cover[f"{c}{rr}"].number_format = fmt
            cover[f"{c}{rr}"].font = f(GREEN)
    rr = 11 + len(outs)
    cover[f"B{rr}"] = "Consensus revenue ($m, Step 4 snapshot)"
    cover[f"B{rr + 1}"] = "Consensus EPS (USD, providers' adjusted basis, I-47)"
    for i, c in enumerate(["D", "E"]):
        cover[f"{c}{rr}"] = "=" + look('Ticker&"|consensus_revenue"', i + 1)
        cover[f"{c}{rr + 1}"] = "=" + look('Ticker&"|consensus_eps"', i + 1)
        cover[f"{c}{rr}"].number_format, cover[f"{c}{rr + 1}"].number_format = MONEY, EPS
    cover[f"B{rr + 3}"], cover[f"B{rr + 3}"].font = "Checks", f(bold=True)
    cover[f"B{rr + 4}"] = "Balance sheet balances in every year (sum of |check| < 1)"
    cover[f"C{rr + 4}"] = f'=IF(SUMPRODUCT(ABS(BS!C{chk}:L{chk}))<1,"OK","CHECK")'
    cover[f"B{rr + 5}"] = "History values missing for this ticker (treated as 0)"
    cover[f"C{rr + 5}"] = f"={missing_cell}"
    cover[f"B{rr + 6}"] = "Balance check total (should be 0)"
    cover[f"C{rr + 6}"] = f"=SUMPRODUCT(ABS(BS!C{chk}:L{chk}))"
    cover[f"C{rr + 6}"].number_format = "0.000000"
    for c in (f"C{rr + 4}", f"C{rr + 5}"):
        cover[c].font = f(bold=True)
    notes = ["How to use: change Ticker (C5) or Scenario (C6). Every other cell is a formula; to change an assumption, edit config/model.yaml and rerun python\\run_step5.py model.",
             "Colours: blue = input (Data, AssumptionsData), black = formula, green = link to another sheet, yellow = switch or selected assumption.",
             "NVIDIA's drivers are argued (Assumptions, column I); peers use mechanical defaults (S5-D6) so the switch works; they are not investment views.",
             "Simplifications (S5-D5): other assets and liabilities held flat; all D&A runs through PP&E; other non-operating income not forecast; interest on opening balances (no circularity)."]
    for k, n in enumerate(notes):
        cover[f"B{rr + 8 + k}"] = n
        cover[f"B{rr + 8 + k}"].font = f(GREY, italic=True, size=9)
    cover.column_dimensions["B"].width = 58
    for c in "CDEFGH":
        cover.column_dimensions[c].width = 13
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None and c.font.name != FONT:
                    c.font = Font(name=FONT, size=c.font.size or 10, bold=c.font.bold, italic=c.font.italic, color=c.font.color)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.calculation.fullCalcOnLoad = True
    wb.save(out)
    return out


ROW_MAP = {  # engine key -> (sheet, row code) for the Excel-vs-Python comparison
    "segment_a": ("IS", "segment_a"), "segment_b": ("IS", "segment_b"), "revenue": ("IS", "revenue"),
    "cost_of_revenue": ("IS", "cost_of_revenue"), "gross_profit": ("IS", "gross_profit"), "operating_income": ("IS", "operating_income"),
    "interest_income": ("IS", "interest_income"), "interest_expense": ("IS", "interest_expense"), "pretax_income": ("IS", "pretax_income"),
    "net_income": ("IS", "net_income"), "eps": ("IS", "eps"), "operating_cash_flow": ("CF", "cf_cfo"), "fcf": ("CF", "cf_fcf"),
    "buybacks": ("CF", "cf_bb"), "dividends": ("CF", "cf_div"), "cash_inv": ("BS", "bs_cash"), "total_assets": ("BS", "bs_ta"),
    "stockholders_equity": ("BS", "bs_eq"), "balance_check": ("BS", "bs_check"),
}
