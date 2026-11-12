"""04b -- VoteCommitted events for every linked DVM request, from raw mainnet logs.

Same architecture as 04_pull_votes.py: per-request, identifier-topic-filtered,
checkpoint-resumable. VoteCommitted has the same indexed fields as VoteRevealed
(voter, caller, identifier) but no price or numTokens — the commit is encrypted.

Multiple VoteCommitted events per (request, round, voter) are possible because
the contract allows re-commits during the commit phase. All events are kept.

Inputs : data/raw/links.parquet, data/raw/dvm_requests.parquet
Outputs: data/raw/vote_committed.parquet
Resumable through data/raw/_checkpoint/commits/*.jsonl.

    python scripts/04b_pull_commits.py
"""
from __future__ import annotations

import json

import pandas as pd

from pmvotes import RAW, ROOT
from pmvotes.chain import (ROUND_SECONDS, VOTING_V2, block_by_time,
                           decode_log, event_info, get_abi, getlogs,
                           identifier_topic, load_env, topic_pos)

CHK = RAW / "_checkpoint" / "commits"
SLACK = 6 * 3600


def parse_rid(rid: str) -> tuple[str, int, str]:
    ident, t, anc = rid.split("-", 2)
    return ident, int(t), anc[2:].lower()


def _key_ok(d: dict, t: int, anc: str) -> bool:
    a = str(d.get("ancillaryData", "")).lower().removeprefix("0x")
    return int(d["time"]) == t and a == anc


def fetch(rid: str, latest_round: int, roll_count: int, ev_com: dict):
    ident, t, anc = parse_rid(rid)
    topics = {}
    p = topic_pos(ev_com, "identifier")
    if p:
        topics[p] = identifier_topic(ident)
    first_round = min(latest_round - roll_count, t // ROUND_SECONDS)
    b0 = block_by_time(first_round * ROUND_SECONDS - SLACK, "after")
    b1 = block_by_time((latest_round + 1) * ROUND_SECONDS + SLACK, "before")
    commits = []
    for lg in getlogs(ev_com, b0, b1, topics):
        d = decode_log(lg, ev_com)
        if not _key_ok(d, t, anc):
            continue
        commits.append({"dvm_request_id": rid, "round_id": int(d["roundId"]),
                        "voter": d["voter"].lower(), "caller": str(d.get("caller", "")).lower(),
                        "block_number": d["_block_number"], "block_timestamp": d["_block_timestamp"],
                        "tx_hash": d["_tx_hash"], "log_index": d["_log_index"]})
    return commits


def main() -> int:
    load_env(ROOT / ".env")
    L = pd.read_parquet(RAW / "links.parquet")
    D = pd.read_parquet(RAW / "dvm_requests.parquet")
    todo = (L[L["link_status"] == "DVM_EXACT"][["dvm_request_id"]]
            .merge(D, on="dvm_request_id", how="left"))
    if todo["latest_round"].isna().any():
        raise SystemExit("linked DVM request without a round in dvm_requests")

    abi = get_abi(VOTING_V2)
    ev_com = event_info(abi, "VoteCommitted", VOTING_V2)

    CHK.mkdir(parents=True, exist_ok=True)
    st_path, cm_path = CHK / "status.jsonl", CHK / "commits.jsonl"
    done = set()
    if st_path.exists():
        for line in st_path.read_text().splitlines():
            if not line:
                continue
            try:
                done.add(json.loads(line)["dvm_request_id"])
            except (json.JSONDecodeError, KeyError):
                pass
    print(f"todo {len(todo)}, already done {len(done)}")
    for i, r in enumerate(todo.itertuples(index=False), 1):
        if r.dvm_request_id in done:
            continue
        try:
            cm = fetch(r.dvm_request_id, int(r.latest_round), int(r.roll_count), ev_com)
            status = "OK" if cm else "NO_COMMITS"
        except Exception as e:
            print(f"  fetch failed {r.dvm_request_id[:40]}: {str(e)[:120]}")
            continue
        with cm_path.open("a") as f:
            f.writelines(json.dumps(x) + "\n" for x in cm)
        with st_path.open("a") as f:
            f.write(json.dumps({"dvm_request_id": r.dvm_request_id, "status": status,
                                "n_commits": len(cm)}) + "\n")
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}", flush=True)

    def _load(path):
        rows = []
        if path.exists():
            for line in path.read_text().splitlines():
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return pd.DataFrame(rows)

    status = _load(st_path)
    if len(status) == 0:
        status = pd.DataFrame(columns=["dvm_request_id", "status", "n_commits"])
    missing = set(todo["dvm_request_id"]) - set(status["dvm_request_id"])
    if missing:
        raise SystemExit(f"{len(missing)} requests not yet fetched; re-run to resume")
    status = status.drop_duplicates("dvm_request_id", keep="last")

    _SCHEMA = {"dvm_request_id": str, "round_id": "int64", "voter": str, "caller": str,
                "block_number": "int64", "block_timestamp": "int64", "tx_hash": str, "log_index": "int64"}
    com = _load(cm_path)
    if len(com):
        com = com.drop_duplicates(["tx_hash", "log_index"])
    else:
        com = pd.DataFrame({c: pd.Series(dtype=t) for c, t in _SCHEMA.items()})
    com.to_parquet(RAW / "vote_committed.parquet", index=False)
    print(f"commits {len(com):,}  status {status['status'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
