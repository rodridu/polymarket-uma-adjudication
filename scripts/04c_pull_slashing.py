"""04c -- VoterSlashed events via two phases.

Phase 1 (receipt-based): For each resolution tx, decode RequestResolved logs to
build a requestIndex → dvm_request_id mapping. Only 459 unique txs for 4,261
resolved requests.  Output: data/raw/request_index_map.parquet.

Phase 2 (global log scan): VoterSlashed events are NOT in resolution txs — they
are emitted during updateTrackers() calls in subsequent rounds.  We scan ALL
VoterSlashed logs from VotingV2 across the full block range, then post-filter
by requestIndex ∈ request_index_map.  Output: data/raw/voter_slashed.parquet.

Inputs : data/raw/request_resolved.parquet
Outputs: data/raw/voter_slashed.parquet, data/raw/request_index_map.parquet
Resumable through data/raw/_checkpoint/slashing/.

    python scripts/04c_pull_slashing.py
"""
from __future__ import annotations

import json
import os
import time

import pandas as pd
import requests

from pmvotes import RAW, ROOT
from pmvotes.chain import (VOTING_V2, decode_log, event_info, get_abi,
                           load_env, rpc)

CHK = RAW / "_checkpoint" / "slashing"
SCAN_CHUNK = 50_000
MIN_CHUNK = 1_000


def _bytes32_to_str(val: str) -> str:
    raw = val[2:] if val.startswith("0x") else val
    return bytes.fromhex(raw).rstrip(b"\x00").decode("utf-8")


def _decode_receipt_logs(receipt: dict, ev_res: dict) -> list:
    res_topic0 = ev_res["topic0"].lower()
    voting_addr = VOTING_V2.lower()
    resolved = []
    for lg in receipt.get("logs", []):
        if lg.get("address", "").lower() != voting_addr:
            continue
        topics = lg.get("topics", [])
        if not topics:
            continue
        if topics[0].lower() == res_topic0:
            resolved.append(decode_log(lg, ev_res))
    return resolved


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


_SPLIT = "SPLIT"
_RATE_LIMIT = "RATE_LIMIT"


def _scan_logs_chunk(url: str, ev: dict, from_block: int, to_block: int) -> list | str:
    """eth_getLogs for a single chunk. Returns list, _SPLIT, or _RATE_LIMIT."""
    topic_list = [ev["topic0"]]
    filt = {"address": ev["address"], "topics": topic_list,
            "fromBlock": hex(from_block), "toBlock": hex(to_block)}
    for a in range(6):
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": "eth_getLogs", "params": [filt]}, timeout=60)
            if r.status_code in (400, 413):
                return _SPLIT
            if r.status_code == 429:
                time.sleep(min(2 ** a, 10))
                continue
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                msg = str(j["error"]).lower()
                if "rate" in msg:
                    time.sleep(min(2 ** a, 10))
                    continue
                if "too many" in msg or "exceed" in msg or "limit" in msg or "range" in msg:
                    return _SPLIT
                time.sleep(min(2 ** a, 10))
                continue
            logs = j.get("result", [])
            return logs if isinstance(logs, list) else []
        except (requests.exceptions.RequestException, OSError, ValueError):
            if a == 5:
                raise
            time.sleep(min(2 ** a, 10))
    raise RuntimeError(f"eth_getLogs exhausted retries for blocks {from_block}-{to_block}")


