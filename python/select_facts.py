"""Turn the observations layer into one value per line item and period, with every choice recorded.

Rules (each one is in docs/decision_log.md and checked by validate_m1.py):
  * Concept choice: the first listed candidate concept that has an observation for the period.
  * Restatements (D4): within that concept, the latest-filed observation wins (ties: higher accession).
    The earliest-filed value is kept beside it as original_value / original_accn.
  * Fiscal labels come from the period dates, never from SEC's fy/fp fields, because SEC's fy/fp
    describe the filing, not the period (a FY2026 10-K also carries FY2025 comparatives tagged fy=2026).
  * Q4 for additive flow items = annual minus 9-month YTD (same start date), labelled derived_q4.
    It is never labelled as reported, and is not derived if SEC reports a 3-month Q4 directly.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd

BASIS_LABELS = {
    "quarter": "reported_quarter",
    "ytd_6m": "reported_ytd",
    "ytd_9m": "reported_ytd",
    "annual": "reported_annual",
    "instant": "reported_instant",
}
VALUE_BASES = {"reported_quarter", "reported_ytd", "reported_annual", "reported_instant", "derived_q4"}

SELECTED_COLUMNS = [
    "line_item", "statement", "fiscal_year", "fiscal_period", "value_basis",
    "period_start", "period_end", "value", "unit", "display_value", "display_unit",
    "concept", "accn", "form", "filed", "sec_fy", "sec_fp", "frame",
    "n_observations", "n_distinct_values", "restated",
    "original_value", "original_accn", "original_filed",
    "other_candidate_concepts", "derived_from_accns", "transformation", "snapshot_sha256",
]
SELECTED_KEY = ["line_item", "period_start", "period_end", "value_basis"]

GAP_COLUMNS = ["line_item", "fiscal_year", "fiscal_period", "expected_basis", "reason"]


# ---------- fiscal calendar ----------

def fiscal_labels(period_end: str, fy_end_month: int) -> tuple[int, int]:
    """(fiscal_year, fiscal_quarter) for a period ending on period_end.

    Fiscal years ending on a weekday near month-end can spill a few days into the next month,
    so an end date in the first 7 days of a month is treated as belonging to the previous month.
    The fiscal year is named after the calendar year in which it ends (NVIDIA: FY2026 ends Jan 2026).
    """
    anchor = date.fromisoformat(period_end)
    if anchor.day <= 7:
        anchor = anchor - timedelta(days=8)
    fiscal_year = anchor.year if anchor.month <= fy_end_month else anchor.year + 1
    quarter = ((anchor.month - fy_end_month - 1) % 12) // 3 + 1
    return fiscal_year, quarter


def classify_duration(days, bounds: dict) -> str:
    if days is None or days == "" or (isinstance(days, float) and days != days):
        return "instant"
    for name in ("quarter", "ytd_6m", "ytd_9m", "annual"):
        lo, hi = bounds[name]
        if lo <= int(days) <= hi:
            return name
    return "other"


def _fiscal_period(kind: str, quarter: int) -> str:
    if kind == "annual":
        return "FY"
    if kind == "ytd_6m":
        return "6M"
    if kind == "ytd_9m":
        return "9M"
    return f"Q{quarter}"


# ---------- value display ----------

def _display(value, unit: str) -> tuple[object, str, str]:
    v = Decimal(value) if not isinstance(value, Decimal) else value
    if unit == "USD":
        return v / Decimal(1_000_000), "USD millions", "scaled to millions (value / 1,000,000)"
    if unit == "shares":
        return v / Decimal(1_000_000), "shares millions", "scaled to millions (value / 1,000,000)"
    return value, unit, "none"


def _as_number(value):
    return value if isinstance(value, (int, Decimal)) else Decimal(str(value))


# ---------- selection ----------

def select_line_items(obs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    fy_month = cfg["company"]["fiscal_year_end_month"]
    bounds = cfg["selection"]["duration_days"]
    allowed_forms = set(cfg["selection"]["allowed_forms"])
    out_rows = []

    for item, spec in cfg["line_items"].items():
        candidates = list(spec["candidates"])
        pool = obs[
            (obs["taxonomy"] == "us-gaap")
            & (obs["concept"].isin(candidates))
            & (obs["unit"] == spec["unit"])
            & (obs["form"].isin(allowed_forms))
            & (obs["period_type"] == spec["period_type"])
        ].copy()
        if pool.empty:
            continue
        pool["kind"] = pool["duration_days"].map(lambda d: classify_duration(d, bounds))
        pool = pool[pool["kind"] != "other"]
        pool["priority"] = pool["concept"].map(candidates.index)

        for (start, end, kind), grp in pool.groupby(["period_start", "period_end", "kind"], sort=True):
            best_priority = grp["priority"].min()
            chosen = grp[grp["priority"] == best_priority]
            others = sorted(set(grp["concept"]) - set(chosen["concept"]))
            ordered = chosen.sort_values(["filed", "accn"], kind="mergesort")
            latest = ordered.iloc[-1]
            original = ordered.iloc[0]
            distinct_values = {str(_as_number(v)) for v in chosen["value"]}
            fy, q = fiscal_labels(end, fy_month)
            disp, disp_unit, transform = _display(latest["value"], spec["unit"])
            out_rows.append({
                "line_item": item,
                "statement": spec["statement"],
                "fiscal_year": fy,
                "fiscal_period": _fiscal_period(kind, q),
                "value_basis": BASIS_LABELS[kind],
                "period_start": start,
                "period_end": end,
                "value": latest["value"],
                "unit": spec["unit"],
                "display_value": disp,
                "display_unit": disp_unit,
                "concept": latest["concept"],
                "accn": latest["accn"],
                "form": latest["form"],
                "filed": latest["filed"],
                "sec_fy": latest["sec_fy"],
                "sec_fp": latest["sec_fp"],
                "frame": latest["frame"],
                "n_observations": len(chosen),
                "n_distinct_values": len(distinct_values),
                "restated": str(_as_number(latest["value"])) != str(_as_number(original["value"])),
                "original_value": original["value"],
                "original_accn": original["accn"],
                "original_filed": original["filed"],
                "other_candidate_concepts": "|".join(others),
                "derived_from_accns": "",
                "transformation": transform,
                "snapshot_sha256": latest["snapshot_sha256"],
            })

    selected = pd.DataFrame(out_rows, columns=SELECTED_COLUMNS, dtype=object)
    derived = derive_q4(selected, cfg)
    return pd.concat([selected, derived], ignore_index=True) if not derived.empty else selected


def derive_q4(selected: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Q4 = annual minus 9-month YTD with the same start date, for items with derive_q4: true."""
    rows = []
    for item, spec in cfg["line_items"].items():
        if not spec.get("derive_q4"):
            continue
        s = selected[selected["line_item"] == item]
        annual = s[s["value_basis"] == "reported_annual"]
        ytd9 = s[(s["value_basis"] == "reported_ytd") & (s["fiscal_period"] == "9M")]
        quarters = s[s["value_basis"] == "reported_quarter"]
        for _, a in annual.iterrows():
            if not quarters[quarters["period_end"] == a["period_end"]].empty:
                continue  # SEC reports Q4 directly: keep the reported value, derive nothing
            match = ytd9[(ytd9["period_start"] == a["period_start"]) & (ytd9["period_end"] < a["period_end"])]
            if len(match) != 1:
                continue  # inputs missing or ambiguous: the gap report records it
            n = match.iloc[0]
            if n["concept"] != a["concept"]:
                continue  # never subtract across different concepts
            value = _as_number(a["value"]) - _as_number(n["value"])
            q4_start = (date.fromisoformat(n["period_end"]) + timedelta(days=1)).isoformat()
            disp, disp_unit, _ = _display(value, spec["unit"])
            rows.append({
                "line_item": item,
                "statement": spec["statement"],
                "fiscal_year": a["fiscal_year"],
                "fiscal_period": "Q4",
                "value_basis": "derived_q4",
                "period_start": q4_start,
                "period_end": a["period_end"],
                "value": value,
                "unit": spec["unit"],
                "display_value": disp,
                "display_unit": disp_unit,
                "concept": a["concept"],
                "accn": "", "form": "", "filed": "", "sec_fy": "", "sec_fp": "", "frame": "",
                "n_observations": "", "n_distinct_values": "", "restated": "",
                "original_value": "", "original_accn": "", "original_filed": "",
                "other_candidate_concepts": "",
                "derived_from_accns": f"annual:{a['accn']}|9M:{n['accn']}",
                "transformation": "derived: annual minus 9-month YTD; then scaled as for reported values"
                if spec["unit"] != "USD/shares" else "derived: annual minus 9-month YTD",
                "snapshot_sha256": a["snapshot_sha256"],
            })
    return pd.DataFrame(rows, columns=SELECTED_COLUMNS, dtype=object)


