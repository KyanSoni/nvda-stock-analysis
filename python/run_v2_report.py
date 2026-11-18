"""Version 2, V2.8: the deliverables, built only from the V2.1-V2.7 outputs (V2-D6). Offline.

  excel/SP500_Screener.xlsx       Read me, Screener (today), Backtest, Holdings, Robustness, Data quality
  docs/v2/v2_results.md           the two-page results note: question, answer, evidence, limits
  docs/v2/exhibits/v2_growth.svg  growth of $1: the screen, the equal-weight universe, SPY

Every number in the note and workbook is read from data/clean/v2; nothing is typed in. Exit code 0 = files written and the
R checks pass.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date

import pandas as pd
import yaml
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from common import PROJECT_ROOT

CFG = PROJECT_ROOT / "config" / "v2.yaml"
CLEAN = PROJECT_ROOT / "data" / "clean" / "v2"
HEAD = PatternFill("solid", fgColor="1F3864")
BAND = PatternFill("solid", fgColor="D9E1F2")


def read(path, **k) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=False, na_values=[""], **k)


def load(cfg: dict) -> dict:
    d = {"today": read(CLEAN / "scores" / "screener_today.csv", dtype={"ticker": str, "cik": str}),
         "scores": read(CLEAN / "scores" / "scores_by_date.csv", dtype={"ticker": str, "cik": str, "date": str}),
         "stats": read(CLEAN / "backtest" / "stats.csv").set_index("series"),
         "periods": read(CLEAN / "backtest" / "periods.csv", dtype={"start": str, "end": str}),
         "holdings": read(CLEAN / "backtest" / "holdings.csv", dtype={"trade_date": str, "ticker": str}),
         "rob": read(CLEAN / "backtest" / "robustness.csv"),
         "nav": read(CLEAN / "backtest" / "nav_daily.csv", dtype={"date": str}),
         "seccov": read(CLEAN / "sec" / "coverage_sec.csv", dtype={"date": str}),
         "pricecov": read(CLEAN / "prices" / "price_coverage.csv", dtype={"date": str}),
         "unicov": read(PROJECT_ROOT / cfg["universe"]["clean_dir"] / "coverage.csv", dtype={"date": str})}
    rec = CLEAN / "scores" / "v1_reconcile.csv"
    d["rec"] = read(rec) if rec.exists() else pd.DataFrame()
    d["today"]["ranked"] = d["today"]["ranked"].astype(str) == "True"
    d["today"] = d["today"].assign(_r=pd.to_numeric(d["today"]["rank"], errors="coerce")).sort_values(["_r", "ticker"], na_position="last").drop(columns="_r")
    d["holdings"] = d["holdings"].sort_values(["trade_date", "rank"])
    d["scores"]["ranked"] = d["scores"]["ranked"].astype(str) == "True"
    return d


# ---------- workbook ----------

def sheet(wb, title, df: pd.DataFrame, fmts: dict | None = None, widths: dict | None = None, note: str = ""):
    ws = wb.create_sheet(title)
    r0 = 1
    if note:
        ws.cell(1, 1, note).font = Font(name="Calibri", size=11, italic=True)
        r0 = 3
    for j, c in enumerate(df.columns, 1):
        x = ws.cell(r0, j, c)
        x.font, x.fill = Font(name="Calibri", size=11, bold=True, color="FFFFFF"), HEAD
        x.alignment = Alignment(wrap_text=True, vertical="center")
    for i, row in enumerate(df.itertuples(index=False), r0 + 1):
        for j, v in enumerate(row, 1):
            v = None if (isinstance(v, float) and v != v) else v
            x = ws.cell(i, j, v)
            x.font = Font(name="Calibri", size=11)
            f = (fmts or {}).get(df.columns[j - 1])
            if f:
                x.number_format = f
            if (i - r0) % 2 == 0:
                x.fill = BAND
    for j, c in enumerate(df.columns, 1):
        ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(c, max(10, min(40, len(str(c)) + 2)))
    ws.freeze_panes = ws.cell(r0 + 1, 3)
    return ws


def workbook(d: dict, cfg: dict, path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Read me"
    s, n = d["stats"], cfg["backtest"]["holdings"]
    lines = [("S&P 500 quality screen and backtest (Version 2)", True),
             ("Question: do companies that score well on the project's quality scorecard beat the S&P 500 over the next year?", False),
             (f"Answer, {s.loc['strategy', 'start']} to {s.loc['strategy', 'end']}: top {n} {s.loc['strategy', 'cagr']:.2%} a year net of costs, "
              f"SPY {s.loc['spy', 'cagr']:.2%}, equal-weight ranked universe {s.loc['universe_ew', 'cagr']:.2%}.", True),
             ("", False),
             ("Method: S&P 500 members at each 1 April rebuilt from Wikipedia's change history (V2.1); each member's SEC filer at that date (V2.2);", False),
             ("annual-report facts filed before the date only (V2.3); prices from Yahoo Finance (V2.4); nine filing-based scorecard tests (V2.5);", False),
             (f"top {n} by total points (a test that cannot be scored takes its sector's median), ties by ROIC, equal weights, held a year, {cfg['backtest']['cost_per_side']:.1%} cost a side (V2.6); robustness (V2.7).", False),
             ("Financials and Real Estate are excluded (the tests do not fit banks, insurers or REITs).", False),
             ("", False),
             ("Limits: Yahoo has no prices for most companies taken over or delisted, so they cannot be held (survivorship, I-80);", False),
             ("the equal-weight universe shares that limit, so 'screen vs universe' is the cleaner comparison. Sectors of former members come from SIC codes (V2-D11).", False),
             ("Decisions V2-D1 to V2-D16 are in docs/decision_log.md; issues in docs/issue_log.md; the note is docs/v2/v2_results.md.", False),
             ("Analysis for a portfolio project, not investment advice.", False)]
    for i, (t, b) in enumerate(lines, 1):
        ws.cell(i, 1, t).font = Font(name="Calibri", size=14 if i == 1 else 11, bold=b)
    ws.column_dimensions["A"].width = 150

    t = d["today"]
    tests = cfg["scores"]["tests"]
    cols = ["rank", "ticker", "security", "sector", "score_total", "points", "imputed_points", "tests_scored", "score_pct", "roic", "revenue_cagr_5y", "pe_fy", "roe_5y_avg",
            "quick_ratio", "gross_margin", "gross_margin_vs_sector", "fcf_conversion", "net_debt_to_ebitda", "shares_change_5y"] + [f"t{k}" for k in tests] + \
           ["fy0_end", "price_as_traded", "other_classes", "flags", "why_not_ranked"]
    pct = "0.0%"
    sheet(wb, "Screener", t[cols], {"score_pct": pct, "roic": pct, "revenue_cagr_5y": pct, "roe_5y_avg": pct, "gross_margin": pct, "gross_margin_vs_sector": pct,
                                    "fcf_conversion": pct, "shares_change_5y": pct, "pe_fy": "0.0", "quick_ratio": "0.00", "net_debt_to_ebitda": "0.00",
                                    "price_as_traded": "0.00"},
          {"security": 30, "sector": 22, "flags": 60, "why_not_ranked": 22},
          note=f"Ranked on {t['date'].iloc[0]} (prices {t['trade_date'].iloc[0]}). Tests: " +
               "; ".join(f"t{k} {v['name']} (pass {v['pass']}, near {v['near']})" for k, v in tests.items()))
    st = d["stats"].reset_index()
    sheet(wb, "Backtest", st, {"total_return": pct, "cagr": pct, "volatility": pct, "max_drawdown": pct, "sharpe": "0.00", "tracking_error": pct,
                               "information_ratio": "0.00", "years": "0.0"}, note="Statistics on daily values; Sharpe over 0% (rf = 0, labelled).")
    p = d["periods"]
    ws = wb["Backtest"]
    r = ws.max_row + 3
    for j, c in enumerate(p.columns, 1):
        x = ws.cell(r, j, c)
        x.font, x.fill = Font(name="Calibri", size=11, bold=True, color="FFFFFF"), HEAD
    for i, row in enumerate(p.itertuples(index=False), r + 1):
        for j, v in enumerate(row, 1):
            x = ws.cell(i, j, None if (isinstance(v, float) and v != v) else v)
            if p.columns[j - 1] in ("return", "universe_ew", "spy", "excess_vs_spy", "excess_vs_universe", "turnover", "cost"):
                x.number_format = pct
    sheet(wb, "Holdings", d["holdings"], {"return": pct, "roic": pct}, {"security": 30, "sector": 22})
    sheet(wb, "Robustness", d["rob"], {"cagr": pct, "volatility": pct, "max_drawdown": pct, "vs_spy_cagr": pct, "sharpe": "0.00", "information_ratio": "0.00"},
          {"variant": 52, "note": 80})
    sc = d["scores"]
    dq = d["unicov"][["date", "members"]].merge(d["seccov"][["date", "resolved"]], on="date", how="left") \
        .merge(d["pricecov"][["date", "with_price"]], on="date", how="left") \
        .merge(sc.groupby("date").agg(scored=("ticker", "size"), ranked=("ranked", "sum")).reset_index(), on="date", how="left")
    sheet(wb, "Data quality", dq, note="members (V2.1) -> resolved SEC filer (V2.2; all sectors) -> usable price (excluded sectors removed) -> scored -> ranked")
    if len(d["rec"]):
        ws = wb["Data quality"]
        r = ws.max_row + 3
        ws.cell(r - 1, 1, "V2 engine vs Version 1 (same fiscal year)").font = Font(name="Calibri", size=11, bold=True)
        for j, c in enumerate(d["rec"].columns, 1):
            x = ws.cell(r, j, c)
            x.font, x.fill = Font(name="Calibri", size=11, bold=True, color="FFFFFF"), HEAD
        for i, row in enumerate(d["rec"].itertuples(index=False), r + 1):
            for j, v in enumerate(row, 1):
                ws.cell(i, j, None if (isinstance(v, float) and v != v) else v)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ---------- chart ----------

def svg(nav: pd.DataFrame, labels: dict, path) -> None:
    W, H, L, R, T, B = 760, 340, 60, 170, 20, 40
    x0, x1 = pd.Timestamp(nav["date"].iloc[0]), pd.Timestamp(nav["date"].iloc[-1])
    hi = max(nav[c].max() for c in labels) * 1.05
    sx = lambda d: L + (pd.Timestamp(d) - x0).days / max((x1 - x0).days, 1) * (W - L - R)   # noqa: E731
    sy = lambda v: T + (1 - v / hi) * (H - T - B)                                            # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Calibri, Arial, sans-serif" font-size="12">',
           f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>']
    step = 0.5 if hi <= 4 else (1 if hi <= 8 else 2)
    v = 0.0
    while v <= hi:
        out.append(f'<line x1="{L}" y1="{sy(v):.1f}" x2="{W - R}" y2="{sy(v):.1f}" stroke="#e5e5e5"/>')
        out.append(f'<text x="{L - 6}" y="{sy(v) + 4:.1f}" text-anchor="end" fill="#555555">${v:.1f}</text>')
        v += step
    for y in range(x0.year + 1, x1.year + 1):
        d = f"{y}-01-01"
        out.append(f'<text x="{sx(d):.1f}" y="{H - B + 18}" text-anchor="middle" fill="#555555">{y}</text>')
    colors = {"strategy": "#1F3864", "universe_ew": "#8FAADC", "spy": "#C55A11"}
    pts = pd.concat([nav.iloc[::3], nav.iloc[[-1]]]).drop_duplicates("date")
    ys = {}
    for c in sorted(labels, key=lambda c: sy(nav[c].iloc[-1])):        # end labels top to bottom, at least 15px apart
        y = sy(nav[c].iloc[-1]) + 4
        ys[c] = max(y, max(ys.values()) + 15) if ys else y
    for c, lab in labels.items():
        p = " ".join(f"{sx(d):.1f},{sy(val):.1f}" for d, val in zip(pts["date"], pts[c]))
        out.append(f'<polyline fill="none" stroke="{colors[c]}" stroke-width="{2.2 if c == "strategy" else 1.6}" points="{p}"/>')
        out.append(f'<text x="{W - R + 8}" y="{ys[c]:.1f}" fill="{colors[c]}">{lab} ${nav[c].iloc[-1]:.2f}</text>')
    out.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------- note ----------

def note(d: dict, cfg: dict) -> str:
    s, p, rob, t = d["stats"], d["periods"], d["rob"], d["today"]
    n, cost = cfg["backtest"]["holdings"], cfg["backtest"]["cost_per_side"]
    st, sp, un = s.loc["strategy"], s.loc["spy"], s.loc["universe_ew"]
    beat_spy, beat_un = int((p["excess_vs_spy"] > 0).sum()), int((p["excess_vs_universe"] > 0).sum())
    gap_spy, gap_un = st["cagr"] - sp["cagr"], st["cagr"] - un["cagr"]
    # wording rule, one-point bands on CAGR: the universe gap measures the scorecard, the SPY gap what an investor would have got
    if gap_un > 0.01 and gap_spy > 0.01:
        verdict = "Yes"
    elif gap_un > 0.01:
        verdict = "Partly: the screen beat the companies it could rank, but only matched the S&P 500" if gap_spy >= -0.01 else \
                  "Partly: the screen beat the companies it could rank, but trailed the S&P 500"
    elif gap_un >= -0.01:
        verdict = "No clear effect"
    else:
        verdict = "No"
    rnd = rob[rob["variant"].str.startswith("Random")]
    rnote = rnd["note"].iloc[0] if len(rnd) else ""
    surv = rob[rob["variant"].str.startswith("Today's members")]
    rows = "\n".join(f"| {r.start[:7]} | {r['return']:+.1%} | {r.universe_ew:+.1%} | {r.spy:+.1%} | {r.excess_vs_spy:+.1%} |" for _, r in p.iterrows())
    robrows = "\n".join(f"| {r.variant} | {r.cagr:.2%} | {r.vs_spy_cagr:+.2%} |" for r in rob.itertuples())
    top = t[t["ranked"]].head(10)
    toprows = "\n".join(f"| {int(r['rank'])} | {r.ticker} | {r.security} | {r.sector} | {r.score_total:.1f}/18 ({int(r.tests_scored)} tests) | "
                        + (f"{r.roic:.0%} |" if pd.notna(r.roic) else "n/a |") for _, r in top.iterrows())
    nv = t[t["ticker"] == "NVDA"]
    nvs = (f"NVIDIA scores {nv.iloc[0]['score_total']:.1f}/18 today and ranks {int(nv.iloc[0]['rank'])} of {int(t['ranked'].sum())}."
           if len(nv) and nv.iloc[0]["ranked"] else "NVIDIA is not ranked today.")
    cov = d["pricecov"]
    apr = cov[cov["date"].str[5:] == cfg["backtest"]["rebalance_month_day"]]
    rec = d["rec"]
    rec_s = f"{int(rec['agree'].sum())}/{len(rec)} metric values for the six Version 1 companies agree with Version 1 within 0.5 points" if len(rec) else "Version 1 reconciliation not available"
    return f"""# Does quality pay? An S&P 500 screen, {st['start'][:4]}–{st['end'][:4]}

