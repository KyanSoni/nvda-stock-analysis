"""Checks run at the end of every M1 run. Each returns (check_id, passed, detail).

These recompute key rules independently from the observations layer rather than trusting the
selection code. A failing check is a finding to investigate and log, never something to suppress.
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from select_facts import SELECTED_KEY, VALUE_BASES


def _num(v):
    return v if isinstance(v, (int, Decimal)) else Decimal(str(v))


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and v != v) or str(v) == ""


def run_checks(obs: pd.DataFrame, selected: pd.DataFrame, cfg: dict, expected_obs_count: int) -> list[tuple[str, bool, str]]:
    results = []

    # C1: every observation in the snapshot is in the observations layer
    results.append(("C1_all_observations_kept", len(obs) == expected_obs_count,
                    f"{len(obs)} rows parsed vs {expected_obs_count} observations counted in the JSON"))

    # C2: one value per line item / period / basis
    dupes = selected.duplicated(SELECTED_KEY, keep=False).sum()
    results.append(("C2_unique_selected_keys", dupes == 0, f"{dupes} duplicate key rows"))

    reported = selected[selected["value_basis"] != "derived_q4"]
    derived = selected[selected["value_basis"] == "derived_q4"]

    # C3: full provenance on every reported row
    prov_cols = ["concept", "unit", "accn", "form", "filed", "snapshot_sha256"]
    missing = sum(reported[c].map(_blank).sum() for c in prov_cols)
    results.append(("C3_reported_rows_have_provenance", missing == 0, f"{missing} blank provenance cells"))

    # C4: derived rows say what they came from and carry no reported-filing fields
    bad = derived[derived["derived_from_accns"].map(_blank) | ~derived["accn"].map(_blank)]
    results.append(("C4_derived_rows_labelled", bad.empty, f"{len(bad)} derived rows mislabelled"))

    # C5: controlled vocabulary for value_basis
    unknown = set(selected["value_basis"]) - VALUE_BASES
    results.append(("C5_value_basis_vocabulary", not unknown, f"unknown: {sorted(unknown)}"))

    # C6: only configured candidate concepts are used
    off = [(r.line_item, r.concept) for r in selected.itertuples()
           if r.concept not in cfg["line_items"][r.line_item]["candidates"]]
    results.append(("C6_only_configured_concepts", not off, f"{len(off)} rows use unlisted concepts"))

    # C7: restatement rule recomputed independently: chosen filing is the latest for that concept and period
    forms = set(cfg["selection"]["allowed_forms"])
    pool = obs[(obs["taxonomy"] == "us-gaap") & obs["form"].isin(forms)]
    latest = (pool.sort_values(["filed", "accn"], kind="mergesort")
                  .groupby(["concept", "unit", "period_start", "period_end"]).tail(1)
                  .set_index(["concept", "unit", "period_start", "period_end"]))
    wrong = 0
    for r in reported.itertuples():
        key = (r.concept, r.unit, r.period_start, r.period_end)
        if key not in latest.index:
            wrong += 1
            continue
        ref = latest.loc[key]
        if str(ref["accn"]) != str(r.accn) or str(_num(ref["value"])) != str(_num(r.value)):
            wrong += 1
    results.append(("C7_latest_filed_rule", wrong == 0, f"{wrong} rows differ from independent latest-filed pick"))

    # C8: fiscal period label agrees with the basis
    expected = {"reported_annual": {"FY"}, "reported_ytd": {"6M", "9M"}, "derived_q4": {"Q4"},
                "reported_quarter": {"Q1", "Q2", "Q3", "Q4"}, "reported_instant": {"Q1", "Q2", "Q3", "Q4"}}
    mismatch = sum(1 for r in selected.itertuples() if r.fiscal_period not in expected.get(r.value_basis, set()))
    results.append(("C8_period_labels_consistent", mismatch == 0, f"{mismatch} inconsistent labels"))

    # C9: derived Q4 arithmetic re-checked from the selected annual and 9M rows
    errors = 0
    for r in derived.itertuples():
        s = selected[(selected["line_item"] == r.line_item) & (selected["period_end"] == r.period_end)
                     & (selected["value_basis"] == "reported_annual")]
        n = selected[(selected["line_item"] == r.line_item) & (selected["fiscal_period"] == "9M")
                     & (selected["fiscal_year"] == r.fiscal_year) & (selected["value_basis"] == "reported_ytd")]
        if len(s) != 1 or len(n) != 1 or _num(s.iloc[0]["value"]) - _num(n.iloc[0]["value"]) != _num(r.value):
            errors += 1
    results.append(("C9_derived_q4_arithmetic", errors == 0, f"{errors} derived values do not recompute"))

    # C10: a single snapshot feeds every row
    shas = set(selected["snapshot_sha256"]) | set(obs["snapshot_sha256"])
    results.append(("C10_single_snapshot", len(shas) <= 1, f"{len(shas)} distinct snapshot hashes"))
    return results


# ---------- C11: scale anomalies (decision C11, issue I-16) ----------

ANOMALY_COLUMNS = [
    "line_item", "fiscal_year", "fiscal_period", "value_basis", "period_end", "value",
    "anomaly_type", "compared_with", "comparison_value", "ratio", "in_target_window", "accn", "filed",
]


def find_scale_anomalies(selected: pd.DataFrame, cfg: dict, latest_fy) -> pd.DataFrame:
    """Flag selected values that look like XBRL scale errors (e.g. thousands tagged as units).

    Two tests, both reporting only (no value is changed or dropped):
      vs_first_filed     - every line item: latest-filed value / first-filed value outside [low, high]
      vs_previous_period - items in validation.scale_check_items: value / previous period's value
                           (same line item and value basis) outside [low, high]
    Stock splits (at most 40x combined for NVIDIA) stay well inside the default 0.01-100 band.
    """
    vcfg = cfg.get("validation", {})
    low = Decimal(str(vcfg.get("scale_ratio_low", "0.01")))
    high = Decimal(str(vcfg.get("scale_ratio_high", "100")))
    trend_items = set(vcfg.get("scale_check_items", []))
    window_start = int(latest_fy) - cfg["history"]["target_fiscal_years"] + 1 if latest_fy else None
    rows = []

    def add(r, kind, compared_with, other, ratio):
        fy = int(r["fiscal_year"])
        rows.append({
            "line_item": r["line_item"], "fiscal_year": fy, "fiscal_period": r["fiscal_period"],
            "value_basis": r["value_basis"], "period_end": r["period_end"], "value": r["value"],
            "anomaly_type": kind, "compared_with": compared_with, "comparison_value": other,
            "ratio": ratio.quantize(Decimal("0.0001")) if isinstance(ratio, Decimal) else ratio,
            "in_target_window": bool(window_start is not None and window_start <= fy <= int(latest_fy)),
            "accn": r["accn"], "filed": r["filed"],
        })

    reported = selected[selected["value_basis"] != "derived_q4"]
    for _, r in reported.iterrows():
        if _blank(r["original_value"]):
            continue
        v, o = _num(r["value"]), _num(r["original_value"])
        if v == 0 or o == 0:
            continue
        ratio = abs(Decimal(v) / Decimal(o))
        if ratio < low or ratio > high:
            add(r, "vs_first_filed", f"first filed {r['original_accn']}", r["original_value"], ratio)

    for (item, basis), grp in reported[reported["line_item"].isin(trend_items)].groupby(["line_item", "value_basis"]):
        grp = grp.sort_values(["period_end", "period_start"], kind="mergesort")
        prev = None
        for _, r in grp.iterrows():
            v = _num(r["value"])
            if prev is not None:
                p = _num(prev["value"])
                if v != 0 and p != 0:
                    ratio = abs(Decimal(v) / Decimal(p))
                    if ratio < low or ratio > high:
                        add(r, "vs_previous_period", f"{prev['fiscal_period']} FY{prev['fiscal_year']} ({prev['period_end']})",
                            prev["value"], ratio)
            prev = r
    return pd.DataFrame(rows, columns=ANOMALY_COLUMNS, dtype=object)


def scale_checks(anomalies: pd.DataFrame) -> tuple[tuple[str, bool, str], tuple[str, bool, str]]:
    """C11 (error level): no scale anomaly inside the target window.
    W1 (warning level): anomalies outside the window, listed for review in anomalies.csv."""
    inside = anomalies[anomalies["in_target_window"] == True]  # noqa: E712 (object column)
    outside = anomalies[anomalies["in_target_window"] != True]  # noqa: E712
    years = sorted({int(y) for y in outside["fiscal_year"]})
    span = f"FY{years[0]}-FY{years[-1]}" if years else "none"
    c11 = ("C11_no_scale_anomalies_in_target_window", inside.empty,
           f"{len(inside)} flagged inside the target window (see anomalies.csv)")
    w1 = ("W1_scale_anomalies_outside_window", outside.empty,
          f"{len(outside)} flagged outside the window ({span}); review only, values unchanged")
    return c11, w1
