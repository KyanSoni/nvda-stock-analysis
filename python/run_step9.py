"""Step 9: the investment memo. Renders docs/memo/NVDA_investment_memo.md and docs/memo/exhibits/football_field.svg from
docs/memo/memo_template.md and the Step 3-7 outputs, and writes data/clean/step9/memo_numbers.csv (every number with its
source).

Usage (project folder, project venv; Steps 4-7 outputs present; no network, no database):
  & $vpy python\\run_step9.py            # write the memo, exhibit and numbers file
  & $vpy python\\run_step9.py --check    # write nothing; fail if the memo in docs\\memo differs from a fresh render
Exit code 0 = every check passes.
"""
from __future__ import annotations

import argparse
import json
import re
import string
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import step9_memo as s
from common import PROJECT_ROOT, sha256_file, write_csv

OUT = PROJECT_ROOT / "data" / "clean" / "step9"


def fmt_value(v) -> str:
    return f"{v:.6f}" if isinstance(v, float) else str(v)


def checks(res: dict, template: str) -> list[tuple]:
    n, cfg = res["numbers"], res["cfg"]
    out = []
    bad = [c for c, ok in res["claims"] if not ok]
    out.append(("M1_comparative_claims_true", not bad, f"{len(res['claims'])} claims; false: {bad or 'none'}"))
    keys = {f[1] for f in string.Formatter().parse(template) if f[1]}
    nosrc = sorted(k for k in keys - {"catalysts", "ex_valuation", "ex_grid", "ex_comps", "ex_scen"} if k not in {r[0] for r in res["sources"]})
    out.append(("M2_every_number_has_a_source", not nosrc, f"{len(keys)} placeholders; without a source: {nosrc or 'none'}"))
    raw = n["w_dcf"] * n["dcf_w"] * (1 + n["ke"] - n["div_yield"]) + n["w_comps"] * n["comps"]
    step = cfg["target"]["round_to"]
    ok = abs(raw - n["target_raw"]) < 1e-9 and abs(n["target"] - raw) <= step / 2 + 1e-9 and n["target"] % step == 0
    out.append(("M3_target_arithmetic", ok, f"{n['w_dcf']} x {n['dcf_w']:.4f} x (1 + {n['ke']:.4f} - {n['div_yield']:.4f}) + {n['w_comps']} x {n['comps']:.4f} = {raw:.4f} -> {n['target']:.0f}"))
    b = cfg["rating_bands"]
    exp = n["target"] / n["price"] - 1 + n["div_yield"]
    want = "Buy" if exp > b["buy_above"] else "Sell" if exp < b["sell_below"] else "Hold"
    out.append(("M4_rating_follows_bands", want == n["rating"] and abs(exp - n["exp_return"]) < 1e-12, f"expected return {exp:+.2%} -> {want}"))
    first = res["memo"].splitlines()[0]
    ok = n["rating"] in first and f"${n['target']:,.0f}" in first and f"${n['price']:.2f}" in first
    out.append(("M5_rating_and_target_in_first_line", ok, first[:90]))
    words = len(re.sub(r"[#*|`\-]", " ", res["memo"].split("## Exhibits")[0]).split())
    out.append(("M6_page_one_length", words <= 1100, f"{words} words before the exhibits (limit 1,100, about one page at 10 pt)"))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    missing = s.missing_inputs()
    if missing:
        print("Step 9 inputs missing (run Steps 4-7 first):\n  " + "\n  ".join(missing))
        return 1
    template = s.TEMPLATE.read_text(encoding="utf-8")
    res = s.build()
    out = Path(args.out) if args.out else OUT
    memo_path, svg_path = (out / "NVDA_investment_memo.md", out / "football_field.svg") if args.out else (s.MEMO, s.SVG)
    cks = checks(res, template)
    if args.check:
        same = s.MEMO.exists() and s.MEMO.read_text(encoding="utf-8").replace("\r\n", "\n") == res["memo"] and \
            s.SVG.exists() and s.SVG.read_text(encoding="utf-8").replace("\r\n", "\n") == res["svg"]
        cks.append(("M7_memo_in_docs_is_current", same, "docs/memo matches a fresh render" if same else "docs/memo differs: run python/run_step9.py"))
    else:
        out.mkdir(parents=True, exist_ok=True)
        write_csv(pd.DataFrame([(k, fmt_value(v), sname) for k, v, sname in res["sources"]], columns=["name", "value", "source"]),
                  out / "memo_numbers.csv", ["name"])
        for p, text in ((memo_path, res["memo"]), (svg_path, res["svg"])):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))
        manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "output_sha256": {"memo_numbers.csv": sha256_file(out / "memo_numbers.csv"), "memo": sha256_file(memo_path),
                                      "football_field.svg": sha256_file(svg_path)},
                    "checks": [{"check": c, "passed": bool(ok), "detail": d} for c, ok, d in cks]}
        (out / "manifest_step9.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Step 9 memo -> {memo_path}, {svg_path}, {out / 'memo_numbers.csv'}")
    for c, ok, d in cks:
        print(f"  {'PASS' if ok else 'FAIL'}  {c}: {d}")
    n = res["numbers"]
    print(f"  {n['rating']}, 12-month target ${n['target']:,.0f} ({n['exp_return']:+.1%} vs ${n['price']:.2f}); "
          f"DCF {n['dcf_w']:.2f} -> {n['dcf_fwd']:.2f} rolled forward, comps {n['comps']:.2f}")
    return 0 if all(ok for _, ok, _ in cks) else 1


if __name__ == "__main__":
    sys.exit(main())
