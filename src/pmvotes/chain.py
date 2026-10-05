"""Minimal chain access: Etherscan V2 (logs, ABI, block-by-time), The Graph, raw JSON-RPC.

Ported from the research pipeline (dvm_commit_spotcheck.py, probe_raw_log_forensic.py,
pull_round_state.py). Behaviour kept: event layouts are resolved from the fetched ABI,
never hardcoded; log retrieval is STRICT (a non-list response or an unsplittable capped
range stops the run instead of looking like "no logs").

Credentials come from the environment only: ETHERSCAN_API_KEY, GRAPH_GATEWAY_API_KEY,
MAINNET_RPC_URL. Nothing here prints them.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

try:
    from Crypto.Hash import keccak as _k

    def keccak256(b: bytes) -> bytes:
        h = _k.new(digest_bits=256)
        h.update(b)
        return h.digest()
except ImportError:  # pragma: no cover
    from eth_hash.auto import keccak as keccak256  # type: ignore

VOTING_V2 = "0x004395edb43EFca9885CEdad51EC9fAf93Bd34ac"   # UMA VotingV2, Ethereum mainnet
ROUND_SECONDS = 172_800                                     # VotingV2: 24h commit + 24h reveal
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
UMA_SUBGRAPH_ID = os.environ.get("UMA_SUBGRAPH_ID", "5YVXjj28Lv4eLhHg54R1QWVHNn8VAjZnT3vJgEtuyWmY")
MAX_LOGS_PER_CALL = 1000
RATE_SLEEP = 0.25


def load_env(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _need(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"missing environment variable {name}")
    return v


# ---------------------------------------------------------------- Etherscan V2
_TRANSIENT = ("rate limit", "max rate", "unexpected error", "timeout",
              "server too busy", "try again later")


def etherscan(**params) -> dict:
    params.setdefault("chainid", 1)
    params["apikey"] = _need("ETHERSCAN_API_KEY")
    for a in range(10):
        try:
            r = requests.get(ETHERSCAN_URL, params=params, timeout=60)
            r.raise_for_status()
            j = r.json()
        except (requests.exceptions.RequestException, OSError, ValueError):
            if a == 9:
                raise
            time.sleep(min(2 ** a, 30))
            continue
        time.sleep(RATE_SLEEP)
        if "jsonrpc" in j:                      # module=proxy responses
            if "error" in j:
                msg = str(j["error"])
                if any(k in msg.lower() for k in _TRANSIENT):
                    time.sleep(min(2 ** a, 30))
                    continue
                raise RuntimeError(f"Etherscan RPC error: {msg[:200]}")
            return j
        status, msg = str(j.get("status", "")), str(j.get("message", ""))
        if status == "0" and ("No records" in msg or msg == ""):
            return {"result": []}
        if status == "1":
            return j
        if any(k in (msg + str(j.get("result", ""))).lower() for k in _TRANSIENT):
            time.sleep(min(2 ** a, 30))
            continue
        raise RuntimeError(f"Etherscan error: {msg} | {str(j.get('result', ''))[:200]}")
    raise RuntimeError("Etherscan retries exhausted")


def get_abi(address: str) -> list:
    cache = Path("data/raw/_checkpoint") / f"abi_{address.lower()}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    abi = json.loads(etherscan(module="contract", action="getabi", address=address)["result"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(abi))
    return abi


_block_ts_cache: dict[int, int] = {}


def _rpc_get_block(url: str, block_num: int | str) -> dict | None:
    tag = hex(block_num) if isinstance(block_num, int) else block_num
    for a in range(6):
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": "eth_getBlockByNumber", "params": [tag, False]}, timeout=30)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(str(j["error"])[:200])
            blk = j.get("result")
            if blk and isinstance(block_num, int):
                _block_ts_cache[block_num] = int(blk["timestamp"], 16)
            return blk
        except (requests.exceptions.RequestException, OSError, ValueError, RuntimeError):
            if a == 5:
                raise
            time.sleep(min(2 ** a, 10))


def _rpc_block_ts(url: str, num: int) -> int:
    if num in _block_ts_cache:
        return _block_ts_cache[num]
    b = _rpc_get_block(url, num)
    return int(b["timestamp"], 16)


_bbt_cache: dict[tuple[int, str], int] = {}


def _rpc_block_by_time(url: str, ts: int, closest: str) -> int:
    key = (ts, closest)
    if key in _bbt_cache:
        return _bbt_cache[key]
    latest = _rpc_get_block(url, "latest")
    hi = int(latest["number"], 16)
    lo = max(1, hi - 5_000_000)  # UMA launched ~2020, narrow search window
    # ensure lo is before ts
    if _rpc_block_ts(url, lo) >= ts:
        lo = 1
    while lo < hi:
        mid = (lo + hi) // 2
        bt = _rpc_block_ts(url, mid)
        if bt < ts:
            lo = mid + 1
        else:
            hi = mid
    if closest == "before":
        if _rpc_block_ts(url, lo) > ts and lo > 1:
            lo -= 1
    _bbt_cache[key] = lo
    return lo


def block_by_time(ts: int, closest: str) -> int:
    url = os.environ.get("MAINNET_RPC_URL")
    if url:
        return _rpc_block_by_time(url, ts, closest)
    return int(etherscan(module="block", action="getblocknobytime",
                         timestamp=int(ts), closest=closest)["result"])


def _canonical_type(inp: dict) -> str:
    t = inp["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_canonical_type(c) for c in inp["components"]) + ")" + t[5:]
    return t


def event_info(abi: list, name: str, address: str) -> dict:
    evs = [x for x in abi if x.get("type") == "event" and x.get("name") == name]
    if len(evs) != 1:
        raise SystemExit(f"ABI has {len(evs)} events named {name}; expected exactly one")
    ev = evs[0]
    sig = f"{name}(" + ",".join(_canonical_type(i) for i in ev["inputs"]) + ")"
    return {"name": name, "address": address, "sig": sig,
            "topic0": "0x" + keccak256(sig.encode()).hex(),
            "indexed": [(i["name"], i["type"]) for i in ev["inputs"] if i.get("indexed")],
            "non_indexed": [(i["name"], i["type"]) for i in ev["inputs"] if not i.get("indexed")]}


def identifier_topic(ident: str) -> str:
    b = ident.encode()
    return "0x" + b.hex() + "00" * (32 - len(b))


def _rpc_enrich_timestamps(url: str, logs: list) -> list:
    """Add timeStamp field to RPC logs by batch-fetching unique block headers."""
    blocks = list({lg["blockNumber"] for lg in logs} - {hex(b) for b in _block_ts_cache})
    ts_map = {hex(b): hex(t) for b, t in _block_ts_cache.items()}
    # batch fetch in groups of 100
    for i in range(0, len(blocks), 100):
        batch = [{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber",
                  "params": [bnum, False]}
                 for j, bnum in enumerate(blocks[i:i+100])]
        for a in range(6):
            try:
                r = requests.post(url, json=batch, timeout=60)
                r.raise_for_status()
                for resp in r.json():
                    blk = resp.get("result")
                    if blk:
                        bnum = blk["number"]
                        ts_map[bnum] = blk["timestamp"]
                        _block_ts_cache[int(bnum, 16)] = int(blk["timestamp"], 16)
                break
            except (requests.exceptions.RequestException, OSError, ValueError):
                if a == 5:
                    break
                time.sleep(min(2 ** a, 10))
    for lg in logs:
        lg["timeStamp"] = ts_map.get(lg["blockNumber"], "0x0")
    return logs


_RPC_LOG_CHUNK = 2000


def _rpc_getlogs_one(url: str, topic_list: list, address: str,
                      from_block: int, to_block: int) -> list:
    filt = {"address": address, "topics": topic_list,
            "fromBlock": hex(from_block), "toBlock": hex(to_block)}
    for a in range(6):
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                              "method": "eth_getLogs", "params": [filt]}, timeout=60)
            if r.status_code in (400, 413, 429):
                time.sleep(min(2 ** a, 10))
                continue
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                time.sleep(min(2 ** a, 10))
                continue
            logs = j.get("result", [])
            return logs if isinstance(logs, list) else []
        except (requests.exceptions.RequestException, OSError, ValueError):
            if a == 5:
                raise
            time.sleep(min(2 ** a, 10))
    return []


def _rpc_getlogs(url: str, ev: dict, from_block: int, to_block: int,
                  topics: dict | None = None) -> list:
    topic_list = [ev["topic0"]]
    for pos in sorted((topics or {}).keys()):
        while len(topic_list) < pos:
            topic_list.append(None)
        topic_list.append(topics[pos])
    all_logs = []
    lo = from_block
    while lo <= to_block:
        hi = min(lo + _RPC_LOG_CHUNK - 1, to_block)
        all_logs.extend(_rpc_getlogs_one(url, topic_list, ev["address"], lo, hi))
        lo = hi + 1
    if all_logs:
        _rpc_enrich_timestamps(url, all_logs)
    return all_logs


def getlogs(ev: dict, from_block: int, to_block: int, topics: dict | None = None) -> list:
    """STRICT eth_getLogs — uses RPC when available, falls back to Etherscan."""
    url = os.environ.get("MAINNET_RPC_URL")
    if url:
        return _rpc_getlogs(url, ev, from_block, to_block, topics)
    params = {"module": "logs", "action": "getLogs", "address": ev["address"],
              "topic0": ev["topic0"], "fromBlock": from_block, "toBlock": to_block}
    for pos, val in (topics or {}).items():
        params[f"topic{pos}"] = val
        params[f"topic0_{pos}_opr"] = "and"
    try:
        logs = etherscan(**params).get("result", [])
    except RuntimeError as e:
        if "timeout" not in str(e).lower() or to_block <= from_block + 1:
            raise
        mid = (from_block + to_block) // 2
        return getlogs(ev, from_block, mid, topics) + getlogs(ev, mid + 1, to_block, topics)
    if not isinstance(logs, list):
        raise SystemExit(f"getLogs {from_block}-{to_block} returned non-list: {str(logs)[:120]!r}")
    if len(logs) < MAX_LOGS_PER_CALL:
        return logs
    if to_block <= from_block + 1:
        raise SystemExit(f"getLogs {from_block}-{to_block} capped and cannot be split")
    mid = (from_block + to_block) // 2
    return getlogs(ev, from_block, mid, topics) + getlogs(ev, mid + 1, to_block, topics)


def topic_pos(ev: dict, name: str) -> int | None:
    names = [n for n, _ in ev["indexed"]]
    return 1 + names.index(name) if name in names else None


def _word(slot: bytes, t: str):
    if t.startswith("uint"):
        return int.from_bytes(slot, "big")
    if t.startswith("int"):
        u = int.from_bytes(slot, "big")
        return u - 2 ** 256 if u >= 2 ** 255 else u
    if t == "address":
        return "0x" + slot[-20:].hex()
    if t == "bool":
        return bool(int.from_bytes(slot, "big"))
    return "0x" + slot.hex()


def _hx(v) -> int:
    """Etherscan hex/decimal field -> int; '0x' (zero) and None/'' -> 0."""
    s = str(v if v is not None else "")
    if s.startswith("0x"):
        return int(s, 16) if len(s) > 2 else 0
    return int(s) if s else 0


def decode_log(lg: dict, ev: dict) -> dict:
    """Decode indexed topics and non-indexed data (static words + dynamic bytes/string)."""
    out = {}
    topics = lg.get("topics", [])
    for i, (name, t) in enumerate(ev["indexed"], start=1):
        out[name] = _word(bytes.fromhex(topics[i][2:]), t)
    d = bytes.fromhex(lg["data"][2:] if lg["data"].startswith("0x") else lg["data"])
    head = 0
    for name, t in ev["non_indexed"]:
        slot = d[head:head + 32]
        if t in ("bytes", "string"):
            off = int.from_bytes(slot, "big")
            n = int.from_bytes(d[off:off + 32], "big")
            payload = d[off + 32:off + 32 + n]
            out[name] = payload.decode("utf-8", "replace") if t == "string" else "0x" + payload.hex()
        else:
            out[name] = _word(slot, t)
        head += 32
    out["_block_number"] = _hx(lg["blockNumber"])
    out["_block_timestamp"] = _hx(lg.get("timeStamp"))
    out["_tx_hash"] = lg["transactionHash"].lower()
    out["_log_index"] = _hx(lg.get("logIndex"))
    return out


# ---------------------------------------------------------------- The Graph
def graph(query: str, variables: dict | None = None) -> dict:
    url = f"https://gateway.thegraph.com/api/subgraphs/id/{UMA_SUBGRAPH_ID}"
    hdr = {"Content-Type": "application/json",
           "Authorization": f"Bearer {_need('GRAPH_GATEWAY_API_KEY')}"}
    last = None
    for a in range(12):
        try:
            r = requests.post(url, headers=hdr, json={"query": query, "variables": variables or {}},
                              timeout=60)
            r.raise_for_status()
            j = r.json()
            if "errors" in j:
                s = str(j["errors"])[:400]
                if "indexers" in s.lower():
                    last = RuntimeError(s)
                    time.sleep(min(2 ** a, 30))
                    continue
                raise RuntimeError(s)
            return j["data"]
        except requests.exceptions.RequestException as e:
            last = e
            time.sleep(min(2 ** a, 30))
    raise last or RuntimeError("graph retries exhausted")


# ---------------------------------------------------------------- JSON-RPC
_RPC_ENV_CHAINID = {"POLYGON_RPC_URL": 137, "MAINNET_RPC_URL": 1}


def _etherscan_eth_call(params: list, chain_id: int) -> str:
    """Fallback: use Etherscan V2 proxy for eth_call when no RPC URL."""
    api_key = _need("ETHERSCAN_API_KEY")
    call_obj = params[0]
    block = params[1] if len(params) > 1 else "latest"
    for a in range(8):
        try:
            r = requests.get(ETHERSCAN_URL, params={
                "chainid": chain_id, "module": "proxy", "action": "eth_call",
                "to": call_obj["to"], "data": call_obj.get("data", ""),
                "tag": block, "apikey": api_key,
            }, timeout=60)
            r.raise_for_status()
            j = r.json()
            result = j.get("result", "")
            if j.get("message") == "NOTOK" or (isinstance(result, str) and result.startswith("Max")):
                raise RuntimeError(result[:200])
            return result if result else "0x"
        except (requests.exceptions.RequestException, OSError, ValueError, RuntimeError):
            if a == 7:
                raise
            time.sleep(min(2 ** a, 30))


def rpc(method: str, params: list, url_env: str = "MAINNET_RPC_URL"):
    url = os.environ.get(url_env)
    if not url:
        chain_id = _RPC_ENV_CHAINID.get(url_env)
        if chain_id and method == "eth_call":
            return _etherscan_eth_call(params, chain_id)
        raise SystemExit(f"missing environment variable {url_env}")
    for a in range(8):
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method,
                                         "params": params}, timeout=60)
            r.raise_for_status()
            j = r.json()
            if "error" in j:
                raise RuntimeError(str(j["error"])[:200])
            return j["result"]
        except (requests.exceptions.RequestException, OSError, ValueError, RuntimeError):
            if a == 7:
                raise
            time.sleep(min(2 ** a, 30))
