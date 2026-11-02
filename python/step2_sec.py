"""Step 2 SEC processing for every company in config/universe.yaml (M2a).

Builds on the M1 rules without changing them: M1's select_line_items() selects every value, so NVIDIA's
reported values are identical to M1. Added on top, each labelled and checked:
  * predecessor registrants merged per company (M2-D1); the latest-filed rule (D4) picks between them
  * guarded fallback concepts per company (M2-D11): used only for periods where the guard concepts are absent or 0
  * derived_quarter: Q2 = 6M - Q1 and Q3 = 9M - 6M for additive flow items (M2-D3)
  * derived_component: gross profit / total liabilities from support items where a company reports none (M2-D12)
"""
from __future__ import annotations

import copy
import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from common import load_config, sha256_bytes
from parse_companyfacts import load_snapshot, parse_observations
from select_facts import SELECTED_COLUMNS, _display, fiscal_labels, select_line_items
from validate_m1 import _blank, _num, find_scale_anomalies, run_checks, scale_checks

M1_BASES = {"reported_quarter", "reported_ytd", "reported_annual", "reported_instant", "derived_q4"}
NEW_BASES = {"derived_quarter", "derived_component"}
ALL_BASES = M1_BASES | NEW_BASES
OUT_COLUMNS = ["ticker", "entity_cik", "entity_role", "support_item"] + SELECTED_COLUMNS
KEY = ["ticker", "line_item", "period_start", "period_end", "value_basis"]
GAP_COLUMNS = ["ticker", "line_item", "fiscal_year", "fiscal_period", "expected_basis", "reason"]


# ---------------------------------------------------------------- configuration

def _candidate_name(c) -> str:
    return c if isinstance(c, str) else c["concept"]


def company_config(base: dict, uni: dict, ticker: str) -> tuple[dict, dict, list[str]]:
    """(cfg for M1 functions, guards {(item, concept): [guard concepts]}, derived item list)."""
    spec = uni["companies"][ticker]
    cfg = copy.deepcopy(base)
    cfg["company"] = {"ticker": ticker, "cik": spec["cik"], "fiscal_year_end_month": spec["fy_end_month"]}
    guards: dict[tuple[str, str], list[str]] = {}
    derived = list(spec.get("derived", []))
    items = cfg["line_items"]
    for item, extra in (spec.get("extra_candidates") or {}).items():
        for c in extra:
            items[item]["candidates"].append(_candidate_name(c))
            if isinstance(c, dict) and c.get("guard_zero_or_absent"):
                guards[(item, c["concept"])] = list(c["guard_zero_or_absent"])
    needed = {uni["derivations"][d][k] for d in derived for k in ("minuend", "subtrahend")} - set(items)
    for s in sorted(needed):
        sspec = copy.deepcopy(uni["support_items"][s])
        cands = sspec["candidates"]
        sspec["candidates"] = [_candidate_name(c) for c in cands]
        sspec["support"] = True
        for c in cands:
            if isinstance(c, dict) and c.get("guard_zero_or_absent"):
                guards[(s, c["concept"])] = list(c["guard_zero_or_absent"])
        items[s] = sspec
    return cfg, guards, derived


def entities(uni: dict, ticker: str) -> list[tuple[str, str]]:
    spec = uni["companies"][ticker]
    return [(spec["cik"], "current")] + [(p["cik"], "predecessor") for p in spec.get("predecessors", [])]


# ---------------------------------------------------------------- loading

def load_company(coll: Path, uni: dict, ticker: str) -> tuple[pd.DataFrame, list[dict]]:
    frames, files = [], []
    for cik, role in entities(uni, ticker):
        path = coll / "sec" / f"companyfacts_CIK{cik}.json"
        if not path.exists():
            files.append({"cik": cik, "role": role, "file": path.name, "present": False, "sha256": "", "observations": 0})
            continue
        data, sha = load_snapshot(path)
        obs = parse_observations(data, sha)
        obs.insert(0, "entity_role", role)
        obs.insert(0, "entity_cik", cik)
        frames.append(obs)
        n = sum(len(o) for c in data.get("facts", {}).values() for b in c.values() for o in b.get("units", {}).values())
        files.append({"cik": cik, "role": role, "file": path.name, "present": True, "sha256": sha,
                      "observations": n, "entity_name": data.get("entityName", "")})
    return pd.concat(frames, ignore_index=True), files


