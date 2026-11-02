"""Live retrieval of SEC companyfacts. Saves the response bytes unchanged and records a manifest row.

Nothing here parses or edits the data: the saved file is the evidence every later step is checked against.
"""
from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from common import PROJECT_ROOT, sha256_bytes

MANIFEST_FIELDS = [
    "retrieved_at_utc", "url", "http_status", "bytes", "sha256",
    "file", "valid_json", "cik_in_file", "entity_name",
]


def _user_agent(cfg: dict) -> str:
    env_name = cfg["sec"]["user_agent_env"]
    ua = os.environ.get(env_name, "").strip()
    if not ua or "@" not in ua:
        raise RuntimeError(
            f"Set the {env_name} environment variable to 'Your Name your-email@example.com' "
            "before a live SEC request (SEC requires a contact in the User-Agent)."
        )
    return ua


def fetch_companyfacts(cfg: dict, root: Path = PROJECT_ROOT) -> Path:
    """Download companyfacts once, save the exact bytes, append a manifest row, return the saved path."""
    cik = cfg["company"]["cik"]
    url = cfg["sec"]["companyfacts_url"].format(cik=cik)
    headers = {"User-Agent": _user_agent(cfg), "Accept-Encoding": "gzip, deflate"}

    last_error = None
    resp = None
    for attempt in range(1, cfg["sec"]["max_retries"] + 1):
        time.sleep(cfg["sec"]["min_seconds_between_requests"])
        try:
            resp = requests.get(url, headers=headers, timeout=cfg["sec"]["timeout_seconds"])
        except requests.RequestException as exc:  # network failure: retry with backoff
            last_error = exc
            time.sleep(2 ** attempt)
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            last_error = RuntimeError(f"HTTP {resp.status_code}")
            time.sleep(2 ** attempt)
            continue
        break
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else "no response"
        raise RuntimeError(f"SEC request failed ({status}); last error: {last_error}")

    body = resp.content  # decoded body bytes, saved exactly as received
    retrieved = datetime.now(timezone.utc)
    stamp = retrieved.strftime("%Y%m%dT%H%M%SZ")
    raw_dir = root / cfg["paths"]["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = raw_dir / f"companyfacts_CIK{cik}_{stamp}.json"
    if out_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing snapshot {out_path}")
    out_path.write_bytes(body)

    valid_json, cik_in_file, entity = "false", "", ""
    try:
        parsed = json.loads(body)
        valid_json = "true"
        cik_in_file = str(parsed.get("cik", ""))
        entity = str(parsed.get("entityName", ""))
    except ValueError:
        pass

    manifest = root / cfg["paths"]["manifest"]
    new_file = not manifest.exists()
    with open(manifest, "a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerow({
            "retrieved_at_utc": retrieved.isoformat(timespec="seconds"),
            "url": url,
            "http_status": resp.status_code,
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "file": out_path.relative_to(root).as_posix(),
            "valid_json": valid_json,
            "cik_in_file": cik_in_file,
            "entity_name": entity,
        })

    if valid_json != "true":
        raise RuntimeError(f"Saved {out_path.name}, but it is not valid JSON; see manifest.")
    if int(cik_in_file or 0) != int(cik):
        raise RuntimeError(f"Saved {out_path.name}, but its CIK {cik_in_file} does not match {cik}.")
    return out_path


def latest_snapshot(cfg: dict, root: Path = PROJECT_ROOT) -> Path:
    """Most recent valid snapshot listed in the manifest."""
    manifest = root / cfg["paths"]["manifest"]
    if not manifest.exists():
        raise FileNotFoundError("No manifest yet: run a live fetch first (python python/run_m1.py --source live).")
    with open(manifest, encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["valid_json"] == "true"]
    if not rows:
        raise FileNotFoundError("Manifest has no valid snapshots.")
    return root / max(rows, key=lambda r: r["retrieved_at_utc"])["file"]