Version 2 of the NVIDIA project · {date.today().isoformat()} · every number below is read from `data/clean/v2` by `python/run_v2_report.py`.

**Question.** Do companies that score well on the project's quality scorecard (Step 4, filing-based version) beat the S&P 500 over the next year?
**Answer: {verdict}.** Buying the top {n} each 1 April from {st['start']} to {st['end']} returned **{st['cagr']:.2%} a year** after {cost:.1%} costs a side,
against **{sp['cagr']:.2%}** for SPY and **{un['cagr']:.2%}** for an equal-weight portfolio of every company the screen could rank. It beat SPY in
{beat_spy} of {len(p)} years and the equal-weight universe in {beat_un} of {len(p)}. Random {n}-stock portfolios from the same companies: {rnote}.

![Growth of $1](exhibits/v2_growth.svg)

| Series | CAGR | Volatility | Sharpe (rf 0) | Max drawdown | Information ratio vs SPY |
|---|---|---|---|---|---|
| Top {n} (net) | {st['cagr']:.2%} | {st['volatility']:.1%} | {st['sharpe']:.2f} | {st['max_drawdown']:.1%} | {st['information_ratio']:.2f} |
| Equal-weight ranked universe | {un['cagr']:.2%} | {un['volatility']:.1%} | {un['sharpe']:.2f} | {un['max_drawdown']:.1%} | {un['information_ratio']:.2f} |
| SPY | {sp['cagr']:.2%} | {sp['volatility']:.1%} | {sp['sharpe']:.2f} | {sp['max_drawdown']:.1%} | – |