# ---------------------------------------------------------------- selection

def _guard_blocked(obs: pd.DataFrame, guard_concepts: list[str]) -> set[tuple[str, str]]:
    """Periods (start, end) where any guard concept has a non-zero value in any filing."""
    g = obs[(obs["taxonomy"] == "us-gaap") & obs["concept"].isin(guard_concepts)]
    return {(r.period_start, r.period_end) for r in g.itertuples() if _num(r.value) != 0}


def select_company(obs: pd.DataFrame, cfg: dict, guards: dict, ticker: str) -> pd.DataFrame:
    """M1 selection, one line item at a time so each item sees only its own guard-filtered pool."""
    parts = []
    for item, spec in cfg["line_items"].items():
        pool = obs
        for (g_item, concept), gconcepts in guards.items():
            if g_item != item:
                continue
            blocked = _guard_blocked(obs, gconcepts)
            drop = (pool["concept"] == concept) & pd.Series(
                [(s, e) in blocked for s, e in zip(pool["period_start"], pool["period_end"])], index=pool.index)
            pool = pool[~drop]
        one = copy.deepcopy(cfg)
        one["line_items"] = {item: spec}
        sel = select_line_items(pool, one)
        if not sel.empty:
            parts.append(sel)
    selected = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=SELECTED_COLUMNS, dtype=object)
    # entity of each reported row, from its accession (accessions are unique to one registrant)
    accn_entity = dict(zip(obs["accn"], zip(obs["entity_cik"], obs["entity_role"])))
    selected.insert(0, "support_item", selected["line_item"].map(lambda i: bool(cfg["line_items"][i].get("support"))))
    selected.insert(0, "entity_role", selected["accn"].map(lambda a: accn_entity.get(a, ("", ""))[1]))
    selected.insert(0, "entity_cik", selected["accn"].map(lambda a: accn_entity.get(a, ("", ""))[0]))
    selected.insert(0, "ticker", ticker)
    return selected


def _row(base: dict, **kw) -> dict:
    r = {c: "" for c in OUT_COLUMNS}
    r.update(base)
    r.update(kw)
    return r


