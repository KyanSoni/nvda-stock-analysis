"""Version 2, V2.2: resolve the filer (CIK) and sector of every member at every rebalance date, offline.

Reads data/clean/v2/universe/membership.csv, the submissions saved by fetch_v2_sec.py submissions, and the SEC name file
from the latest universe collection. Writes data/clean/v2/sec/:
  cik_by_date.csv     one row per (date, ticker): cik_pit, pit_basis, sector, sector_basis, excluded_sector, note
  unresolved.csv      members with no usable CIK at a date (basis unresolved, ambiguous or no annual report in the window)
  sic_check.csv       SIC-derived sector vs Wikipedia GICS for current members (check S4)
  coverage_sec.csv    per date: members, resolved, share
  manifest_v2_sec.json
Exit code 0 = no error-level check fails.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml

import v2_sec as s
import v2_universe as u
from common import PROJECT_ROOT, sha256_file, write_csv

CFG = PROJECT_ROOT / "config" / "v2.yaml"
OUT = PROJECT_ROOT / "data" / "clean" / "v2" / "sec"
GOOD = {"v21_cik_annual_report", "edgar_name_annual_report", "v1_verified_chain"}


def build(cfg: dict) -> dict:
    clean = PROJECT_ROOT / cfg["universe"]["clean_dir"]
    mem = pd.read_csv(clean / "membership.csv", dtype=str, keep_default_na=False)
    cur = pd.read_csv(clean / "constituents_current.csv", dtype=str, keep_default_na=False)
    root = s.bulk_root(cfg)
    cpath = root / "sec" / "candidates.json"
    cands = json.loads(cpath.read_text(encoding="utf-8")) if cpath.exists() else {}
    from fetch_v2_sec import latest_universe_raw
    raw = latest_universe_raw(cfg)
    u.sec_maps((raw / "company_tickers.json").read_text(encoding="utf-8"), (raw / "cik-lookup-data.txt").read_text(encoding="latin-1"))
    cik_names = u.sec_maps.cik_names
    wanted = {c for c in mem["cik"] if c} | {c for v in cands.values() for c in v} | set(cur["cik"])
    subs = {c: x for c in sorted(wanted) if (x := s.load_submissions(root, c))}
    chains = s.v1_chains(PROJECT_ROOT / cfg["sec"]["v1_chains"])
    wanted |= {c for v in chains.values() for c in v}
    subs.update({c: x for c in sorted(set(wanted) - set(subs)) if (x := s.load_submissions(root, c))})
    res = s.resolve(mem, subs, cands, cik_names, cfg, chains)
    res = s.sectors(res, cur, subs, cfg)
    res["edgar_name"] = [subs[c][0]["name"] if c in subs else "" for c in res["cik_pit"]]
    res["sic"] = [subs[c][0]["sic"] if c in subs else "" for c in res["cik_pit"]]
    agree, sic_df = s.sic_check(cur, subs, cfg)
    res["resolved"] = res["pit_basis"].isin(GOOD)
    cov = res.groupby("date").agg(members=("ticker", "size"), resolved=("resolved", "sum"),
                                  with_sector=("sector", lambda x: (x != "").sum())).reset_index()
    cov["resolved_share"] = cov["resolved"] / cov["members"]
    return {"res": res, "cov": cov, "sic": sic_df, "sic_agree": agree, "subs": subs, "mem": mem, "cands": cands}


def checks(b: dict, cfg: dict) -> list[tuple]:
    res, cov, subs, mem = b["res"], b["cov"], b["subs"], b["mem"]
    v21 = sorted({c for c in mem["cik"] if c})
    have = sum(c in subs for c in v21)
    out = [("S1_submissions_on_disk", have >= 0.99 * len(v21), f"{have}/{len(v21)} V2.1 CIKs have submissions saved", "error")]
    out.append(("S2_every_member_classified", res["pit_basis"].ne("").all() and len(res) == len(mem),
                f"{len(res)} (date, ticker) rows; bases " + ", ".join(f"{k} {v}" for k, v in res["pit_basis"].value_counts().items()), "error"))
    lo = cov["resolved_share"].min()
    out.append(("S3_resolved_share_each_date", lo >= 0.90,
                "resolved " + ", ".join(f"{d} {x:.1%}" for d, x in zip(cov["date"], cov["resolved_share"])) + (" (target 97%)" if lo < 0.97 else ""), "error"))
    out.append(("S4_sic_sector_agrees_with_gics", b["sic_agree"] >= 0.75,
                f"SIC mapping gives today's GICS sector for {b['sic_agree']:.1%} of current members (sic_check.csv); used only for former members", "warning"))
    nosec = (res["sector"] == "").mean()
    out.append(("S5_sector_present", nosec <= 0.01, f"{nosec:.2%} of member-dates without a sector", "warning"))
    aa = res[(res["ticker"] == "AA") & (res["date"] == f"{cfg['backtest']['first_year']}-{cfg['backtest']['rebalance_month_day']}")]
    ok6 = len(aa) == 0 or (aa.iloc[0]["cik_pit"] != aa.iloc[0]["cik_v21"] and aa.iloc[0]["pit_basis"] == "edgar_name_annual_report")
    nv = res[res["ticker"] == "NVDA"]
    ok6 = ok6 and (nv["cik_pit"] == "0001045810").all() and len(nv) > 0
    av = res[(res["ticker"] == "AVGO") & (res["date"] < "2016-12-01")]
    ok6 = ok6 and (av["cik_pit"] == "0001441634").all()                 # Version 1 verified: Avago Technologies before Broadcom Ltd
    out.append(("S6_known_cases", ok6, "NVDA is CIK 0001045810 at every date; AVGO in 2016 is Avago Technologies (Version 1's chain); AA in April 2016 is the filer that reported then "
                + (f"({aa.iloc[0]['cik_pit']} {aa.iloc[0]['edgar_name']}), not {aa.iloc[0]['cik_v21']} (I-78)" if len(aa) else "(AA not a member)"), "error"))
    sw = res[res["pit_basis"] == "edgar_name_annual_report"]
    bad = sw[~sw["name_agrees"]]
    out.append(("S8_switched_filers_named_alike", bad.empty, f"{len(sw)} member-dates use a filer other than the V2.1 one; all carried a matching EDGAR name on the date"
                if bad.empty else f"{len(bad)} switched rows whose EDGAR name on the date does not match: {sorted(set(bad['ticker']))[:10]}", "error"))
    ren = res[(res["pit_basis"] == "v21_cik_annual_report") & ~res["name_agrees"]].drop_duplicates("ticker")
    out.append(("S9_renamed_filers_kept", True, f"{len(ren)} companies keep their V2.1 filer although it filed under another name then (renamed, e.g. "
                + ", ".join(f"{t} as {n}" for t, n in zip(ren["ticker"].head(5), ren["name_at_date"].head(5))) + ")", "info"))
    dup = res[res["resolved"]].groupby(["date", "cik_pit"])["ticker"].apply(list)
    dup = dup[dup.str.len() > 1]
    pairs = sorted({"/".join(sorted(x)) for x in dup})
    out.append(("S7_shared_ciks", True, f"{len(pairs)} ticker groups share one CIK at a date (dual share classes; one line per company in V2.5): {pairs[:8]}", "info"))
    return out


def main(argv=None) -> int:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    b = build(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["date", "ticker", "security", "cik_pit", "pit_basis", "edgar_name", "name_at_date", "name_agrees", "sic", "sector", "sector_basis", "excluded_sector",
            "cik_v21", "cik_basis_v21", "n_qualifying", "note"]
    write_csv(b["res"][cols], OUT / "cik_by_date.csv", ["date", "ticker"])
    unres = b["res"][~b["res"]["resolved"]]
    write_csv(unres[cols], OUT / "unresolved.csv", ["date", "ticker"])
    write_csv(b["sic"], OUT / "sic_check.csv", ["ticker"])
    write_csv(b["cov"], OUT / "coverage_sec.csv", ["date"])
    cks = checks(b, cfg)
    print(f"V2.2 filer by date -> {OUT}")
    for c, ok, d, lvl in cks:
        print(f"  {'PASS' if ok else ('WARN' if lvl != 'error' else 'FAIL')}  {c}: {d}")
    ch = b["res"][b["res"]["pit_basis"] == "edgar_name_annual_report"].drop_duplicates(["ticker", "cik_pit"])
    print(f"  CIK changed from V2.1 for {ch['ticker'].nunique()} companies, e.g.:")
    for r in ch.head(12).itertuples():
        print(f"    {r.ticker:<6} {r.security[:28]:<28} {r.cik_v21 or '(none)':<10} -> {r.cik_pit} {r.edgar_name[:34]}")
    un = unres.drop_duplicates("ticker")
    print(f"  Not resolved at one or more dates: {len(un)} companies (unresolved.csv); "
          f"{int(unres['excluded_sector'].sum())} of those rows are in excluded sectors")
    files = ["cik_by_date.csv", "unresolved.csv", "sic_check.csv", "coverage_sec.csv"]
    man = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bulk_root": str(s.bulk_root(cfg)),
           "submissions_loaded": len(b["subs"]), "output_sha256": {f: sha256_file(OUT / f) for f in files},
           "checks": [{"check": c, "passed": bool(ok), "detail": d, "level": lvl} for c, ok, d, lvl in cks]}
    (OUT / "manifest_v2_sec.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    return 0 if all(ok for _, ok, _, lvl in cks if lvl == "error") else 1


if __name__ == "__main__":
    sys.exit(main())