**Year by year** (holding period starting each April)

| Start | Top {n} | Universe | SPY | vs SPY |
|---|---|---|---|---|
{rows}

## How robust is it?

| Variant (one change at a time) | CAGR | vs SPY |
|---|---|---|
{robrows}

Read the "today's members only" line as a warning, not a result: testing only companies still in the index
changes the result by {format(surv.iloc[0]['cagr'] - st['cagr'], '+.2%') + " a year" if len(surv) else "an unknown amount"}, the effect of the survivorship bias the point-in-time universe removes.

## Today's screen

{nvs} Top ten (full list in `excel/SP500_Screener.xlsx`):

| Rank | Ticker | Company | Sector | Points | ROIC |
|---|---|---|---|---|---|
{toprows}

## Method and limits

- **Universe (V2-D1).** Members at each date rebuilt from Wikipedia's dated change history; each member's SEC filer at that date is the one that filed an annual report in the prior 18 months (V2-D9). Financials and Real Estate excluded (V2-D2).
- **No look-ahead (V2-D12).** Only annual-report facts filed before the date; latest fiscal year; Version 1's formulas. {rec_s}.
- **Scorecard (V2-D3, V2-D13).** Nine of Step 4's ten tests (PEG needs consensus history that free sources do not keep); ROIC against a fixed 15% hurdle; gross margin against the sector median; at least {cfg['scores']['min_tests_scored']} tests to be ranked; a test a company cannot be scored on (an insurer's quick ratio, ROE on negative equity) takes its sector's median points, so data gaps neither help nor hurt.
- **Survivorship (I-80).** Yahoo has no prices for most companies taken over or delisted, so they cannot be held: usable prices for {apr['price_share'].min():.0%}–{apr['price_share'].max():.0%} of eligible members across April dates. The equal-weight universe has the same limit, so the screen-versus-universe gap is the cleaner measure of the scorecard's effect.
- **Sectors of former members** come from SEC SIC codes mapped to GICS (V2-D11); current members use Wikipedia's GICS.
- Holdings whose prices stop are held at their last price to the next rebalance (V2-D16). Costs {cost:.1%} a side on traded weight.

