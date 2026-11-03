"""Step 3a: extended facts for every company, from the same Step 2 collection (no network).

Selection of every value - old and new line items - is done by the signed-off M1/M2 functions. Added here,
each labelled with its own value_basis and checked:
  derived_sum        target = sum of terms (total debt; D&A where no single tag covers it)        (S3-D1)
  declared_zero      a line item a company does not present on its balance sheet, by decision     (S3-D10)
  manual_from_filing a value read from a filing where the company used a non-standard tag          (S3-D9)
  split adjustment   eps_diluted / shares_diluted restated to the share basis at the cutoff         (S3-D2)
"""
from __future__ import annotations

import copy
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yaml

import step2_sec as s2
from common import PROJECT_ROOT
from select_facts import _display, fiscal_labels
from validate_m1 import _blank, _num

STEP3_CFG = PROJECT_ROOT / "config" / "step3.yaml"
STEP3_BASES = {"derived_sum", "declared_zero", "manual_from_filing"}
ALL_BASES = s2.ALL_BASES | STEP3_BASES
EXTRA_COLUMNS = ["split_factor", "value_split_adjusted", "display_split_adjusted", "source_url", "location_in_filing"]
OUT_COLUMNS = s2.OUT_COLUMNS + EXTRA_COLUMNS
MANUAL_COLUMNS = ["ticker", "line_item", "fiscal_year", "fiscal_period", "period_start", "period_end", "value", "unit",
                  "source_form", "accession", "filed", "source_url", "location_in_filing", "entered_by", "entered_on", "notes"]


def load_step3(path: Path = STEP3_CFG) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------- configuration

def company_config(base: dict, uni: dict, s3: dict, ticker: str):
    """Step 2 company config plus the Step 3 line items, support items and per-company candidate lists."""
    cfg, guards, derived2 = s2.company_config(base, uni, ticker)
    spec = s3["companies"].get(ticker, {})
    for item, item_spec in s3["line_items"].items():
        cfg["line_items"][item] = copy.deepcopy(item_spec)
    for item, item_spec in s3["support_items"].items():
        cfg["line_items"][item] = {**copy.deepcopy(item_spec), "support": True}
    for item, cands in (spec.get("candidates") or {}).items():
        cfg["line_items"][item]["candidates"] = list(cands)
    # support items with no candidates for this company are not selected at all
    for item in [i for i, sp in cfg["line_items"].items() if not sp["candidates"] and sp.get("support")]:
        del cfg["line_items"][item]
    return cfg, guards, derived2, list(spec.get("derived", []))


# ---------------------------------------------------------------- derivations

def _row(**kw) -> dict:
    r = {c: "" for c in OUT_COLUMNS}
    r.update(kw)
    return r


def derive_sums(selected: pd.DataFrame, cfg: dict, s3: dict, ticker: str, names: list[str]) -> pd.DataFrame:
    """target = sum of terms for each period with every required term present and no value for the target."""
    rows = []
    optional = (s3["companies"].get(ticker, {}).get("optional_zero_terms") or {})
    for name in names:
        d = s3["derivations"][name]
        target, terms = d["target"], d["terms"]
        spec = cfg["line_items"][target]
        current = pd.concat([selected] + ([pd.DataFrame(rows, columns=OUT_COLUMNS)] if rows else []), ignore_index=True)
        have = set(zip(current.loc[current["line_item"] == target, "period_start"],
                       current.loc[current["line_item"] == target, "period_end"]))
        by_term = {t: {(r.period_start, r.period_end): r for r in selected[selected["line_item"] == t].itertuples()}
                   for t in terms}
        opt = optional.get(name, {})
        anchors = set().union(*[set(v) for v in by_term.values()]) if by_term else set()
        for key in sorted(anchors - have):
            parts, missing_ok = [], []
            for t in terms:
                r = by_term[t].get(key)
                if r is not None:
                    parts.append((t, r))
                    continue
                o = opt.get(t)
                any_row = next((v for v in (by_term[x].get(key) for x in terms) if v is not None), None)
                if o and any_row is not None and int(any_row.fiscal_year) <= int(o["through_fiscal_year"]):
                    missing_ok.append(t)
                    continue
                parts = None
                break
            if not parts or len(missing_ok) == len(terms):
                continue
            first = parts[0][1]
            if any(p.fiscal_period != first.fiscal_period for _, p in parts):
                continue
            value = sum((_num(p.value) for _, p in parts), Decimal(0))
            disp, disp_unit, _ = _display(value, spec["unit"])
            src = "|".join(f"{t}:{p.accn or 'derived(' + p.derived_from_accns + ')'}" for t, p in parts)
            note = "".join(f"; {t} absent, taken as 0 by decision (through FY{opt[t]['through_fiscal_year']})" for t in missing_ok)
            rows.append(_row(ticker=ticker, support_item=False, line_item=target, statement=spec["statement"],
                             fiscal_year=first.fiscal_year, fiscal_period=first.fiscal_period, value_basis="derived_sum",
                             period_start=first.period_start, period_end=first.period_end, value=value, unit=spec["unit"],
                             display_value=disp, display_unit=disp_unit, derived_from_accns=src,
                             transformation=f"derived ({name}): sum of {' + '.join(terms)}{note}",
                             snapshot_sha256=first.snapshot_sha256))
    return pd.DataFrame(rows, columns=OUT_COLUMNS, dtype=object)


