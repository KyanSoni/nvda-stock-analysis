"""Shared helpers: project paths, config loading, hashing and deterministic CSV output."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "project.yaml"


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(df: pd.DataFrame, path: Path | str, sort_by: list[str]) -> None:
    """Write a CSV that is byte-identical for identical input.

    Every value is converted to text with str() so numbers keep the exact form SEC published
    (no float rounding), rows are sorted on explicit keys, and line endings are always LF.
    """
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else str(v))
    out = out.sort_values(sort_by, kind="mergesort").reset_index(drop=True)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        out.to_csv(fh, index=False, lineterminator="\n")