Analysis for a portfolio project, not investment advice. Decisions V2-D1 to V2-D16: `docs/decision_log.md`; issues I-72 onwards: `docs/issue_log.md`.
"""


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    d = load(cfg)
    xl = PROJECT_ROOT / cfg["outputs"]["workbook"]
    md = PROJECT_ROOT / cfg["outputs"]["note"]
    chart = md.parent / "exhibits" / "v2_growth.svg"
    workbook(d, cfg, xl)
    n = cfg["backtest"]["holdings"]
    svg(d["nav"], {"strategy": f"Top {n}", "universe_ew": "Universe EW", "spy": "SPY"}, chart)
    text = note(d, cfg)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(text, encoding="utf-8")
    from openpyxl import load_workbook
    wb = load_workbook(xl)
    s = d["stats"]
    cks = [("R1_workbook_sheets", wb.sheetnames == ["Read me", "Screener", "Backtest", "Holdings", "Robustness", "Data quality"], ", ".join(wb.sheetnames)),
           ("R2_note_numbers_match", f"{s.loc['strategy', 'cagr']:.2%}" in text and f"{s.loc['spy', 'cagr']:.2%}" in text, "CAGR in the note equals stats.csv"),
           ("R3_screener_rows", wb["Screener"].max_row - 3 == len(d["today"]), f"{len(d['today'])} companies on the Screener sheet"),
           ("R4_no_placeholders", "{" not in text and not re.search(r"\bnan\b", text, re.I), "no unfilled fields or nan in the note")]
    print(f"V2.8 report -> {xl.relative_to(PROJECT_ROOT)}, {md.relative_to(PROJECT_ROOT)}, {chart.relative_to(PROJECT_ROOT)}")
    for c, ok, dd in cks:
        print(f"  {'PASS' if ok else 'FAIL'}  {c}: {dd}")
    (CLEAN / "manifest_v2_report.json").write_text(json.dumps({"checks": [{"check": c, "passed": bool(ok), "detail": dd} for c, ok, dd in cks]}, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _ in cks) else 1


if __name__ == "__main__":
    sys.exit(main())
