"""04 -- ballot-level VotingV2 records for every linked DVM request, from raw mainnet logs.

Supersedes build_corrected_reveal_shadow_159.py + build_corrected_reveal_bulk.py (same exact
request filter) and adds what a public release needs:
  * full provenance per ballot: block_number, block_timestamp, tx_hash, log_index, caller;
  * reveals from EVERY round the request sat in (rolled requests), not only the resolving round;
  * the protocol's own resolution: VotingV2 RequestResolved, replacing the stale local snapshot.

Exact request filter (unchanged): decoded event fields (identifier, time, ancillaryData) must
equal the DVM request id's three parts. roundId is taken from each event, never assumed.

Inputs : data/raw/links.parquet, data/raw/dvm_requests.parquet
Outputs: data/raw/vote_revealed.parquet, data/raw/request_resolved.parquet,
         data/raw/pull_status.parquet
Resumable through data/raw/_checkpoint/*.jsonl.

    python scripts/04_pull_votes.py
"""
from __future__ import annotations

import json
import time

import pandas as pd

from pmvotes import RAW, ROOT
from pmvotes.chain import (ROUND_SECONDS, VOTING_V2, block_by_time,
                           decode_log, event_info, get_abi, getlogs,
                           identifier_topic, load_env, topic_pos)

CHK = RAW / "_checkpoint"
SLACK = 6 * 3600                  # block-time granularity at window edges
RESOLVE_LOOKAHEAD = 30 * 86400    # RequestResolved is emitted lazily after the round ends


def parse_rid(rid: str) -> tuple[str, int, str]:
    ident, t, anc = rid.split("-", 2)
    return ident, int(t), anc[2:].lower()


def _key_ok(d: dict, t: int, anc: str) -> bool:
    a = str(d.get("ancillaryData", "")).lower().removeprefix("0x")
    return int(d["time"]) == t and a == anc


def fetch(rid: str, latest_round: int, roll_count: int, ev_rev: dict, ev_res: dict):
    ident, t, anc = parse_rid(rid)
    topics = {}
    p = topic_pos(ev_rev, "identifier")
    if p:
        topics[p] = identifier_topic(ident)
    # earliest possible round: the one holding the request time (does not assume rolls are
    # contiguous); events are filtered by exact key, so a wide window costs only calls
    first_round = min(latest_round - roll_count, t // ROUND_SECONDS)
    b0 = block_by_time(first_round * ROUND_SECONDS - SLACK, "after")
    b1 = block_by_time((latest_round + 1) * ROUND_SECONDS + SLACK, "before")
    reveals = []
    for lg in getlogs(ev_rev, b0, b1, topics):
        d = decode_log(lg, ev_rev)
        if not _key_ok(d, t, anc):
            continue
        reveals.append({"dvm_request_id": rid, "round_id": int(d["roundId"]),
                        "voter": d["voter"].lower(), "caller": str(d.get("caller", "")).lower(),
                        "price_raw": str(d["price"]), "num_tokens_raw": str(d["numTokens"]),
                        "block_number": d["_block_number"], "block_timestamp": d["_block_timestamp"],
                        "tx_hash": d["_tx_hash"], "log_index": d["_log_index"]})

    p = topic_pos(ev_res, "identifier")
    topics = {p: identifier_topic(ident)} if p else {}
    r0 = block_by_time((latest_round + 1) * ROUND_SECONDS - SLACK, "after")
    r1 = block_by_time(min((latest_round + 1) * ROUND_SECONDS + RESOLVE_LOOKAHEAD,
                           int(time.time()) - 600), "before")
    resolved = []
    for lg in getlogs(ev_res, r0, r1, topics):
        d = decode_log(lg, ev_res)
        if _key_ok(d, t, anc):
            resolved.append({"dvm_request_id": rid, "round_id": int(d["roundId"]),
                             "resolved_price_raw": str(d["price"]),
                             "block_number": d["_block_number"],
                             "block_timestamp": d["_block_timestamp"],
                             "tx_hash": d["_tx_hash"], "log_index": d["_log_index"]})
    return reveals, resolved


def main() -> int:
    load_env(ROOT / ".env")
    L = pd.read_parquet(RAW / "links.parquet")
    D = pd.read_parquet(RAW / "dvm_requests.parquet")
    todo = (L[L["link_status"] == "DVM_EXACT"][["dvm_request_id"]]
            .merge(D, on="dvm_request_id", how="left"))
    if todo["latest_round"].isna().any():
        raise SystemExit("linked DVM request without a round in dvm_requests")

    abi = get_abi(VOTING_V2)
    ev_rev = event_info(abi, "VoteRevealed", VOTING_V2)
    ev_res = event_info(abi, "RequestResolved", VOTING_V2)

    CHK.mkdir(parents=True, exist_ok=True)
    st_path, rv_path, rs_path = CHK / "status.jsonl", CHK / "reveals.jsonl", CHK / "resolved.jsonl"
    done = set()
    if st_path.exists():
        done = {json.loads(x)["dvm_request_id"] for x in st_path.read_text().splitlines() if x}
    for i, r in enumerate(todo.itertuples(index=False), 1):
        if r.dvm_request_id in done:
            continue
        try:
            rv, rs = fetch(r.dvm_request_id, int(r.latest_round), int(r.roll_count), ev_rev, ev_res)
            status = "OK" if rv else "NO_REVEALS"
        except Exception as e:      # recorded, retried on next run
            print(f"  fetch failed {r.dvm_request_id[:40]}: {str(e)[:120]}")
            continue
        with rv_path.open("a") as f:
            f.writelines(json.dumps(x) + "\n" for x in rv)
        with rs_path.open("a") as f:
            f.writelines(json.dumps(x) + "\n" for x in rs)
        with st_path.open("a") as f:
            f.write(json.dumps({"dvm_request_id": r.dvm_request_id, "status": status,
                                "n_reveals": len(rv), "n_resolved_events": len(rs)}) + "\n")
        if i % 25 == 0:
            print(f"  {i}/{len(todo)}", flush=True)

    status = pd.read_json(st_path, lines=True)
    missing = set(todo["dvm_request_id"]) - set(status["dvm_request_id"])
    if missing:
        raise SystemExit(f"{len(missing)} requests not yet fetched; re-run to resume")
    status = status.drop_duplicates("dvm_request_id", keep="last")
    def _load(path):          # json.loads keeps every value exact; no dtype inference
        rows = [json.loads(x) for x in path.read_text().splitlines() if x] if path.exists() else []
        return pd.DataFrame(rows)
    rev, res = _load(rv_path), _load(rs_path)
    if len(rev):
        rev = rev.drop_duplicates(["tx_hash", "log_index"])
    if len(res):
        res = res.sort_values(["block_number", "log_index"]).drop_duplicates(["tx_hash", "log_index"])
    rev.to_parquet(RAW / "vote_revealed.parquet", index=False)
    res.to_parquet(RAW / "request_resolved.parquet", index=False)
    status.to_parquet(RAW / "pull_status.parquet", index=False)
    print(f"reveals {len(rev):,}  resolved events {len(res):,}  "
          f"status {status['status'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
