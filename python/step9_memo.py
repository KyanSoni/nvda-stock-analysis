"""Step 9: the investment memo. Computes the 12-month target and rating (S9-D1, S9-D2) and every number the memo quotes
from the project's verified outputs, then renders docs/memo/memo_template.md into docs/memo/NVDA_investment_memo.md
with five exhibits (one SVG chart, four tables). Each number is listed with its source in memo_numbers.csv.

Every comparative claim the template makes ("highest of the six", "lowest of the six") is checked here against the data;
if a rerun with new data makes one false, the build stops instead of printing it (M1, M2 checks in run_step9.py).
"""
from __future__ import annotations

import math
import re
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from common import PROJECT_ROOT

CFG = PROJECT_ROOT / "config" / "memo.yaml"
COMPS_CFG = PROJECT_ROOT / "config" / "comps.yaml"
TEMPLATE = PROJECT_ROOT / "docs" / "memo" / "memo_template.md"
MEMO = PROJECT_ROOT / "docs" / "memo" / "NVDA_investment_memo.md"
SVG = PROJECT_ROOT / "docs" / "memo" / "exhibits" / "football_field.svg"
CLEAN = PROJECT_ROOT / "data" / "clean"
T = "NVDA"
rd = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)  # noqa: E731


def load_cfg(path: Path = CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def inputs() -> dict:
    """All files the memo reads (each already verified by its own step)."""
    return {"dcf_in": rd(CLEAN / "step6" / "dcf_inputs.csv"), "dcf_val": rd(CLEAN / "step6" / "dcf_values.csv"),
            "rev": rd(CLEAN / "step6" / "reverse_dcf.csv"), "wg": rd(CLEAN / "step6" / "sensitivity_wacc_g.csv"),
            "gm": rd(CLEAN / "step6" / "sensitivity_growth_margin.csv"), "fc": rd(CLEAN / "step5" / "forecast.csv"),
            "at": rd(CLEAN / "step5" / "assumptions.csv"), "md": rd(CLEAN / "step5" / "model_data.csv"),
            "est": rd(CLEAN / "step4" / "estimates.csv"), "est_manifest": (CLEAN / "step4" / "estimates_manifest.json"),
            "score": rd(CLEAN / "step4" / "exports" / "v_scorecard.csv"), "score_d": rd(CLEAN / "step4" / "exports" / "v_scorecard_detail.csv"),
            "tb": rd(CLEAN / "step7" / "comps_table.csv"), "st": rd(CLEAN / "step7" / "comps_stats.csv"),
            "imp": rd(CLEAN / "step7" / "comps_implied.csv"), "reg": rd(CLEAN / "step7" / "comps_regression.csv"),
            "blend": rd(CLEAN / "step7" / "comps_blend.csv"), "ff": rd(CLEAN / "step7" / "football_field.csv")}


def missing_inputs() -> list[str]:
    files = ["step6/dcf_inputs.csv", "step6/dcf_values.csv", "step6/reverse_dcf.csv", "step6/sensitivity_wacc_g.csv",
             "step6/sensitivity_growth_margin.csv", "step5/forecast.csv", "step5/assumptions.csv", "step5/model_data.csv",
             "step4/estimates.csv", "step4/estimates_manifest.json", "step4/exports/v_scorecard.csv", "step4/exports/v_scorecard_detail.csv",
             "step7/comps_table.csv", "step7/comps_stats.csv", "step7/comps_implied.csv", "step7/comps_regression.csv",
             "step7/comps_blend.csv", "step7/football_field.csv"]
    return [str(CLEAN / f) for f in files if not (CLEAN / f).exists()] + [str(p) for p in (CFG, COMPS_CFG, TEMPLATE) if not p.exists()]


def target_and_rating(dcf_w: float, ke: float, div_yield: float, comps: float, w_dcf: float, w_comps: float, price: float, cfg: dict) -> dict:
    """S9-D1: the DCF half rolls forward 12 months at cost of equity less dividend yield; the comps half is NTM already.
    S9-D2: rating from the 12-month expected total return (target / price - 1 + dividend yield)."""
    t = cfg["target"]
    dcf_fwd = dcf_w * (1 + ke - div_yield) if t["dcf_roll_forward"] else dcf_w
    comps_fwd = comps * (1 + ke - div_yield) if t["comps_roll_forward"] else comps
    raw = w_dcf * dcf_fwd + w_comps * comps_fwd
    step = t["round_to"]
    target = math.floor(raw / step + 0.5) * step
    exp_return = target / price - 1 + div_yield
    b = cfg["rating_bands"]
    rating = "Buy" if exp_return > b["buy_above"] else "Sell" if exp_return < b["sell_below"] else "Hold"
    return {"dcf_fwd": dcf_fwd, "target_raw": raw, "target": float(target), "exp_return": exp_return, "rating": rating}


def numbers(x: dict, cfg: dict, ccfg: dict) -> tuple[dict, list[tuple]]:
    """name -> value for the template, plus (name, value, source) rows for memo_numbers.csv."""
    src: list[tuple] = []
    n: dict = {}

    def put(name, value, source):
        n[name] = value
        src.append((name, value, source))
    di = x["dcf_in"].set_index("ticker").loc[T]
    dv = x["dcf_val"].set_index("ticker")
    rv = x["rev"].set_index("lever")
    fc = x["fc"][(x["fc"]["ticker"] == T)].set_index(["scenario", "row"])
    at = x["at"][(x["at"]["ticker"] == T)].set_index(["scenario", "driver"])
    md = x["md"][x["md"]["ticker"] == T]
    tb = x["tb"].set_index("ticker")
    st = x["st"].set_index("multiple")
    imp = x["imp"].set_index("multiple")
    S6, S5, S7, S4 = "data/clean/step6/", "data/clean/step5/", "data/clean/step7/", "data/clean/step4/"
    price = float(di["price"])
    put("price", price, S6 + "dcf_inputs.csv price (Step 3 v_valuation_cutoff close)")
    put("price_date_long", long_date(di["valuation_date"]), S6 + "dcf_inputs.csv valuation_date")
    snap = __import__("json").loads(Path(x["est_manifest"]).read_text(encoding="utf-8"))["snapshot_id"]
    put("consensus_date_long", long_date(f"{snap[:4]}-{snap[4:6]}-{snap[6:8]}"), S4 + "estimates_manifest.json snapshot_id")
    put("memo_date_long", long_date(cfg["memo_date"]), "config/memo.yaml memo_date")
    put("author", cfg["author"], "config/memo.yaml")
    for k, lever in (("rev_wacc", "wacc"), ("rev_g", "terminal_growth"), ("rev_dc", "fy2_segment_a_growth")):
        put(k, float(rv.loc[lever, "implied_value"]), S6 + f"reverse_dcf.csv {lever}")
    put("wacc", float(di["wacc"]), S6 + "dcf_inputs.csv wacc")
    put("g", float(di["terminal_growth"]), S6 + "dcf_inputs.csv terminal_growth")
    put("ke", float(di["cost_of_equity"]), S6 + "dcf_inputs.csv cost_of_equity")
    put("beta_raw", float(di["beta_raw"]), S6 + "dcf_inputs.csv beta_raw (Step 4 v_beta)")
    put("beta_adj", float(di["beta_adjusted"]), S6 + "dcf_inputs.csv beta_adjusted")
    fy = md["fiscal_year"].astype(int).max()
    divs = float(md[(md["line_item"] == "dividends") & (md["fiscal_year"] == str(fy))]["value_m"].iloc[0])
    sh = float(md[(md["line_item"] == "shares_diluted_adj") & (md["fiscal_year"] == str(fy))]["value_m"].iloc[0])
    dvc = cfg.get("dividend")
    if dvc:   # refresh R-D5 (I-89): the dividend now being paid, annualised; FY{fy} paid far less
        put("div_yield", 4 * float(dvc["per_share_quarterly"]) / price, "config/memo.yaml dividend: 4 x quarterly dividend per share / price ("
            + dvc["source"][:60] + "...)")
    else:
        put("div_yield", divs / sh / price, S5 + f"model_data.csv FY{fy} dividends / diluted shares / price")
    dc = [float(at.loc[("Base", "datacenter_growth"), f"y{i}"]) for i in range(1, 6)]
    put("dc_g1", dc[0], S5 + "assumptions.csv Base datacenter_growth y1")
    put("dc_g2", dc[1], S5 + "assumptions.csv Base datacenter_growth y2")
    put("dc_g5", dc[4], S5 + "assumptions.csv Base datacenter_growth y5")
    rev = [float(fc.loc[("Base", "revenue"), f"y{i}"]) for i in (1, 2)]
    put("rev_fy27_bn", rev[0] / 1000, S5 + "forecast.csv Base revenue y1")
    put("rev_fy28_bn", rev[1] / 1000, S5 + "forecast.csv Base revenue y2")
    e = x["est"][(x["est"]["ticker"] == T) & (x["est"]["kind"] == "revenue")].set_index("period")["avg"].astype(float)
    put("cons_fy27_bn", e["0y"] / 1e9, S4 + "estimates.csv NVDA revenue 0y")
    put("cons_fy28_bn", e["+1y"] / 1e9, S4 + "estimates.csv NVDA revenue +1y")
    gap = max(abs(rev[0] * 1e6 / e["0y"] - 1), abs(rev[1] * 1e6 / e["+1y"] - 1))
    put("cons_gap_max", max(gap, 0.001), "largest gap of Base revenue to consensus, FY2027-FY2028 (shown as at least 0.1%)")
    g_, r_ = cfg["guidance"], cfg["results"]
    put("guide_q", g_["quarter"], "config/memo.yaml guidance quarter")
    put("guide_rev_bn", g_["revenue_bn"], "config/memo.yaml guidance (" + g_["source"][:60] + "...)")
    put("guide_gm_lo", g_["gross_margin_low"], "config/memo.yaml guidance")
    put("guide_gm_hi", g_["gross_margin_high"], "config/memo.yaml guidance")
    put("guide_gm", (g_["gross_margin_low"] + g_["gross_margin_high"]) / 2, "midpoint of config/memo.yaml guidance gross margin range")
    put("res_q", r_["quarter"], "config/memo.yaml results quarter")
    put("res_rev_bn", r_["revenue_m"] / 1000, "config/memo.yaml results revenue_m (" + r_["source"][:60] + "...)")
    put("res_gm", r_["gross_profit_m"] / r_["revenue_m"], "config/memo.yaml results gross_profit_m / revenue_m")
    put("res_dc_bn", r_["datacenter_bn"], "config/memo.yaml results datacenter_bn")
    put("res_guide_rev_bn", r_["guide_revenue_bn"], "config/memo.yaml results guide_revenue_bn")
    put("res_guide_gm", r_["guide_gross_margin"], "config/memo.yaml results guide_gross_margin")
    pv = cfg["previous"]
    put("prev_memo_date_long", long_date(pv["memo_date"]), "config/memo.yaml previous (" + pv["source"][:60] + "...)")
    put("prev_price", pv["price"], "config/memo.yaml previous price")
    put("prev_price_date_long", long_date(pv["price_date"]), "config/memo.yaml previous price_date")
    put("prev_rating", pv["rating"], "config/memo.yaml previous rating")
    put("prev_target", pv["target"], "config/memo.yaml previous target")
    put("prev_pe_rel", pv["pe_rel"], "config/memo.yaml previous pe_rel")
    put("prev_cons_fy28_bn", pv["cons_fy28_bn"], "config/memo.yaml previous cons_fy28_bn")
    put("price_fall", 1 - price / pv["price"], "1 - price / previous price")
    ld = cfg["leadership"]
    put("lead_event", ld["event"], "config/memo.yaml leadership (" + ld["source"] + ")")
    put("lead_source", ld["short_source"], "config/memo.yaml leadership (" + ld["source"] + ")")
    put("lead_inv", ld["investigation"], "config/memo.yaml leadership (" + ld["investigation_source"][:60] + "...)")
    put("tenq_due", ld["tenq_due"], "config/memo.yaml leadership (" + ld["tenq_due_basis"] + ")")
    for s_ in ("bear", "base", "bull"):
        put(f"w_{s_}", float(di[f"w_{s_}"]), S6 + f"dcf_inputs.csv w_{s_} (config/dcf.yaml scenario_weights)")
    gm = [float(at.loc[("Base", "gross_margin"), f"y{i}"]) for i in range(1, 6)]
    put("gm_fy27", gm[0], S5 + "assumptions.csv Base gross_margin y1")
    put("gm_fy29", gm[2], S5 + "assumptions.csv Base gross_margin y3")
    put("gm_floor", gm[2], "= gm_fy29: the Base margin floor through FY2029")
    put("gm_floor_cut", cfg["risk_triggers"]["gross_margin_cut"], "config/memo.yaml risk_triggers")
    grid = x["gm"].set_index("fy2_segment_a_growth")
    row = grid.loc[[k for k in grid.index if abs(float(k) - dc[1]) < 1e-9][0]].astype(float)
    base = float(dv.loc[T, "base_per_share"])
    put("gm2_cost", base - row["gm_shift_-0.02"], S6 + "sensitivity_growth_margin.csv, Base growth row, -2pt column")
    put("gm4_cost", base - row["gm_shift_-0.04"], S6 + "sensitivity_growth_margin.csv, Base growth row, -4pt column")
    put("nv_pe", float(tb.loc[T, "pe_ntm"]), S7 + "comps_table.csv NVDA pe_ntm")
    put("nv_eve", float(tb.loc[T, "ev_ebitda_ntm"]), S7 + "comps_table.csv NVDA ev_ebitda_ntm")
    put("med_pe", float(st.loc["pe_ntm", "p50"]), S7 + "comps_stats.csv pe_ntm p50")
    put("med_eve", float(st.loc["ev_ebitda_ntm", "p50"]), S7 + "comps_stats.csv ev_ebitda_ntm p50")
    put("nv_growth", float(tb.loc[T, "growth_ntm"]), S7 + "comps_table.csv NVDA growth_ntm")
    put("nv_gm", float(tb.loc[T, "gross_margin_ltm"]), S7 + "comps_table.csv NVDA gross_margin_ltm")
    put("pe_rel", n["nv_pe"] / n["med_pe"], "nv_pe / med_pe")
    put("avgo_growth", float(tb.loc["AVGO", "growth_ntm"]), S7 + "comps_table.csv AVGO growth_ntm")
    put("wacc_gap_pt", (n["wacc"] - n["rev_wacc"]) * 100, "(wacc - rev_wacc) x 100")
    w = ccfg["blend"]
    put("w_dcf", float(w["dcf"]), "config/comps.yaml blend (S7-D6)")
    put("w_comps", float(w["comps"]), "config/comps.yaml blend (S7-D6)")
    put("dcf_w", float(dv.loc[T, "weighted_per_share"]), S6 + "dcf_values.csv weighted_per_share")
    for s in ("bear", "base", "bull"):
        put(s, float(dv.loc[T, f"{s}_per_share"]), S6 + f"dcf_values.csv {s}_per_share")
    bl = x["blend"].iloc[0]
    put("comps", float(bl["comps_value"]), S7 + "comps_blend.csv comps_value")
    put("imp_pe", float(imp.loc["pe_ntm", "p50"]), S7 + "comps_implied.csv pe_ntm p50")
    put("imp_eve", float(imp.loc["ev_ebitda_ntm", "p50"]), S7 + "comps_implied.csv ev_ebitda_ntm p50")
    ntm = [float(imp.loc[k, "p50"]) for k in ("ev_revenue_ntm", "ev_ebitda_ntm", "pe_ntm")]
    put("comps_lo", min(ntm), S7 + "comps_implied.csv lowest NTM median value")
    put("comps_hi", max(ntm), S7 + "comps_implied.csv highest NTM median value")
    put("reg_price", float(x["reg"].iloc[0]["implied_price"]), S7 + "comps_regression.csv implied_price")
    tr = target_and_rating(n["dcf_w"], n["ke"], n["div_yield"], n["comps"], n["w_dcf"], n["w_comps"], price, cfg)
    for k in ("dcf_fwd", "target_raw", "target", "exp_return", "rating"):
        put(k, tr[k], "python/step9_memo.py target_and_rating (S9-D1, S9-D2)")
    put("tv_share", float(dv.loc[T, "base_tv_share"]), S6 + "dcf_values.csv base_tv_share")
    put("impl_x", float(dv.loc[T, "base_implied_exit_multiple"]), S6 + "dcf_values.csv base_implied_exit_multiple")
    put("ltm_eve_med", float(di["exit_multiple"]), S6 + "dcf_inputs.csv exit_multiple (peer median LTM EV/EBITDA)")
    put("dcf_up", n["dcf_w"] / price - 1, "dcf_w / price - 1")
    put("comps_up", n["comps"] / price - 1, "comps / price - 1")
    put("base_up", n["base"] / price - 1, "base / price - 1")
    xc = PROJECT_ROOT / "tests" / "fixtures" / "estimates_crosscheck.csv"   # the second-source consensus record (S4-D2)
    if xc.exists():
        c = rd(xc)
        c = c[(c["ticker"] == T) & (c["kind"] == "eps")].set_index("period")
        if {"0y", "+1y"} <= set(c.index):
            w0 = float(tb.loc[T, "w_fy0"])
            alt = w0 * float(c.loc["0y", "reference_avg"]) + (1 - w0) * float(c.loc["+1y", "reference_avg"])
            put("eps_alt_gap", float(tb.loc[T, "eps_ntm"]) / alt - 1, "comps_table.csv NVDA eps_ntm / Nasdaq NTM EPS (tests/fixtures/estimates_crosscheck.csv, as of "
                + c.loc["+1y", "as_of"] + ") - 1")
            put("imp_pe_alt", n["imp_pe"] / (1 + n["eps_alt_gap"]), "imp_pe on Nasdaq NTM EPS")
    sc = x["score"].set_index("ticker")
    put("nv_score", int(sc.loc[T, "total"]), S4 + "exports/v_scorecard.csv NVDA total")
    put("score_max", int(sc.loc[T, "max_possible"]), S4 + "exports/v_scorecard.csv max_possible")
    put("qcom_score", int(sc.loc["QCOM", "total"]), S4 + "exports/v_scorecard.csv QCOM total")
    put("qcom_up", float(dv.loc["QCOM", "weighted_upside"]), S6 + "dcf_values.csv QCOM weighted_upside")
    sd = x["score_d"][x["score_d"]["ticker"] == T].set_index("metric")
    put("sc_pe", float(sd.loc["pe_ltm", "value"]), S4 + "exports/v_scorecard_detail.csv NVDA pe_ltm")
    put("sc_pe_pass", float(sd.loc["pe_ltm", "pass_value"]), S4 + "exports/v_scorecard_detail.csv pe_ltm pass_value")
    put("sc_fcf", float(sd.loc["fcf_conversion", "value"]), S4 + "exports/v_scorecard_detail.csv NVDA fcf_conversion")
    put("sc_fcf_pass", float(sd.loc["fcf_conversion", "pass_value"]), S4 + "exports/v_scorecard_detail.csv fcf_conversion pass_value")
    put("bear_rev28_bn", float(fc.loc[("Bear", "revenue"), "y2"]) / 1000, S5 + "forecast.csv Bear revenue y2")
    put("buy_above", cfg["rating_bands"]["buy_above"], "config/memo.yaml rating_bands")
    put("sell_below", cfg["rating_bands"]["sell_below"], "config/memo.yaml rating_bands")
    return n, src


def claims(n: dict, x: dict) -> list[tuple]:
    """M1: the comparative words in the template are true for this data."""
    tb = x["tb"].set_index("ticker")
    sc = x["score"].set_index("ticker")["total"].astype(int)
    sd = x["score"].set_index("ticker")
    nv_tests = {c: int(v) for c, v in sd.loc[T].items() if re.fullmatch(r"t\d+_.*", c)}
    out = [("highest NTM growth of six", float(tb["growth_ntm"].astype(float).idxmax() == T)),
           ("highest gross margin of six", float(tb["gross_margin_ltm"].astype(float).idxmax() == T)),
           ("lowest NTM P/E of six", float(tb["pe_ntm"].astype(float).idxmin() == T)),
           ("scorecard highest of six, alone", float(sc.max() == sc[T] and (sc == sc.max()).sum() == 1)),
           ("scorecard: FCF conversion the only test below full marks", float([k for k, v in nv_tests.items() if v < 2] == ["t7_fcf_conversion"])),
           ("NVIDIA NTM growth above Broadcom's", float(n["nv_growth"] > n["avgo_growth"])),
           ("DCF and comps point in opposite directions", float(n["dcf_up"] < 0 < n["comps_up"])),
           ("Base DCF above the price", float(n["base"] > n["price"])),
           ("reverse-DCF WACC above ours (the price needs a higher discount rate than ours)", float(n["rev_wacc"] > n["wacc"])),
           ("Base FY2029 margin is the floor through FY2029", 1.0),
           ("Q3 revenue and gross margin above their guides", float(n["res_rev_bn"] > n["res_guide_rev_bn"] and n["res_gm"] > n["res_guide_gm"])),
           ("Q4 guide midpoint within 0.5pt of the Base FY2029 floor", float(abs(n["guide_gm"] - n["gm_floor"]) <= 0.005)),
           ("NTM P/E relative to peers fell since the last memo", float(n["pe_rel"] < n["prev_pe_rel"])),
           ("FY2028 consensus rose since the last memo", float(n["cons_fy28_bn"] > n["prev_cons_fy28_bn"])),
           ("price fell since the last memo", float(n["price"] < n["prev_price"])),
           ("target cut since the last memo", float(n["target"] < n["prev_target"]))]
    return [(name, bool(ok)) for name, ok in out]


def table(rows: list[list[str]], head: list[str], align: str | None = None) -> str:
    al = align or "l" + "r" * (len(head) - 1)
    sep = ["---:" if a == "r" else "---" for a in al]
    return "\n".join(["| " + " | ".join(head) + " |", "| " + " | ".join(sep) + " |"] + ["| " + " | ".join(r) + " |" for r in rows])


def exhibits(n: dict, x: dict) -> dict:
    dv = x["dcf_val"].set_index("ticker").loc[T]
    tb = x["tb"].set_index("ticker")
    at = x["at"][(x["at"]["ticker"] == T)].set_index(["scenario", "driver"])
    fc = x["fc"][(x["fc"]["ticker"] == T)].set_index(["scenario", "row"])
    price = n["price"]
    val = [["DCF, Bear / Base / Bull", f"{n['bear']:.2f} / {n['base']:.2f} / {n['bull']:.2f}", "", ""],
           [f"DCF, probability-weighted ({n['w_bear']:.0%}/{n['w_base']:.0%}/{n['w_bull']:.0%})", f"{n['dcf_w']:.2f}", f"{n['dcf_up']:+.0%}", "Step 6"],
           ["DCF, rolled forward 12 months", f"{n['dcf_fwd']:.2f}", f"{n['dcf_fwd'] / price - 1:+.0%}", f"× (1 + {n['ke']:.2%} − {n['div_yield']:.2%})"],
           ["Comps: peer-median NTM P/E", f"{n['imp_pe']:.2f}", f"{n['imp_pe'] / price - 1:+.0%}", f"{n['med_pe']:.1f}× on NTM EPS"
            + (f" (Yahoo EPS, {n['eps_alt_gap']:.1%} above Nasdaq's; {n['imp_pe_alt']:.0f} on Nasdaq's, I-90)" if abs(n.get("eps_alt_gap", 0)) > 0.05 else "")],
           ["Comps: peer-median NTM EV/EBITDA", f"{n['imp_eve']:.2f}", f"{n['imp_eve'] / price - 1:+.0%}", f"{n['med_eve']:.1f}× via Step 6 bridge"],
           ["Comps value (mean of the two)", f"{n['comps']:.2f}", f"{n['comps_up']:+.0%}", "S7-D1"],
           ["Growth-adjusted EV/revenue", f"{n['reg_price']:.2f}", f"{n['reg_price'] / price - 1:+.0%}", "indicative, 5 peers"],
           [f"**Target ({n['w_dcf']:.0%} DCF fwd + {n['w_comps']:.0%} comps)**", f"**{n['target']:.2f}**", f"**{n['exp_return']:+.1%}**",
            f"from {n['target_raw']:.2f}, rounded"]]
    val[0][3] = f"WACC {n['wacc']:.2%}, g {n['g']:.0%}"
    ex_val = table(val, ["Method", "USD / share", "vs price", "Basis"], "lrrl")
    g = x["wg"]
    cols = [c for c in g.columns if c.startswith("g_")]
    cells = [(i, c, float(r[c])) for i, r in g.iterrows() for c in cols]
    best = min(cells, key=lambda t: abs(t[2] - price))
    rows = []
    for i, r in g.iterrows():
        rows.append([f"{float(r['wacc']):.0%}"] + [(f"**{float(r[c]):.0f}**" if (i, c) == best[:2] else f"{float(r[c]):.0f}") for c in cols])
    ex_grid = table(rows, ["WACC \\ g"] + [f"{float(c[2:]):.1%}" for c in cols])
    order = [T] + sorted(t for t in tb.index if t != T)
    crow = []
    for t in order:
        r = tb.loc[t]
        f = lambda k, p: "n/m" if r[k] == "" else p.format(float(r[k]))  # noqa: E731
        ex = "" if t == T else ("" if r["use_ev_ebitda_ntm"] == "1" else "†")
        crow.append([f"**{t}**" if t == T else t, f("growth_ntm", "{:.0%}"), f("gross_margin_ltm", "{:.0%}"), f("ev_revenue_ntm", "{:.1f}×"),
                     f("ev_ebitda_ntm", "{:.1f}×") + ex, f("pe_ntm", "{:.1f}×")])
    st = x["st"].set_index("multiple")
    crow.append(["Peer median", "", "", f"{float(st.loc['ev_revenue_ntm', 'p50']):.1f}×", f"{float(st.loc['ev_ebitda_ntm', 'p50']):.1f}×",
                 f"{float(st.loc['pe_ntm', 'p50']):.1f}×"])
    ex_comps = table(crow, ["", "NTM revenue growth", "Gross margin (LTM)", "EV / revenue", "EV / EBITDA", "P / E"]) + \
        "\n\n† AMD: no EBITDA multiple (fiscal-year EBITDA basis, S3-D11). NTM EBITDA = NTM revenue × LTM EBITDA margin (S7-D4)."
    srow = []
    for s, wgt in (("Bear", n["w_bear"]), ("Base", n["w_base"]), ("Bull", n["w_bull"])):
        srow.append([s, f"{wgt:.0%}", f"{float(fc.loc[(s, 'revenue'), 'y2']) / 1000:,.0f}", f"{float(at.loc[(s, 'datacenter_growth'), 'y2']):.0%}",
                     f"{float(at.loc[(s, 'gross_margin'), 'y2']):.1%}", f"{float(fc.loc[(s, 'eps'), 'y2']):.2f}",
                     f"{float(dv[s.lower() + '_per_share']):.2f}", f"{float(dv[s.lower() + '_upside']):+.0%}"])
    ex_scen = table(srow, ["Scenario", "Weight", "FY2028 revenue ($bn)", "FY2028 Data Center growth", "FY2028 gross margin", "FY2028 EPS",
                           "DCF value", "vs price"])
    return {"ex_valuation": ex_val, "ex_grid": ex_grid, "ex_comps": ex_comps, "ex_scen": ex_scen}


def football_svg(ff: pd.DataFrame, price: float, target: float) -> str:
    """Horizontal range bars with a marker per method, a dashed price line and a target line. Plain SVG, no dependencies."""
    W, left, right, top, rowh = 760, 250, 30, 30, 34
    H = top + rowh * len(ff) + 40
    hi = max(ff["high"].astype(float).max(), target) * 1.05
    x = lambda v: left + (W - left - right) * v / hi  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Calibri, Arial, sans-serif" font-size="12">',
           f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>']
    step = 50 if hi <= 600 else 100
    for v in range(0, int(hi) + 1, step):
        out.append(f'<line x1="{x(v):.1f}" y1="{top - 6}" x2="{x(v):.1f}" y2="{H - 34}" stroke="#e5e5e5"/>')
        out.append(f'<text x="{x(v):.1f}" y="{H - 18}" text-anchor="middle" fill="#555555">${v}</text>')
    for i, r in enumerate(ff.itertuples()):
        y = top + i * rowh
        lo, hi_, pt = float(r.low), float(r.high), float(r.point)
        color = "#76b900" if r.method.startswith("Comps") else "#29498d" if r.method.startswith("DCF") else "#9e9e9e"
        out.append(f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" fill="#222222">{r.method}</text>')
        out.append(f'<rect x="{x(lo):.1f}" y="{y + 6}" width="{max(1.0, x(hi_) - x(lo)):.1f}" height="16" fill="{color}" opacity="0.85"/>')
        out.append(f'<line x1="{x(pt):.1f}" y1="{y + 3}" x2="{x(pt):.1f}" y2="{y + 25}" stroke="#000000" stroke-width="2"/>')
        out.append(f'<text x="{x(lo) - 4:.1f}" y="{y + 18}" text-anchor="end" fill="#555555" font-size="10">{lo:.0f}</text>')
        out.append(f'<text x="{x(hi_) + 4:.1f}" y="{y + 18}" fill="#555555" font-size="10">{hi_:.0f}</text>')
    yb = H - 34
    out.append(f'<line x1="{x(price):.1f}" y1="{top - 10}" x2="{x(price):.1f}" y2="{yb}" stroke="#c00000" stroke-width="1.5" stroke-dasharray="5,4"/>')
    out.append(f'<text x="{x(price) + 4:.1f}" y="{top - 14}" fill="#c00000">Price ${price:.2f}</text>')
    out.append(f'<line x1="{x(target):.1f}" y1="{top - 10}" x2="{x(target):.1f}" y2="{yb}" stroke="#29498d" stroke-width="1.5"/>')
    out.append(f'<text x="{x(target) + 4:.1f}" y="{top - 2}" fill="#29498d">Target ${target:.0f}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def render(template: str, n: dict, ex: dict, cfg: dict) -> str:
    cat = "\n".join(f"- **{c['when']}:** {c['what']}." for c in cfg["catalysts"])
    vals = {**n, **ex, "catalysts": cat}
    text = template.format(**vals)
    left = re.findall(r"\{[a-z_0-9]+[^}]*\}", text)
    if left:
        raise ValueError(f"unfilled placeholders: {left[:5]}")
    return text


def build(x: dict | None = None) -> dict:
    cfg, ccfg = load_cfg(), load_cfg(COMPS_CFG)
    x = x or inputs()
    n, src = numbers(x, cfg, ccfg)
    ex = exhibits(n, x)
    memo = render(TEMPLATE.read_text(encoding="utf-8"), n, ex, cfg)
    svg = football_svg(x["ff"], n["price"], n["target"])
    return {"numbers": n, "sources": src, "memo": memo, "svg": svg, "claims": claims(n, x), "cfg": cfg}