def derive_quarters(selected: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Q2 = 6M - Q1 and Q3 = 9M - 6M (same fiscal-year start, same concept) for derive_q4 items."""
    rows = []
    fy_month = cfg["company"]["fiscal_year_end_month"]
    for item, spec in cfg["line_items"].items():
        if not spec.get("derive_q4"):
            continue
        s = selected[selected["line_item"] == item]
        q = s[s["value_basis"] == "reported_quarter"]
        ytd = s[s["value_basis"] == "reported_ytd"]
        reported_ends = set(q["period_end"])
        for _, cur in ytd.iterrows():
            if cur["period_end"] in reported_ends:
                continue  # a 3-month value is reported: keep it, derive nothing
            if cur["fiscal_period"] == "6M":
                prev = q[(q["period_start"] == cur["period_start"]) & (q["period_end"] < cur["period_end"])]
                label = "Q2"
            elif cur["fiscal_period"] == "9M":
                prev = ytd[(ytd["fiscal_period"] == "6M") & (ytd["period_start"] == cur["period_start"])]
                label = "Q3"
            else:
                continue
            if len(prev) != 1 or prev.iloc[0]["concept"] != cur["concept"]:
                continue
            p = prev.iloc[0]
            value = _num(cur["value"]) - _num(p["value"])
            disp, disp_unit, _ = _display(value, spec["unit"])
            start = (date.fromisoformat(p["period_end"]) + timedelta(days=1)).isoformat()
            fy, _ = fiscal_labels(cur["period_end"], fy_month)
            rows.append(_row({}, ticker=cur["ticker"], support_item=cur["support_item"], line_item=item,
                             statement=spec["statement"], fiscal_year=fy, fiscal_period=label,
                             value_basis="derived_quarter", period_start=start, period_end=cur["period_end"],
                             value=value, unit=spec["unit"], display_value=disp, display_unit=disp_unit,
                             concept=cur["concept"],
                             derived_from_accns=f"{cur['fiscal_period']}:{cur['accn']}|{p['fiscal_period']}:{p['accn']}",
                             transformation=f"derived: {cur['fiscal_period']} YTD minus {p['fiscal_period']}",
                             snapshot_sha256=cur["snapshot_sha256"]))
    return pd.DataFrame(rows, columns=OUT_COLUMNS, dtype=object)


def derive_components(selected: pd.DataFrame, cfg: dict, uni: dict, derived: list[str]) -> pd.DataFrame:
    """target = minuend - subtrahend for each period where the company reports no value for the target."""
    rows = []
    for target in derived:
        d = uni["derivations"][target]
        spec = cfg["line_items"][target]
        a_rows = selected[selected["line_item"] == d["minuend"]]
        b_rows = selected[selected["line_item"] == d["subtrahend"]]
        have = selected[selected["line_item"] == target]
        have_periods = set(zip(have["period_start"], have["period_end"]))
        b_index = {(r.period_start, r.period_end): r for r in b_rows.itertuples()}
        for a in a_rows.itertuples():
            key = (a.period_start, a.period_end)
            if key in have_periods or key not in b_index:
                continue
            b = b_index[key]
            if a.fiscal_period != b.fiscal_period:
                continue
            value = _num(a.value) - _num(b.value)
            disp, disp_unit, _ = _display(value, spec["unit"])
            src = lambda r: r.accn if r.accn else f"derived({r.derived_from_accns})"  # noqa: E731
            rows.append(_row({}, ticker=a.ticker, support_item=False, line_item=target, statement=spec["statement"],
                             fiscal_year=a.fiscal_year, fiscal_period=a.fiscal_period, value_basis="derived_component",
                             period_start=a.period_start, period_end=a.period_end, value=value, unit=spec["unit"],
                             display_value=disp, display_unit=disp_unit, concept="",
                             derived_from_accns=f"{d['minuend']}:{src(a)}|{d['subtrahend']}:{src(b)}",
                             transformation=f"derived: {d['minuend']} ({a.concept}) minus {d['subtrahend']} ({b.concept})",
                             snapshot_sha256=a.snapshot_sha256))
    return pd.DataFrame(rows, columns=OUT_COLUMNS, dtype=object)


# ---------------------------------------------------------------- gaps

def gap_report(selected: pd.DataFrame, cfg: dict, ticker: str) -> tuple[pd.DataFrame, int | None]:
    n = cfg["history"]["target_fiscal_years"]
    rev = selected[(selected["line_item"] == "revenue") & (selected["value_basis"] == "reported_annual")]
    if rev.empty:
        return pd.DataFrame([[ticker, "revenue", "", "FY", "reported_annual", "no annual revenue; window undefined"]],
                            columns=GAP_COLUMNS), None
    latest = int(max(rev["fiscal_year"]))
    s = selected
    idx = {(r.line_item, int(r.fiscal_year), r.fiscal_period, r.value_basis) for r in s.itertuples()}

    def has(item, fy, period, bases):
        return any((item, fy, period, b) in idx for b in bases)

    gaps = []
    for item, spec in cfg["line_items"].items():
        if spec.get("support"):
            continue
        for fy in range(latest - n + 1, latest + 1):
            if spec["period_type"] == "instant":
                for q in ("Q1", "Q2", "Q3", "Q4"):
                    if not has(item, fy, q, {"reported_instant", "derived_component"}):
                        gaps.append([ticker, item, fy, q, "reported_instant", "no_observation"])
                continue
            if not has(item, fy, "FY", {"reported_annual", "derived_component"}):
                gaps.append([ticker, item, fy, "FY", "reported_annual", "no_observation"])
            for q in ("Q1", "Q2", "Q3"):
                if has(item, fy, q, {"reported_quarter", "derived_quarter", "derived_component"}):
                    continue
                ytd = {"Q2": "6M", "Q3": "9M"}.get(q)
                if not spec.get("derive_q4"):
                    reason = "no_observation"
                elif ytd and has(item, fy, ytd, {"reported_ytd"}):
                    reason = "only_ytd_reported: derivation inputs incomplete"
                else:
                    reason = "no_observation"
                gaps.append([ticker, item, fy, q, "reported_quarter or derived_quarter", reason])
            if not has(item, fy, "Q4", {"reported_quarter", "derived_q4", "derived_component"}):
                if not spec.get("derive_q4"):
                    reason = "not_derivable_by_subtraction"
                elif not has(item, fy, "FY", {"reported_annual"}):
                    reason = "derived_q4_inputs_missing: annual"
                elif not has(item, fy, "9M", {"reported_ytd"}):
                    reason = "derived_q4_inputs_missing: 9M YTD"
                else:
                    reason = "derived_q4_not_computed: concept mismatch or ambiguous inputs"
                gaps.append([ticker, item, fy, "Q4", "reported_quarter or derived_q4", reason])
    return pd.DataFrame(gaps, columns=GAP_COLUMNS, dtype=object), latest


# ---------------------------------------------------------------- checks

def company_checks(obs, selected, files, cfg, guards, uni, derived, latest_fy):
    """Error-level checks C1-C17 and warning W1 for one company: [(check, passed, detail, level)]."""
    m1 = selected[selected["value_basis"].isin(M1_BASES)]
    m1_cols = m1[SELECTED_COLUMNS].copy()
    expected = sum(f["observations"] for f in files if f["present"])
    base = [c for c in run_checks(obs, m1_cols, cfg, expected) if c[0] != "C10_single_snapshot"]
    out = [(c, p, d, "error") for c, p, d in base]

    shas = {f["sha256"] for f in files if f["present"]}
    used = set(selected["snapshot_sha256"]) | set(obs["snapshot_sha256"])
    out.append(("C10_snapshots_are_collection_files", used <= shas,
                f"{len(used)} snapshot hashes used, {len(shas)} entity files in the collection"))

    anomalies = find_scale_anomalies(m1_cols, cfg, latest_fy)
    c11, w1 = scale_checks(anomalies)
    out.append((*c11, "error"))

    dq = selected[selected["value_basis"] == "derived_quarter"]
    bad = 0
    for r in dq.itertuples():
        s = selected[(selected["line_item"] == r.line_item) & (selected["period_end"] == r.period_end)
                     & (selected["value_basis"] == "reported_ytd")]
        tag = "6M" if r.fiscal_period == "Q2" else "9M"
        prev_basis, prev_tag = ("reported_quarter", "Q1") if tag == "6M" else ("reported_ytd", "6M")
        p_end = (date.fromisoformat(r.period_start) - timedelta(days=1)).isoformat()
        p = selected[(selected["line_item"] == r.line_item) & (selected["period_end"] == p_end)
                     & (selected["value_basis"] == prev_basis) & (selected["fiscal_period"] == prev_tag)]
        # the YTD row and the earlier row must share a fiscal-year start date (as in derive_quarters)
        pairs = [(a, b) for _, a in s.iterrows() for _, b in p.iterrows() if a["period_start"] == b["period_start"]]
        if (len(pairs) != 1 or _num(pairs[0][0]["value"]) - _num(pairs[0][1]["value"]) != _num(r.value)
                or not _blank(r.accn) or _blank(r.derived_from_accns)):
            bad += 1
    out.append(("C12_derived_quarters_recompute", bad == 0, f"{bad} of {len(dq)} derived quarters fail"))

    viol = 0
    for (item, concept), gconcepts in guards.items():
        blocked = _guard_blocked(obs, gconcepts)
        hit = selected[(selected["line_item"] == item) & (selected["concept"] == concept)
                       & selected["value_basis"].isin({"reported_quarter", "reported_ytd", "reported_annual", "reported_instant"})]
        viol += sum((r.period_start, r.period_end) in blocked for r in hit.itertuples())
    out.append(("C13_guarded_fallbacks_respected", viol == 0, f"{viol} fallback rows where a guard concept is non-zero"))

    dc = selected[selected["value_basis"] == "derived_component"]
    bad = 0
    for r in dc.itertuples():
        d = uni["derivations"][r.line_item]
        a = selected[(selected["line_item"] == d["minuend"]) & (selected["period_start"] == r.period_start)
                     & (selected["period_end"] == r.period_end)]
        b = selected[(selected["line_item"] == d["subtrahend"]) & (selected["period_start"] == r.period_start)
                     & (selected["period_end"] == r.period_end)]
        if len(a) != 1 or len(b) != 1 or _num(a.iloc[0]["value"]) - _num(b.iloc[0]["value"]) != _num(r.value) \
                or r.line_item not in derived:
            bad += 1
    out.append(("C14_derived_components_recompute", bad == 0, f"{bad} of {len(dc)} derived components fail"))

    unknown = set(selected["value_basis"]) - ALL_BASES
    out.append(("C15_value_basis_vocabulary_all", not unknown, f"unknown: {sorted(unknown)}"))
    dupes = int(selected.duplicated(KEY, keep=False).sum())
    out.append(("C16_unique_keys_all_rows", dupes == 0, f"{dupes} duplicate key rows"))
    reported = selected[~selected["value_basis"].isin({"derived_q4"} | NEW_BASES)]
    ciks = {c for c, _ in entities(uni, cfg["company"]["ticker"])}
    off = int((~reported["entity_cik"].isin(ciks)).sum())
    out.append(("C17_rows_from_configured_registrants", off == 0, f"{off} reported rows from other registrants"))
    # C18: D5 LTM readiness - every flow item has a value for each of the four latest fiscal quarters
    flows = [i for i, sp in cfg["line_items"].items() if sp["period_type"] == "duration" and sp.get("derive_q4") and not sp.get("support")]
    qbases = {"reported_quarter", "derived_quarter", "derived_q4", "derived_component"}
    qrows = selected[selected["value_basis"].isin(qbases) & selected["fiscal_period"].str.startswith("Q")]
    ends = sorted(set(qrows.loc[qrows["line_item"] == "revenue", "period_end"]))[-4:]
    missing = [f"{i}@{e}" for i in flows for e in ends if qrows[(qrows["line_item"] == i) & (qrows["period_end"] == e)].empty]
    out.append(("C18_ltm_quarters_complete", len(ends) == 4 and not missing,
                f"latest 4 quarters end {ends[0] if ends else '-'} to {ends[-1] if ends else '-'}; missing {missing or 'none'}"))
    out = [c if len(c) == 4 else (*c, "error") for c in out]
    out.append((*w1, "warning"))
    return out, anomalies


# ---------------------------------------------------------------- identity

def identity_report(coll: Path, uni: dict) -> tuple[pd.DataFrame, list]:
    tick = json.loads((coll / "sec" / "company_tickers.json").read_bytes())
    by_ticker = {v["ticker"]: str(v["cik_str"]).zfill(10) for v in tick.values()}
    rows, problems = [], []
    for ticker, spec in uni["companies"].items():
        chain = []
        for cik, role in entities(uni, ticker):
            sub_path = coll / "sec" / f"submissions_CIK{cik}.json"
            if not sub_path.exists():
                problems.append(f"{ticker} {cik}: submissions file missing")
                continue
            s = json.loads(sub_path.read_bytes())
            r = s["filings"]["recent"]
            tenk = sorted(rd for f, rd in zip(r["form"], r["reportDate"]) if f in ("10-K", "10-K/A") and rd)
            fye = s.get("fiscalYearEnd") or ""
            m, d = (int(fye[:2]), int(fye[2:])) if len(fye) == 4 else (0, 0)
            fye_month = (m - 1 or 12) if d and d <= 7 else m
            expected_name = next((p.get("expected_name_contains", "") for p in spec.get("predecessors", [])
                                  if p["cik"] == cik), "")
            row = {"ticker": ticker, "cik": cik, "role": role, "sec_name": s.get("name", ""),
                   "former_names": "|".join(x["name"] for x in s.get("formerNames", [])),
                   "sec_fiscal_year_end": fye, "fy_end_month_from_sec": fye_month,
                   "fy_end_month_config": spec["fy_end_month"],
                   "first_10k_period": tenk[0] if tenk else "", "last_10k_period": tenk[-1] if tenk else "",
                   "ticker_file_cik": by_ticker.get(ticker, "") if role == "current" else ""}
            if role == "current" and row["ticker_file_cik"] != cik:
                problems.append(f"{ticker}: ticker file CIK {row['ticker_file_cik']} != configured {cik}")
            if fye_month != spec["fy_end_month"]:
                problems.append(f"{ticker} {cik}: SEC year-end {fye} -> month {fye_month} != configured {spec['fy_end_month']}")
            if expected_name and expected_name.upper() not in (row["sec_name"] + row["former_names"]).upper():
                problems.append(f"{ticker} {cik}: name '{row['sec_name']}' lacks '{expected_name}'")
            rows.append(row)
            chain.append(row)
        # predecessors must end before their successor starts (listed newest first)
        for newer, older in zip(chain, chain[1:]):
            if older["last_10k_period"] and newer["first_10k_period"] and older["last_10k_period"] >= newer["first_10k_period"]:
                problems.append(f"{ticker}: {older['cik']} last 10-K {older['last_10k_period']} overlaps {newer['cik']}")
    return pd.DataFrame(rows, dtype=object), problems