# ---------- gaps ----------

def gap_report(selected: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, int | None]:
    """List every expected (line item, fiscal year, period) in the target window that has no value.

    The window is the latest fiscal year with a reported annual revenue value and the 9 years before it.
    Missing values are listed with a reason; nothing is filled in.
    """
    n_years = cfg["history"]["target_fiscal_years"]
    rev = selected[(selected["line_item"] == "revenue") & (selected["value_basis"] == "reported_annual")]
    if rev.empty:
        return pd.DataFrame([{"line_item": "revenue", "fiscal_year": "", "fiscal_period": "FY",
                              "expected_basis": "reported_annual", "reason": "no annual revenue found; window undefined"}],
                            columns=GAP_COLUMNS), None
    latest = int(max(rev["fiscal_year"]))
    years = range(latest - n_years + 1, latest + 1)
    gaps = []

    def has(item, fy, period, bases):
        s = selected
        return not s[(s["line_item"] == item) & (s["fiscal_year"] == fy)
                     & (s["fiscal_period"] == period) & (s["value_basis"].isin(bases))].empty

    for item, spec in cfg["line_items"].items():
        for fy in years:
            if spec["period_type"] == "instant":
                for q in ("Q1", "Q2", "Q3", "Q4"):
                    if not has(item, fy, q, {"reported_instant"}):
                        gaps.append([item, fy, q, "reported_instant", "no_observation"])
                continue
            if not has(item, fy, "FY", {"reported_annual"}):
                gaps.append([item, fy, "FY", "reported_annual", "no_observation"])
            for q in ("Q1", "Q2", "Q3"):
                if has(item, fy, q, {"reported_quarter"}):
                    continue
                ytd = {"Q2": "6M", "Q3": "9M"}.get(q)
                reason = "only_ytd_reported" if ytd and has(item, fy, ytd, {"reported_ytd"}) else "no_observation"
                gaps.append([item, fy, q, "reported_quarter", reason])
            if not has(item, fy, "Q4", {"reported_quarter", "derived_q4"}):
                if not spec.get("derive_q4"):
                    reason = "not_derivable_by_subtraction"
                elif not has(item, fy, "FY", {"reported_annual"}):
                    reason = "derived_q4_inputs_missing: annual"
                elif not has(item, fy, "9M", {"reported_ytd"}):
                    reason = "derived_q4_inputs_missing: 9M YTD"
                else:
                    reason = "derived_q4_not_computed: concept mismatch or ambiguous inputs"
                gaps.append([item, fy, "Q4", "reported_quarter or derived_q4", reason])
    return pd.DataFrame(gaps, columns=GAP_COLUMNS, dtype=object), latest


# ---------- diagnostics ----------

def concept_availability(obs: pd.DataFrame, selected: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rows = []
    for item, spec in cfg["line_items"].items():
        for rank, concept in enumerate(spec["candidates"], start=1):
            c = obs[(obs["taxonomy"] == "us-gaap") & (obs["concept"] == concept)]
            in_unit = c[c["unit"] == spec["unit"]]
            used = selected[(selected["line_item"] == item) & (selected["concept"] == concept)
                            & (selected["value_basis"] != "derived_q4")]
            rows.append({
                "line_item": item,
                "priority": rank,
                "concept": concept,
                "observations_in_expected_unit": len(in_unit),
                "units_present": "|".join(sorted(set(c["unit"]))),
                "first_period_end": min(in_unit["period_end"]) if len(in_unit) else "",
                "last_period_end": max(in_unit["period_end"]) if len(in_unit) else "",
                "selected_rows_using_concept": len(used),
            })
    return pd.DataFrame(rows, dtype=object)