def _scan_logs(url: str, ev: dict, from_block: int, to_block: int,
               chk_path, sl_path, idx_set: set, idx_to_rid: dict) -> None:
    """Scan VoterSlashed logs, write matches to sl_path per chunk, checkpoint-resumable."""
    done_ranges = set()
    if chk_path.exists():
        for line in chk_path.read_text().splitlines():
            if not line:
                continue
            try:
                d = json.loads(line)
                done_ranges.add((d["from"], d["to"]))
            except (json.JSONDecodeError, KeyError):
                pass

    lo = from_block
    chunk = SCAN_CHUNK
    n_decode_err = 0
    while lo <= to_block:
        hi = min(lo + chunk - 1, to_block)
        if (lo, hi) in done_ranges:
            lo = hi + 1
            continue
        result = _scan_logs_chunk(url, ev, lo, hi)
        if result in (_SPLIT, _RATE_LIMIT):
            if result == _RATE_LIMIT:
                time.sleep(5)
                continue
            if chunk <= MIN_CHUNK:
                raise RuntimeError(f"Cannot shrink chunk below {MIN_CHUNK} at block {lo}")
            chunk = max(chunk // 2, MIN_CHUNK)
            continue
        logs = result
        matched_rows = []
        for lg in logs:
            try:
                d = decode_log(lg, ev)
                req_idx = d["requestIndex"]
            except Exception:
                n_decode_err += 1
                continue
            if req_idx not in idx_set:
                continue
            rid = idx_to_rid.get(req_idx)
            if rid is None:
                continue
            matched_rows.append({"dvm_request_id": rid,
                                 "voter": d["voter"].lower(),
                                 "slashed_tokens_raw": str(d["slashedTokens"]),
                                 "request_index": req_idx,
                                 "block_number": d["_block_number"],
                                 "tx_hash": d["_tx_hash"],
                                 "log_index": d["_log_index"]})

        # write matches BEFORE checkpoint so crash doesn't lose them
        if matched_rows:
            with sl_path.open("a") as f:
                for r in matched_rows:
                    f.write(json.dumps(r) + "\n")
        with chk_path.open("a") as f:
            f.write(json.dumps({"from": lo, "to": hi,
                                "n_total": len(logs), "n_matched": len(matched_rows)}) + "\n")
        if lo % (SCAN_CHUNK * 10) < chunk:
            print(f"  scan block {lo:,}–{hi:,}: {len(logs)} events, {len(matched_rows)} matched",
                  flush=True)
        lo = hi + 1
        chunk = min(chunk * 2, SCAN_CHUNK)

    if n_decode_err:
        print(f"  WARNING: {n_decode_err} decode errors during scan")


def main() -> int:
    load_env(ROOT / ".env")
    rr = pd.read_parquet(RAW / "request_resolved.parquet")
    unique_txs = rr.drop_duplicates("tx_hash")[["tx_hash", "block_number"]].reset_index(drop=True)
    our_ids = set(rr["dvm_request_id"])

    abi = get_abi(VOTING_V2)
    ev_res = event_info(abi, "RequestResolved", VOTING_V2)
    ev_slash = event_info(abi, "VoterSlashed", VOTING_V2)

    CHK.mkdir(parents=True, exist_ok=True)
    st_path = CHK / "status.jsonl"
    idx_path = CHK / "request_index.jsonl"
    scan_chk = CHK / "scan_progress.jsonl"
    sl_path = CHK / "slashed_scan.jsonl"

    # ---- Phase 1: receipt-based request_index_map
    done = set()
    if st_path.exists():
        for line in st_path.read_text().splitlines():
            if not line:
                continue
            try:
                done.add(json.loads(line)["tx_hash"])
            except (json.JSONDecodeError, KeyError):
                pass

    remaining = len(unique_txs) - len(done & set(unique_txs["tx_hash"]))
    print(f"Phase 1 — resolution txs: {len(unique_txs)} unique, {remaining} remaining")

    for i, row in enumerate(unique_txs.itertuples(index=False), 1):
        if row.tx_hash in done:
            continue
        try:
            receipt = rpc("eth_getTransactionReceipt", [row.tx_hash])
            resolved = _decode_receipt_logs(receipt, ev_res)
        except Exception as e:
            print(f"  receipt failed {row.tx_hash[:20]}: {str(e)[:120]}")
            continue

        for d in resolved:
            try:
                ident = _bytes32_to_str(d["identifier"])
                t = d["time"]
                anc_hex = str(d.get("ancillaryData", "")).lower().removeprefix("0x")
                rid_key = f"{ident}-{t}-0x{anc_hex}"
            except (ValueError, UnicodeDecodeError):
                continue
            if rid_key in our_ids:
                req_idx = d["resolvedPriceRequestIndex"]
                with idx_path.open("a") as f:
                    f.write(json.dumps({"request_index": req_idx,
                                        "dvm_request_id": rid_key,
                                        "round_id": d["roundId"],
                                        "tx_hash": d["_tx_hash"]}) + "\n")

        with st_path.open("a") as f:
            f.write(json.dumps({"tx_hash": row.tx_hash,
                                "n_resolved": len(resolved)}) + "\n")
        if i % 25 == 0:
            print(f"  {i}/{len(unique_txs)}", flush=True)

    status = _load(st_path)
    if len(status) == 0:
        status = pd.DataFrame(columns=["tx_hash", "n_resolved"])
    missing_txs = set(unique_txs["tx_hash"]) - set(status["tx_hash"])
    if missing_txs:
        raise SystemExit(f"{len(missing_txs)} txs not yet fetched; re-run to resume")

    _IDX_SCHEMA = {"request_index": "int64", "dvm_request_id": str,
                   "round_id": "int64", "tx_hash": str}
    idx = _load(idx_path)
    if len(idx):
        idx = idx.drop_duplicates(["request_index", "dvm_request_id"])
    else:
        idx = pd.DataFrame({c: pd.Series(dtype=t) for c, t in _IDX_SCHEMA.items()})

    # requestIndex is a global monotonic counter in VotingV2 — must be 1:1
    if len(idx) and idx["request_index"].duplicated().any():
        dupes = idx[idx["request_index"].duplicated(keep=False)]
        raise SystemExit(f"requestIndex not unique:\n{dupes.head(10)}")

    idx.to_parquet(RAW / "request_index_map.parquet", index=False)
    if len(idx) == 0 and len(our_ids) > 0:
        raise SystemExit("Phase 1 produced 0 index mappings — rid_key format may be wrong")
    print(f"Phase 1 done — request_index_map: {len(idx):,}")

    # ---- Phase 2: global VoterSlashed log scan
    idx_set = set(idx["request_index"].astype(int))
    idx_to_rid = dict(zip(idx["request_index"].astype(int), idx["dvm_request_id"]))
    rpc_url = os.environ.get("MAINNET_RPC_URL")
    if not rpc_url:
        raise SystemExit("MAINNET_RPC_URL required for Phase 2 log scan")

    first_block = int(rr["block_number"].min()) - 100_000
    last_block = int(rr["block_number"].max()) + 500_000
    latest_chain = int(rpc("eth_blockNumber", []), 16)
    last_block = min(last_block, latest_chain)
    print(f"Phase 2 — scanning VoterSlashed {first_block:,}–{last_block:,} "
          f"({(last_block - first_block):,} blocks, {len(idx_set)} target indices)")

    _scan_logs(rpc_url, ev_slash, first_block, last_block, scan_chk, sl_path, idx_set, idx_to_rid)

    _SL_SCHEMA = {"dvm_request_id": str, "voter": str, "slashed_tokens_raw": str,
                   "request_index": "int64", "block_number": "int64",
                   "tx_hash": str, "log_index": "int64"}
    all_sl = _load(sl_path)
    if len(all_sl):
        all_sl = all_sl.drop_duplicates(["tx_hash", "log_index"])
    else:
        all_sl = pd.DataFrame({c: pd.Series(dtype=t) for c, t in _SL_SCHEMA.items()})

    all_sl.to_parquet(RAW / "voter_slashed.parquet", index=False)
    print(f"Phase 2 done — voter_slashed: {len(all_sl):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
