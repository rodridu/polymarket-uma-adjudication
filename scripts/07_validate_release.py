"""07 -- the release checklist. Fixed list, run once per release; a release ships only on all PASS.

    C1  primary keys unique
    C2  referential integrity (ballot -> request -> case; ballot round -> rounds)
    C3  linkage injective (one case per linked DVM request)
    C4  request aggregates reproduce from ballots
    C5  resolved price == revealed-weight mode in the resolution round (every RESOLVED request)
    C6  round state valid (stake > 0; agreement floor 0.50 or 0.65 of stake)
    C7  raw integers are exact decimal strings
    C8  resolved prices are standard values (P1/P2/P3/P4), never NONSTANDARD or null
    C9  provenance complete (tx_hash, log_index, block_number on every ballot; every resolved
        request has an on-chain RequestResolved; no RESOLVED_PRICE_MISSING)
    C10 manifest reproduces (row counts, sha256)

Coverage (link / resolution status) is reported, not graded.

    python scripts/07_validate_release.py
"""
from __future__ import annotations

import hashlib
import json
import re

import pandas as pd

from pmvotes import RELEASE

INT_RE = re.compile(r"^-?\d+$")


def main() -> int:
    T = {k: pd.read_parquet(RELEASE / f"{k}.parquet")
         for k in ("cases", "dvm_requests", "rounds", "ballots")}
    c, q, r, b = T["cases"], T["dvm_requests"], T["rounds"], T["ballots"]
    M = json.loads((RELEASE / "manifest.json").read_text())
    res = []

    def check(cid, name, ok, detail=""):
        res.append((cid, name, bool(ok), detail))

    # C1
    d = {"cases": c["oo_request_id"].duplicated().sum(),
         "dvm_requests": q["dvm_request_id"].duplicated().sum(),
         "rounds": r["round_id"].duplicated().sum(),
         "ballots": b.duplicated(["dvm_request_id", "round_id", "voter"]).sum()}
    check("C1", "primary keys unique", sum(d.values()) == 0, str({k: int(v) for k, v in d.items()}))

    # C2
    orphan_b = (~b["dvm_request_id"].isin(q["dvm_request_id"])).sum()
    orphan_q = (~q["oo_request_id"].isin(c.loc[c["dvm_link_status"].eq("DVM_EXACT"),
                                                "oo_request_id"])).sum()
    missing_q = (~c.loc[c["dvm_link_status"].eq("DVM_EXACT"), "dvm_request_id"]
                 .isin(q["dvm_request_id"])).sum()
    orphan_r = (~b["round_id"].isin(r["round_id"])).sum()
    check("C2", "referential integrity", orphan_b + orphan_q + missing_q + orphan_r == 0,
          f"ballot->req {orphan_b}, req->case {orphan_q}, case->req {missing_q}, "
          f"ballot->round {orphan_r}")

    # C3
    ex = c[c["dvm_link_status"].eq("DVM_EXACT")]
    check("C3", "linkage injective", not ex["dvm_request_id"].duplicated().any()
          and ex["dvm_request_id"].notna().all(), f"{len(ex)} linked cases")

    # C4
    bw = b.assign(w=b["num_tokens_raw"].map(int)).groupby("dvm_request_id").agg(
        n=("voter", "size"), w=("w", "sum"))
    qq = q.set_index("dvm_request_id")
    n_bad = (qq["n_ballots"] != bw["n"].reindex(qq.index).fillna(0).astype(int)).sum()
    has = qq["revealed_weight_raw"].notna()
    w_bad = (qq.loc[has, "revealed_weight_raw"].map(int) != bw["w"].reindex(qq.index[has])).sum()
    check("C4", "aggregates reproduce from ballots", n_bad + w_bad == 0,
          f"n_ballots mismatches {n_bad}, weight mismatches {w_bad}")

    # C5
    rr = q[q["resolution_status"].eq("RESOLVED")]
    br = b.merge(rr[["dvm_request_id", "resolution_round"]], on="dvm_request_id")
    br = br[br["round_id"].eq(br["resolution_round"])]
    br = br.assign(w=br["num_tokens_raw"].map(int))
    mode = (br.groupby(["dvm_request_id", "price_raw"])["w"].sum().reset_index()
            .sort_values("w", ascending=False).drop_duplicates("dvm_request_id")
            .set_index("dvm_request_id")["price_raw"])
    got = rr.set_index("dvm_request_id")["resolved_price_raw"]
    bad = (mode.reindex(got.index) != got).sum()
    check("C5", "resolved price == revealed-weight mode", bad == 0,
          f"{len(got) - bad}/{len(got)} resolved requests agree")

    # C6
    st = r["cumulative_stake_raw"].map(int)
    ag = r["min_agreement_raw"].map(int)
    floor = (ag / st.where(st > 0)).round(6)
    check("C6", "round state valid", (st > 0).all() and floor.isin([0.5, 0.65]).all(),
          f"floors {sorted(floor.dropna().unique().tolist())}")

    # C7
    raw_cols = {"cases": ["proposed_price_raw", "bond_raw"],
                "dvm_requests": ["resolved_price_raw", "revealed_weight_raw"],
                "rounds": ["cumulative_stake_raw", "min_participation_raw", "min_agreement_raw"],
                "ballots": ["price_raw", "num_tokens_raw"]}
    badc = {f"{t}.{col}": int((~T[t][col].dropna().astype(str).str.match(INT_RE)).sum())
            for t, cols in raw_cols.items() for col in cols}
    check("C7", "raw integers exact", sum(badc.values()) == 0,
          ", ".join(f"{k}={v}" for k, v in badc.items() if v) or "all exact")

    # C8
    rc = q.loc[q["resolved_price_raw"].notna(), "resolved_uma_value_class"]
    check("C8", "resolved prices standard", rc.notna().all() and not rc.eq("NONSTANDARD").any(),
          f"resolved classes {rc.value_counts().to_dict()}")

    # C9
    miss = {k: int(b[k].isna().sum()) for k in ("tx_hash", "log_index", "block_number")}
    dup_ev = int(b.dropna(subset=["tx_hash", "log_index"])
                 .duplicated(["tx_hash", "log_index"]).sum())
    src_ok = (len(rr) > 0 and rr["resolution_source"].eq("VotingV2.RequestResolved").all()
              and rr["resolution_tx"].notna().all())
    n_pm = int(q["resolution_status"].eq("RESOLVED_PRICE_MISSING").sum())
    check("C9", "provenance complete",
          sum(miss.values()) == 0 and dup_ev == 0 and src_ok and n_pm == 0,
          f"missing {miss}, duplicate events {dup_ev}, resolved-but-no-price {n_pm}, "
          f"resolution sources {rr['resolution_source'].value_counts().to_dict()}")

    # C10
    rows_ok = all(M["rows"][k] == len(v) for k, v in T.items())
    sha_ok = all(hashlib.sha256((RELEASE / f).read_bytes()).hexdigest() == h
                 for f, h in M["sha256"].items())
    check("C10", "manifest reproduces", rows_ok and sha_ok, f"rows {rows_ok}, sha256 {sha_ok}")

    print(f"release {M['version']}  build_mode {M['build_mode']}\n")
    for cid, name, ok, det in res:
        print(f"[{'PASS' if ok else 'FAIL'}] {cid:<4} {name:<42} {det}")
    print("\nCOVERAGE (reported, not graded)")
    print("  cases by link status   ", c["dvm_link_status"].value_counts().to_dict())
    print("  requests by resolution ", q["resolution_status"].value_counts().to_dict())
    print("  requests by ballots    ", q["ballot_status"].value_counts().to_dict())
    n_fail = sum(not ok for *_, ok, _ in res)
    print(f"\n{'RELEASE OK' if n_fail == 0 else f'NOT RELEASABLE: {n_fail} check(s) failed'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
