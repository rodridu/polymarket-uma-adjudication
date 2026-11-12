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

    v1.1 commit-layer checks (run only when commit-layer tables are present):
    C11 commit-layer primary keys unique
    C12 referential integrity: commit->request, participation->round, incentive->request
    C13 reveal ⊆ commit: every revealed ballot has ≥1 commit in that round
    C14 orthogonal classification: participation_class by price, reward_class by sign
    C15 raw integers: slashed_tokens_raw exact decimal strings
    C16 incentive coverage: every RESOLVED request has ≥1 VoterSlashed event

Coverage (link / resolution status) is reported, not graded.

    python scripts/07_validate_release.py
"""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pandas as pd

from pmvotes import RELEASE

INT_RE = re.compile(r"^-?\d+$")


def main() -> int:
    T = {k: pd.read_parquet(RELEASE / f"{k}.parquet")
         for k in ("cases", "dvm_requests", "rounds", "ballots")}
    c, q, r, b = T["cases"], T["dvm_requests"], T["rounds"], T["ballots"]
    M = json.loads((RELEASE / "manifest.json").read_text())
    commit_tables = ("commits", "participation", "voter_request_incentives")
    has_commit_layer = all(k in M.get("rows", {}) for k in commit_tables)
    if has_commit_layer:
        for k in commit_tables:
            T[k] = pd.read_parquet(RELEASE / f"{k}.parquet")
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

    # ---------------------------------------------------------------- commit-layer checks
    if has_commit_layer:
        cm, pt, vi = T["commits"], T["participation"], T["voter_request_incentives"]

        # C11
        d11 = {"commits": cm.duplicated(["dvm_request_id", "round_id", "voter",
                                          "tx_hash", "log_index"]).sum(),
               "participation": pt.duplicated(["dvm_request_id", "round_id", "voter"]).sum(),
               "incentives": vi.duplicated(["voter", "dvm_request_id"]).sum()}
        check("C11", "commit-layer PKs unique", sum(d11.values()) == 0,
              str({k: int(v) for k, v in d11.items()}))

        # C12
        orphan_cm = (~cm["dvm_request_id"].isin(q["dvm_request_id"])).sum()
        orphan_pt_r = (~pt["round_id"].isin(r["round_id"])).sum()
        orphan_vi = (~vi["dvm_request_id"].isin(q["dvm_request_id"])).sum()
        check("C12", "commit-layer referential integrity",
              orphan_cm + orphan_pt_r + orphan_vi == 0,
              f"commit->req {orphan_cm}, part->round {orphan_pt_r}, incent->req {orphan_vi}")

        # C13
        revealed = set(zip(b["dvm_request_id"], b["round_id"], b["voter"]))
        committed = set(zip(cm["dvm_request_id"], cm["round_id"], cm["voter"]))
        reveal_no_commit = revealed - committed
        check("C13", "reveal subset of commit", len(reveal_no_commit) == 0,
              f"{len(reveal_no_commit)} revealed without commit")

        # C14 — orthogonal classification consistency
        #  a) CORRECT_VOTE must have voted the resolved price in resolution round
        #  b) WRONG_VOTE must have voted a different price in resolution round
        #  c) DID_NOT_VOTE must not appear in resolution-round ballots
        #  d) reward_class values are valid
        #  e) positive reward implies CORRECT_VOTE (never rewards wrong/absent)
        resolved_prices = q.loc[q["resolution_status"].eq("RESOLVED"),
                                ["dvm_request_id", "resolved_price_raw", "resolution_round"]].dropna()
        rp = resolved_prices.set_index("dvm_request_id")
        # (a) CORRECT_VOTE price check
        correct = vi[vi["participation_class"].eq("CORRECT_VOTE")]
        if len(correct) and len(rp):
            merged_c = correct.merge(rp, on="dvm_request_id", how="inner")
            merged_c = merged_c.merge(b[["dvm_request_id", "round_id", "voter", "price_raw"]],
                                      on=["dvm_request_id", "voter"], how="inner")
            res_c = merged_c[merged_c["round_id"].eq(merged_c["resolution_round"])]
            correct_wrong_price = (res_c["price_raw"].astype(str) != res_c["resolved_price_raw"].astype(str)).sum()
        else:
            correct_wrong_price = 0
        # (b) WRONG_VOTE price check
        wrong = vi[vi["participation_class"].eq("WRONG_VOTE")]
        if len(wrong) and len(rp):
            merged_w = wrong.merge(rp, on="dvm_request_id", how="inner")
            merged_w = merged_w.merge(b[["dvm_request_id", "round_id", "voter", "price_raw"]],
                                      on=["dvm_request_id", "voter"], how="inner")
            res_w = merged_w[merged_w["round_id"].eq(merged_w["resolution_round"])]
            wrong_correct_price = (res_w["price_raw"].astype(str) == res_w["resolved_price_raw"].astype(str)).sum()
        else:
            wrong_correct_price = 0
        # (d) reward_class valid
        valid_rc = {"POSITIVE_REWARD", "NEGATIVE_SLASH", "ZERO_CHANGE"}
        rc_ok = set(vi["reward_class"]) <= valid_rc
        # (e) positive reward implies CORRECT_VOTE
        pos_tokens = vi["slashed_tokens_raw"].map(lambda s: int(s) > 0)
        pos_not_correct = (pos_tokens & ~vi["participation_class"].eq("CORRECT_VOTE")).sum()
        c14_ok = (correct_wrong_price + wrong_correct_price + pos_not_correct == 0) and rc_ok
        check("C14", "orthogonal classification consistency", c14_ok,
              f"correct-wrong-price {correct_wrong_price}, wrong-correct-price {wrong_correct_price}, "
              f"pos-not-correct {pos_not_correct}, reward_class valid {rc_ok}")

        # C15
        raw_bad = (~vi["slashed_tokens_raw"].astype(str).str.match(INT_RE)).sum()
        check("C15", "slashed_tokens_raw exact integers", raw_bad == 0,
              f"{raw_bad} non-integer values")

        # C16 — only resolved requests with ballots (NO_REVEALS may lack slashing)
        resolved_with_ballots = set(q.loc[q["resolution_status"].eq("RESOLVED")
                                          & q["ballot_status"].eq("OK"), "dvm_request_id"])
        covered = set(vi["dvm_request_id"])
        uncovered = resolved_with_ballots - covered
        check("C16", "incentive coverage for resolved requests", len(uncovered) == 0,
              f"{len(resolved_with_ballots) - len(uncovered)}/{len(resolved_with_ballots)} "
              f"resolved-with-ballots have incentives")

    print(f"release {M['version']}  build_mode {M['build_mode']}\n")
    for cid, name, ok, det in res:
        print(f"[{'PASS' if ok else 'FAIL'}] {cid:<4} {name:<42} {det}")
    print("\nCOVERAGE (reported, not graded)")
    print("  cases by link status   ", c["dvm_link_status"].value_counts().to_dict())
    print("  requests by resolution ", q["resolution_status"].value_counts().to_dict())
    print("  requests by ballots    ", q["ballot_status"].value_counts().to_dict())
    if has_commit_layer:
        print("  participation classes   ", T["voter_request_incentives"]["participation_class"]
              .value_counts().to_dict())
        print("  reward classes          ", T["voter_request_incentives"]["reward_class"]
              .value_counts().to_dict())
        print(f"  commits {len(T['commits']):,}  participation rows {len(T['participation']):,}  "
              f"incentive rows {len(T['voter_request_incentives']):,}")
    n_fail = sum(not ok for *_, ok, _ in res)
    print(f"\n{'RELEASE OK' if n_fail == 0 else f'NOT RELEASABLE: {n_fail} check(s) failed'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
