"""Flatten a companyfacts snapshot into one row per SEC observation, keeping every observation and its provenance.

No row is dropped, merged or edited here. Numbers are kept exactly as published (ints stay ints,
decimals are parsed as Decimal), so the observations layer is a faithful copy of the snapshot.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from common import sha256_bytes

OBSERVATION_COLUMNS = [
    "snapshot_sha256", "cik", "entity_name", "taxonomy", "concept", "unit",
    "period_type", "period_start", "period_end", "duration_days", "value",
    "accn", "sec_fy", "sec_fp", "form", "filed", "frame",
]
OBSERVATION_KEY = ["taxonomy", "concept", "unit", "period_start", "period_end", "accn", "form", "filed", "frame", "value"]


def load_snapshot(path: Path | str) -> tuple[dict, str]:
    data = Path(path).read_bytes()
    return json.loads(data, parse_float=Decimal), sha256_bytes(data)


def parse_observations(facts_json: dict, snapshot_sha256: str) -> pd.DataFrame:
    rows = []
    cik = str(facts_json.get("cik", ""))
    entity = str(facts_json.get("entityName", ""))
    for taxonomy, concepts in facts_json.get("facts", {}).items():
        for concept, body in concepts.items():
            for unit, observations in body.get("units", {}).items():
                for o in observations:
                    start = o.get("start")
                    end = o["end"]
                    if start:
                        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
                        ptype = "duration"
                    else:
                        days = None
                        ptype = "instant"
                    rows.append({
                        "snapshot_sha256": snapshot_sha256,
                        "cik": cik,
                        "entity_name": entity,
                        "taxonomy": taxonomy,
                        "concept": concept,
                        "unit": unit,
                        "period_type": ptype,
                        "period_start": start or "",
                        "period_end": end,
                        "duration_days": days,
                        "value": o["val"],
                        "accn": o.get("accn", ""),
                        "sec_fy": o.get("fy", ""),
                        "sec_fp": o.get("fp", ""),
                        "form": o.get("form", ""),
                        "filed": o.get("filed", ""),
                        "frame": o.get("frame", ""),
                    })
    # dtype=object keeps ints as ints and Decimals as Decimals (no float conversion anywhere)
    return pd.DataFrame(rows, columns=OBSERVATION_COLUMNS, dtype=object)