def declared_zeros(selected: pd.DataFrame, cfg: dict, s3: dict, ticker: str) -> pd.DataFrame:
    """value 0 for an item the company does not present, at each balance-sheet date with no reported value."""
    rows = []
    for item, d in ((s3["companies"].get(ticker, {}).get("declared_zero")) or {}).items():
        spec = cfg["line_items"][item]
        have = set(selected.loc[selected["line_item"] == item, "period_end"])
        assets = selected[(selected["line_item"] == "total_assets") & (selected["value_basis"] == "reported_instant")]
        for r in assets.itertuples():
            if int(r.fiscal_year) < int(d["from_fiscal_year"]) or r.period_end in have:
                continue
            disp, disp_unit, _ = _display(0, spec["unit"])
            rows.append(_row(ticker=ticker, support_item=False, line_item=item, statement=spec["statement"],
                             fiscal_year=r.fiscal_year, fiscal_period=r.fiscal_period, value_basis="declared_zero",
                             period_start="", period_end=r.period_end, value=0, unit=spec["unit"], display_value=disp,
                             display_unit=disp_unit, transformation=f"declared zero: {d['evidence']}",
                             snapshot_sha256=r.snapshot_sha256))
    return pd.DataFrame(rows, columns=OUT_COLUMNS, dtype=object)


def manual_facts(path: Path, cfg: dict, ticker: str, fy_month: int) -> tuple[pd.DataFrame, list[str]]:
    """Rows from config/manual_facts.csv for this company; returns (rows, problems)."""
    rows, problems = [], []
    if not path.exists():
        return pd.DataFrame(columns=OUT_COLUMNS, dtype=object), problems
    with open(path, encoding="utf-8", newline="") as fh:
        for i, m in enumerate(csv.DictReader(fh), start=2):
            if m["ticker"] != ticker:
                continue
            blanks = [c for c in MANUAL_COLUMNS if c != "notes" and not (m.get(c) or "").strip()
                      and not (c == "period_start" and cfg["line_items"].get(m["line_item"], {}).get("period_type") == "instant")]
            if blanks:
                problems.append(f"manual_facts.csv row {i}: blank {blanks}")
                continue
            spec = cfg["line_items"].get(m["line_item"])
            if spec is None:
                problems.append(f"manual_facts.csv row {i}: unknown line item {m['line_item']}")
                continue
            fy, q = fiscal_labels(m["period_end"], fy_month)
            if str(fy) != m["fiscal_year"] or (spec["period_type"] == "instant" and f"Q{q}" != m["fiscal_period"]):
                problems.append(f"manual_facts.csv row {i}: fiscal label {m['fiscal_year']} {m['fiscal_period']} "
                                f"does not match period end {m['period_end']} (FY{fy} Q{q})")
                continue
            value = Decimal(m["value"].replace(",", ""))
            disp, disp_unit, _ = _display(value, spec["unit"])
            rows.append(_row(ticker=ticker, support_item=False, line_item=m["line_item"], statement=spec["statement"],
                             fiscal_year=int(m["fiscal_year"]), fiscal_period=m["fiscal_period"],
                             value_basis="manual_from_filing", period_start=m["period_start"], period_end=m["period_end"],
                             value=value, unit=spec["unit"], display_value=disp, display_unit=disp_unit,
                             accn=m["accession"], form=m["source_form"], filed=m["filed"],
                             transformation=f"manual from filing by {m['entered_by']} on {m['entered_on']}: {m['notes']}",
                             source_url=m["source_url"], location_in_filing=m["location_in_filing"]))
    return pd.DataFrame(rows, columns=OUT_COLUMNS, dtype=object), problems


# ---------------------------------------------------------------- split adjustment

def split_table(actions: pd.DataFrame, companies: list[str]) -> pd.DataFrame:
    s = actions[(actions["action"] == "split") & actions["ticker"].isin(companies)].copy()
    return s.rename(columns={"value": "ratio"})[["ticker", "date", "ratio"]].sort_values(["ticker", "date"]).reset_index(drop=True)


