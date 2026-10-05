"""01 -- disputed Optimistic Oracle attempts on Polymarket binary adapters.

Input: one or more Polygon OO request-universe parquets (UMA OO subgraph schema: id, identifier,
ancillaryData, time, requester, proposer, proposedPrice, disputer, settlementPrice, bond,
requestTimestamp, proposalTimestamp, disputeTimestamp, settlementTimestamp, *Hash fields),
each tagged with the oracle contract it came from (OOV2 or MANAGED_OOV2).

Output: data/raw/oo_disputes.parquet, one row per disputed OO request whose requester is a
first-party Polymarket binary adapter (registry/adapters.yaml).

condition_id is enrichment, not an admission gate:
  STANDARD  conditionId = keccak(adapter || keccak(ancillary) || uint256(2))
  NEGRISK   requestId = keccak(ancillary) -> NegRiskOperator.questionIds(requestId) -> questionId
            conditionId = keccak(NegRiskAdapter || questionId || uint256(2))   [Polygon RPC]
A condition that cannot be derived keeps condition_id = null and says why in condition_id_status.

    python scripts/01_prepare_oo_disputes.py --oo OOV2=path/a.parquet --oo MANAGED_OOV2=path/b.parquet
"""
from __future__ import annotations

import argparse

import pandas as pd
import yaml

from pmvotes import RAW, ROOT
from pmvotes.chain import keccak256, load_env, rpc

COLS = ["id", "identifier", "ancillaryData", "time", "requester", "proposer", "proposedPrice",
        "disputer", "settlementPrice", "bond", "requestTimestamp", "proposalTimestamp",
        "disputeTimestamp", "settlementTimestamp", "proposalHash", "disputeHash"]


def cond_id(oracle: str, qid: bytes) -> str:
    return "0x" + keccak256(bytes.fromhex(oracle[2:]) + qid + (2).to_bytes(32, "big")).hex()


def polygon_call(to: str, data: str) -> str:
    return rpc("eth_call", [{"to": to, "data": data}, "latest"], url_env="POLYGON_RPC_URL")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oo", action="append", required=True, help="ORACLE_TAG=path.parquet")
    ap.add_argument("--no-negrisk-rpc", action="store_true",
                    help="skip NegRisk condition ids (status NEGRISK_NOT_QUERIED)")
    a = ap.parse_args()
    load_env(ROOT / ".env")
    with open(ROOT / "registry" / "adapters.yaml") as f:
        reg = {a["address"]: a for a in yaml.safe_load(f)["adapters"]}

    frames = []
    for spec in a.oo:
        tag, _, path = spec.partition("=")
        df = pd.read_parquet(path, columns=COLS)
        df["requester"] = df["requester"].astype("string").str.lower()
        df = df[df["requester"].isin(reg.keys())
                & df["disputer"].fillna("").astype(str).ne("")
                & df["identifier"].eq("YES_OR_NO_QUERY")].copy()
        df["oo_contract"] = tag
        frames.append(df)
        print(f"{tag}: {len(df):,} disputed requests on registry adapters")
    D = pd.concat(frames, ignore_index=True)
    if D["id"].duplicated().any():
        raise SystemExit("OO request id appears in more than one input")

    D["architecture"] = D["requester"].map(lambda r: reg[r]["architecture"])
    D["adapter_version"] = D["requester"].map(lambda r: reg[r]["adapter_version"])
    anc = D["ancillaryData"].astype(str).map(lambda s: bytes.fromhex(s[2:]))
    D["question_id"] = None
    D["condition_id"] = None
    D["condition_id_status"] = None

    std = D["architecture"].eq("STANDARD")
    D.loc[std, "question_id"] = ["0x" + keccak256(b).hex() for b in anc[std]]
    D.loc[std, "condition_id"] = [cond_id(r, bytes.fromhex(q[2:]))
                                  for r, q in zip(D.loc[std, "requester"], D.loc[std, "question_id"])]
    D.loc[std, "condition_id_status"] = "STANDARD_CLOSED_FORM"

    sel = keccak256(b"questionIds(bytes32)")[:4].hex()
    for i in D.index[~std]:
        cfg = reg[D.at[i, "requester"]]
        if a.no_negrisk_rpc:
            D.at[i, "condition_id_status"] = "NEGRISK_NOT_QUERIED"
            continue
        if not cfg.get("negrisk_operator"):
            D.at[i, "condition_id_status"] = "OPERATOR_PROVENANCE_UNVERIFIED"
            continue
        rid = keccak256(anc[i]).hex()
        q = polygon_call(cfg["negrisk_operator"], "0x" + sel + rid)
        if not q or q == "0x" or int(q, 16) == 0:
            D.at[i, "condition_id_status"] = "NEGRISK_MAP_ZERO"
            continue
        D.at[i, "question_id"] = q.lower()
        D.at[i, "condition_id"] = cond_id(cfg["negrisk_adapter"], bytes.fromhex(q[2:]))
        D.at[i, "condition_id_status"] = "NEGRISK_OPERATOR_RPC"

    # attempt order within a condition (or within the raw question when condition is unknown)
    key = D["condition_id"].fillna(D["question_id"]).fillna(D["id"])
    D["proposalTimestamp"] = pd.to_numeric(D["proposalTimestamp"]).astype("Int64")
    D = D.sort_values(["proposalTimestamp", "id"])
    D["dispute_seq_in_condition"] = D.groupby(key.loc[D.index]).cumcount() + 1

    out = D.rename(columns={
        "id": "oo_request_id", "ancillaryData": "ancillary_hex", "time": "request_time",
        "requester": "adapter_address", "proposedPrice": "proposed_price_raw",
        "settlementPrice": "oo_settlement_price_raw", "bond": "bond_raw",
        "requestTimestamp": "request_timestamp", "proposalTimestamp": "proposal_timestamp",
        "disputeTimestamp": "dispute_timestamp", "settlementTimestamp": "oo_settlement_timestamp",
        "proposalHash": "proposal_tx", "disputeHash": "dispute_tx"})
    RAW.mkdir(parents=True, exist_ok=True)
    out.to_parquet(RAW / "oo_disputes.parquet", index=False)
    print(f"wrote {len(out):,} rows; condition_id_status: "
          f"{out['condition_id_status'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
