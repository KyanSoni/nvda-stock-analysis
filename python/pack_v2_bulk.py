"""Version 2: pack the bulk downloads (SEC submissions and company facts, the latest complete price collection) into zip files
of at most ~300 MB in <bulk>\\pack\\, so they can be handed over in one go. The files go in exactly as saved (the SEC files
are already gzip-compressed, so they are stored, not recompressed); a list of every file with its SHA-256 goes alongside.

Usage: & $vpy python\\pack_v2_bulk.py     (offline; nothing in the project folder changes)
"""
from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path

import yaml

import v2_sec as s
from common import PROJECT_ROOT, sha256_file

LIMIT = 300 * 1024 * 1024


def pack(files: list[tuple[Path, str]], out_dir: Path, stem: str) -> list[Path]:
    parts, size, n = [], 0, 1
    z = None
    for path, arc in files:
        b = path.stat().st_size
        if z is None or size + b > LIMIT:
            if z:
                z.close()
            parts.append(out_dir / f"{stem}_{n:02d}.zip")
            z = zipfile.ZipFile(parts[-1], "w")
            size, n = 0, n + 1
        kind = zipfile.ZIP_STORED if path.suffix == ".gz" else zipfile.ZIP_DEFLATED
        z.write(path, arc, compress_type=kind)
        size += b
    if z:
        z.close()
    return parts


def main(argv=None) -> int:
    cfg = yaml.safe_load((PROJECT_ROOT / "config" / "v2.yaml").read_text(encoding="utf-8"))
    root = s.bulk_root(cfg)
    out = root / "pack"
    out.mkdir(exist_ok=True)
    for old in out.glob("*"):
        old.unlink()
    groups = {"sec_submissions": sorted((root / "sec" / "submissions").glob("*.gz")),
              "sec_companyfacts": sorted((root / "sec" / "companyfacts").glob("*.gz")),
              "sec_meta": [p for p in (root / "sec" / "manifest.csv", root / "sec" / "candidates.json") if p.exists()]}
    prices = sorted(p for p in (root / cfg["prices"]["raw_dir_name"]).glob("*T*Z") if (p / "complete.json").exists())
    groups["prices"] = sorted(prices[-1].glob("*")) if prices else []
    listing = []
    for stem, paths in groups.items():
        files = [(p, p.relative_to(root).as_posix()) for p in paths]
        parts = pack(files, out, stem) if files else []
        listing += [{"file": a, "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p, a in files]
        print(f"  {stem}: {len(files)} files -> {', '.join(x.name for x in parts) or 'none'}")
    with open(out / "pack_listing.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "bytes", "sha256"], lineterminator="\n")
        w.writeheader()
        w.writerows(listing)
    total = sum(p.stat().st_size for p in out.glob("*.zip"))
    print(f"Packed {len(listing)} files, {total / 1e6:,.0f} MB, into {out}")
    if not prices:
        print("No complete price collection yet: run python\\fetch_v2_prices.py first")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