def apply_split_adjustment(facts: pd.DataFrame, splits: pd.DataFrame, items: list[str]) -> pd.DataFrame:
    """A per-share figure is on the share basis of the date it was filed: every split after that date applies.
    shares x factor; EPS / factor. Derived or manual rows carry no filing date and are left unadjusted (none exist
    for these items: EPS and share counts are never derived)."""
    f = facts.copy()
    for col in EXTRA_COLUMNS[:3]:
        if col not in f.columns:
            f[col] = ""
    by_ticker = {t: [(r.date, Decimal(r.ratio)) for r in g.itertuples()] for t, g in splits.groupby("ticker")}
    for i, r in f[f["line_item"].isin(items)].iterrows():
        if _blank(r["filed"]):
            continue
        factor = Decimal(1)
        for d, ratio in by_ticker.get(r["ticker"], []):
            if d > r["filed"]:
                factor *= ratio
        v = _num(r["value"])
        adj = v * factor if r["line_item"] == "shares_diluted" else Decimal(v) / factor
        disp, _, _ = _display(adj, r["unit"])
        f.at[i, "split_factor"] = factor
        f.at[i, "value_split_adjusted"] = adj
        f.at[i, "display_split_adjusted"] = disp
    return f


# ---------------------------------------------------------------- checks

def step3_checks(facts_t: pd.DataFrame, step2_t: pd.DataFrame, cfg: dict, s3: dict, ticker: str,
                 manual_problems: list[str]) -> list:
    out = []
    keep = [c for c in s2.OUT_COLUMNS]
    # C24: every Step 2 row is unchanged (same selection rules, same collection)
    def norm(df):
        return df[keep].map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v))
    a = norm(step2_t)
    b = norm(facts_t[facts_t["line_item"].isin(set(step2_t["line_item"])) & ~facts_t["value_basis"].isin(STEP3_BASES)])
    merged = a.merge(b, how="outer", indicator=True)
    diff = int((merged["_merge"] != "both").sum()) + abs(len(a) - len(b))
    out.append(("C24_step2_rows_unchanged", diff == 0, f"{diff} rows differ from the signed-off Step 2 output"))

    ds = facts_t[facts_t["value_basis"] == "derived_sum"]
    bad = 0
    for r in ds.itertuples():
        name = r.transformation.split("(")[1].split(")")[0]
        terms = s3["derivations"][name]["terms"]
        total = Decimal(0)
        for t in terms:
            x = facts_t[(facts_t["line_item"] == t) & (facts_t["period_start"] == r.period_start) & (facts_t["period_end"] == r.period_end)]
            if len(x) == 1:
                total += _num(x.iloc[0]["value"])
            elif len(x) == 0 and f"{t} absent, taken as 0" in r.transformation:
                continue
            else:
                bad += 1
                break
        else:
            bad += total != _num(r.value)
    out.append(("C21_derived_sums_recompute", bad == 0, f"{bad} of {len(ds)} derived sums fail"))

    dz = facts_t[facts_t["value_basis"] == "declared_zero"]
    allowed = (s3["companies"].get(ticker, {}).get("declared_zero")) or {}
    other = facts_t[~facts_t["value_basis"].isin({"declared_zero"})]
    clash = sum(1 for r in dz.itertuples() if r.line_item not in allowed
                or not other[(other["line_item"] == r.line_item) & (other["period_end"] == r.period_end)].empty
                or int(r.fiscal_year) < int(allowed[r.line_item]["from_fiscal_year"]))
    out.append(("C22_declared_zeros_only_where_configured", clash == 0, f"{len(dz)} declared zeros, {clash} not allowed"))

    mf = facts_t[facts_t["value_basis"] == "manual_from_filing"]
    rep = facts_t[~facts_t["value_basis"].isin(STEP3_BASES)]
    overlap = sum(1 for r in mf.itertuples()
                  if not rep[(rep["line_item"] == r.line_item) & (rep["period_end"] == r.period_end)].empty)
    out.append(("C23_manual_facts_valid", not manual_problems and overlap == 0,
                f"{len(mf)} manual facts; {overlap} overlap a selected value; problems: {manual_problems or 'none'}"))

    # C19: split-adjusted EPS x split-adjusted diluted shares reproduces net income (annual)
    worst, tested, failed = Decimal(0), 0, []
    rev = facts_t[(facts_t["line_item"] == "revenue") & (facts_t["value_basis"] == "reported_annual")]
    latest_fy = int(rev["fiscal_year"].astype(int).max())
    eps = facts_t[(facts_t["line_item"] == "eps_diluted") & (facts_t["value_basis"] == "reported_annual")]
    for r in eps.itertuples():
        sh = facts_t[(facts_t["line_item"] == "shares_diluted") & (facts_t["value_basis"] == "reported_annual") & (facts_t["period_end"] == r.period_end)]
        # EPS is computed on net income to common shareholders where the company tags it (preferred dividends, NCI)
        ni = facts_t[(facts_t["line_item"] == "ni_to_common") & (facts_t["value_basis"] == "reported_annual") & (facts_t["period_end"] == r.period_end)]
        if len(ni) != 1:
            ni = facts_t[(facts_t["line_item"] == "net_income") & (facts_t["value_basis"] == "reported_annual") & (facts_t["period_end"] == r.period_end)]
        if len(sh) != 1 or len(ni) != 1 or _blank(r.value_split_adjusted) or _blank(sh.iloc[0]["value_split_adjusted"]):
            continue
        shares = _num(sh.iloc[0]["value_split_adjusted"])
        implied = _num(r.value_split_adjusted) * shares
        tolerance = Decimal("0.0051") / (_num(r.split_factor) if not _blank(r.split_factor) else 1) * shares + abs(_num(ni.iloc[0]["value"])) * Decimal("0.03")
        gap = abs(implied - _num(ni.iloc[0]["value"]))
        if int(r.fiscal_year) <= latest_fy - 10:
            continue  # outside the 10-year window (pre-window share counts carry known scale errors, I-16)
        tested += 1
        if gap > tolerance:
            failed.append(f"FY{r.fiscal_year}")
    out.append(("C19_split_adjusted_eps_x_shares_matches_net_income", tested > 0 and not failed,
                f"{tested} fiscal years in the window tested; outside tolerance: {failed or 'none'}"))

    # C20: no split-sized jump left in the split-adjusted annual share series
    s = facts_t[(facts_t["line_item"] == "shares_diluted") & (facts_t["value_basis"] == "reported_annual")].sort_values("period_end")
    vals = [(_num(v), y) for v, y in zip(s["value_split_adjusted"], s["fiscal_year"]) if not _blank(v)]
    jumps = [f"FY{y2}" for (v1, _), (v2, y2) in zip(vals, vals[1:]) if v1 and not (Decimal("0.5") <= Decimal(v2) / Decimal(v1) <= Decimal("2"))]
    jumps_in = [j for j in jumps if int(j[2:]) > latest_fy - 10]
    out.append(("C20_split_adjusted_shares_smooth_in_window", not jumps_in,
                f"jumps over 2x inside the window: {jumps_in or 'none'}; outside: {[j for j in jumps if j not in jumps_in] or 'none'}"))

    unknown = set(facts_t["value_basis"]) - ALL_BASES
    out.append(("C15b_value_basis_vocabulary_step3", not unknown, f"unknown: {sorted(unknown)}"))
    dupes = int(facts_t.duplicated(s2.KEY, keep=False).sum())
    out.append(("C16b_unique_keys_step3", dupes == 0, f"{dupes} duplicate key rows"))
    return [(*c, "error") for c in out]


