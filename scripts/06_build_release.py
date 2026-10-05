"""06 -- build the four release tables and the manifest from data/raw.

    cases.parquet         one row per disputed OO attempt on a Polymarket binary adapter
    dvm_requests.parquet  one row per DVM request exactly linked to a case
    rounds.parquet        one row per VotingV2 round holding a linked ballot
    ballots.parquet       one row per VoteRevealed event for a linked request

No row is dropped for being inconvenient: every case stays, with dvm_link_status; every linked
request stays, with resolution_status and ballot_status. Raw integers are decimal strings.

    python scripts/06_build_release.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pmvotes import RAW, RELEASE
from pmvotes.chain import ROUND_SECONDS, VOTING_V2
from pmvotes.semantics import classify

VERSION = "1.0.0"


def _cls(series: pd.Series, prefix: str) -> pd.DataFrame:
    c = series.map(lambda p: classify(p) if pd.notna(p) and str(p) not in ("", "None", "nan")
                   else (None, None, None))
    return pd.DataFrame(c.tolist(), index=series.index,
                        columns=[f"{prefix}uma_value_class", f"{prefix}ctf_payout",
                                 f"{prefix}adapter_effect"])


def _text(h) -> str | None:
    try:
        return bytes.fromhex(str(h).removeprefix("0x")).decode("utf-8", "replace")
    except ValueError:
        return None


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    oo = pd.read_parquet(RAW / "oo_disputes.parquet")
    dvm = pd.read_parquet(RAW / "dvm_requests.parquet")
    links = pd.read_parquet(RAW / "links.parquet")
    rv = pd.read_parquet(RAW / "vote_revealed.parquet")
    res = pd.read_parquet(RAW / "request_resolved.parquet")
    rs = pd.read_parquet(RAW / "round_state.parquet")
    legacy = "resolution_source" in res.columns and res["resolution_source"].eq("LEGACY_SNAPSHOT").all()

    # ---------------------------------------------------------------- cases
    cases = oo.merge(links, on="oo_request_id", how="left", validate="1:1")
    cases["dvm_link_status"] = cases.pop("link_status").fillna("NOT_ATTEMPTED")
    votingv2_start = int(dvm["request_time"].min())
    pre_v2 = (cases["dvm_link_status"].eq("DVM_NOT_FOUND")
              & pd.to_numeric(cases["proposal_timestamp"]).lt(votingv2_start))
    cases.loc[pre_v2, "dvm_link_status"] = "PRE_VOTING_V2"
    cases["dvm_link_format"] = cases.pop("link_format")
    cases["ancillary_text"] = cases["ancillary_hex"].map(_text)
    cases = pd.concat([cases, _cls(cases["proposed_price_raw"], "proposed_")], axis=1)
    cases = cases[[
        "oo_request_id", "oo_contract", "adapter_address", "architecture", "adapter_version",
        "condition_id", "condition_id_status", "question_id", "dispute_seq_in_condition",
        "ancillary_hex", "ancillary_text", "request_timestamp",
        "proposer", "proposed_price_raw", "proposed_uma_value_class", "proposal_timestamp",
        "proposal_tx", "disputer", "dispute_timestamp", "dispute_tx", "bond_raw",
        "dvm_link_status", "dvm_link_format", "dvm_request_id"]]

    # ---------------------------------------------------------------- ballots
    linked = cases.loc[cases["dvm_link_status"].eq("DVM_EXACT"),
                       ["dvm_request_id", "oo_request_id", "condition_id"]]
    rv = rv[rv["dvm_request_id"].isin(linked["dvm_request_id"])].copy()
    if "block_number" in res.columns and res["block_number"].notna().any():
        res = res.sort_values(["block_number", "log_index"])
    if res["dvm_request_id"].duplicated().any():
        raise SystemExit("more than one resolution for a DVM request")
    res_round = res.set_index("dvm_request_id")["round_id"]
    ballots = rv.merge(linked[["dvm_request_id", "condition_id"]], on="dvm_request_id", how="left")
    ballots = pd.concat([ballots, _cls(ballots["price_raw"], "")], axis=1)
    ballots["is_resolution_round"] = ballots["round_id"].eq(
        ballots["dvm_request_id"].map(res_round)).where(
        ballots["dvm_request_id"].isin(res_round.index)).astype("boolean")
    ballots = ballots[[
        "dvm_request_id", "round_id", "condition_id", "voter", "caller",
        "price_raw", "uma_value_class", "ctf_payout", "adapter_effect", "num_tokens_raw",
        "is_resolution_round", "block_number", "block_timestamp", "tx_hash", "log_index"]] \
        .sort_values(["dvm_request_id", "round_id", "block_timestamp", "voter"]).reset_index(drop=True)

    # ---------------------------------------------------------------- dvm_requests
    req = linked.merge(dvm, on="dvm_request_id", how="left", validate="1:1")
    r1 = res[["dvm_request_id", "round_id", "resolved_price_raw", "tx_hash"]]
    r1 = r1.rename(columns={"round_id": "resolution_round", "tx_hash": "resolution_tx"})
    req = req.merge(r1, on="dvm_request_id", how="left")
    req["resolution_source"] = ("LEGACY_SNAPSHOT" if legacy else "VotingV2.RequestResolved")
    req.loc[req["resolved_price_raw"].isna(), "resolution_source"] = None
    agg = ballots.assign(w=ballots["num_tokens_raw"].map(int)).groupby("dvm_request_id").agg(
        n_ballots=("voter", "size"), n_voters=("voter", "nunique"), n_rounds=("round_id", "nunique"),
        revealed_weight=("w", "sum"), first_reveal_ts=("block_timestamp", "min"),
        last_reveal_ts=("block_timestamp", "max"))
    agg["revealed_weight_raw"] = agg.pop("revealed_weight").map(str)
    req = req.merge(agg, left_on="dvm_request_id", right_index=True, how="left")
    req["n_ballots"] = req["n_ballots"].fillna(0).astype(int)
    req["ballot_status"] = req["n_ballots"].gt(0).map({True: "OK", False: "NO_REVEALS"})

    def _status(r):
        if pd.notna(r["resolved_price_raw"]):
            return "RESOLVED"
        flag = str(r["is_resolved"]).lower()
        if flag == "true":
            return "RESOLVED_PRICE_MISSING"     # DVM says resolved; price not in our source
        if flag == "false":
            return "UNRESOLVED_AT_SOURCE"
        return "STATUS_UNKNOWN"
    req["resolution_status"] = req.apply(_status, axis=1)
    req = pd.concat([req, _cls(req["resolved_price_raw"], "resolved_")], axis=1)
    req["first_round"] = req["latest_round"] - req["roll_count"]
    req["resolution_round"] = req["resolution_round"].astype("Int64")
    req = req[[
        "dvm_request_id", "oo_request_id", "condition_id", "request_time", "ancillary_hex",
        "roll_count", "first_round", "latest_round",
        "resolution_status", "resolution_round", "resolved_price_raw", "resolved_uma_value_class",
        "resolved_ctf_payout", "resolved_adapter_effect", "resolution_source", "resolution_tx",
        "ballot_status", "n_ballots", "n_voters", "n_rounds", "revealed_weight_raw",
        "first_reveal_ts", "last_reveal_ts"]]

    # ---------------------------------------------------------------- rounds
    used = sorted(set(ballots["round_id"]))
    rounds = rs[rs["round_id"].isin(used)].copy()
    for c in ("minParticipationRequirement", "minAgreementRequirement", "cumulativeStakeAtRound"):
        rounds[c] = rounds[c].map(lambda v: str(int(v)))
    rounds = rounds.rename(columns={
        "minParticipationRequirement": "min_participation_raw",
        "minAgreementRequirement": "min_agreement_raw",
        "cumulativeStakeAtRound": "cumulative_stake_raw",
        "numberOfRequestsToVote": "n_requests_to_vote", "slashingLibrary": "slashing_library",
        "read_at_block": "state_read_block"})
    rounds["round_start_ts"] = rounds["round_id"] * ROUND_SECONDS
    rounds["reveal_start_ts"] = rounds["round_start_ts"] + ROUND_SECONDS // 2
    rounds["round_end_ts"] = rounds["round_start_ts"] + ROUND_SECONDS
    rounds["n_linked_requests"] = rounds["round_id"].map(
        ballots.groupby("round_id")["dvm_request_id"].nunique())
    rounds = rounds[["round_id", "round_start_ts", "reveal_start_ts", "round_end_ts",
                     "cumulative_stake_raw", "min_participation_raw", "min_agreement_raw",
                     "n_requests_to_vote", "slashing_library", "state_read_block",
                     "n_linked_requests"]].sort_values("round_id").reset_index(drop=True)

    # ---------------------------------------------------------------- write
    RELEASE.mkdir(parents=True, exist_ok=True)
    tables = {"cases": cases, "dvm_requests": req, "rounds": rounds, "ballots": ballots}
    for k, df in tables.items():
        df.to_parquet(RELEASE / f"{k}.parquet", index=False)
    manifest = {
        "dataset": "polymarket-uma-adjudication",
        "version": VERSION,
        "build_mode": "LEGACY_IMPORT" if legacy else "CHAIN",
        "built_utc": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "rows": {k: int(len(v)) for k, v in tables.items()},
        "counts": {
            "cases_by_link_status": cases["dvm_link_status"].value_counts().to_dict(),
            "cases_by_oo_contract": cases["oo_contract"].value_counts().to_dict(),
            "linked_conditions": int(req["condition_id"].nunique()),
            "requests_by_resolution_status": req["resolution_status"].value_counts().to_dict(),
            "requests_by_resolved_value_class":
                req["resolved_uma_value_class"].value_counts().to_dict(),
            "ballots_by_value_class": ballots["uma_value_class"].value_counts().to_dict(),
            "distinct_voter_addresses": int(ballots["voter"].nunique()),
            "rounds": int(len(rounds)),
        },
        "coverage": {
            "first_dispute_ts": int(pd.to_numeric(cases["dispute_timestamp"]).min()),
            "last_dispute_ts": int(pd.to_numeric(cases["dispute_timestamp"]).max()),
            "first_round": int(rounds["round_id"].min()),
            "last_round": int(rounds["round_id"].max()),
            "last_ballot_block": int(ballots["block_number"].max()),
            "last_ballot_ts": int(ballots["block_timestamp"].max()),
        },
        "contracts": {
            "voting_v2": VOTING_V2,
            "voting_v2_chain": "ethereum",
            "oo_chain": "polygon",
        },
        "cursor": {
            "last_dispute_ts": int(pd.to_numeric(cases["dispute_timestamp"]).max()),
            "last_ethereum_block": int(ballots["block_number"].max()),
            "last_round_id": int(rounds["round_id"].max()),
        },
        "sha256": {f"{k}.parquet": sha256(RELEASE / f"{k}.parquet") for k in tables},
    }
    (RELEASE / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps(manifest["rows"]), json.dumps(manifest["counts"], default=str)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