def coverage_checks(facts_t: pd.DataFrame, cfg: dict, s3: dict, latest_fy: int) -> list:
    """Report-only: annual coverage of every Step 3 line item in the 10-year window."""
    out = []
    for item, spec in s3["line_items"].items():
        per, bases = (("Q4", {"reported_instant", "derived_component", "derived_sum", "declared_zero", "manual_from_filing"})
                      if spec["period_type"] == "instant" else
                      ("FY", {"reported_annual", "derived_component", "derived_sum", "manual_from_filing"}))
        have = {int(y) for y in facts_t[(facts_t["line_item"] == item) & (facts_t["fiscal_period"] == per)
                                        & facts_t["value_basis"].isin(bases)]["fiscal_year"]}
        miss = [y for y in range(latest_fy - 9, latest_fy + 1) if y not in have]
        out.append((f"W3_coverage_{item}", not miss, f"missing FY{miss}" if miss else "10/10", "warning"))
    return out


def ltm_check(facts_t: pd.DataFrame, cfg: dict, items: list[str], check_id="C18_ltm_quarters_complete", level="error"):
    """C18 (error, Step 2 flows) / W4 (warning, Step 3 flows, S3-D11): each of the four latest fiscal quarters exists."""
    flows = items
    qbases = {"reported_quarter", "derived_quarter", "derived_q4", "derived_component", "derived_sum", "manual_from_filing"}
    q = facts_t[facts_t["value_basis"].isin(qbases) & facts_t["fiscal_period"].astype(str).str.startswith("Q")]
    ends = sorted(set(q.loc[q["line_item"] == "revenue", "period_end"]))[-4:]
    missing = [f"{i}@{e}" for i in flows for e in ends if q[(q["line_item"] == i) & (q["period_end"] == e)].empty]
    return (check_id, len(ends) == 4 and not missing,
            f"latest 4 quarters end {ends[0] if ends else '-'} to {ends[-1] if ends else '-'}; missing {missing or 'none'}", level)
