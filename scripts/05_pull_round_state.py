"""05 -- VotingV2 round state for every round that holds a linked ballot.

Ported from Code/governance/pull_round_state.py. `rounds(uint256)` is a mapping read of current
storage, pinned to one block; an archive node is not required. Every member is decoded by its
ABI type; uint256 values are written as decimal strings so no stake or threshold passes
through float.

Inputs : data/raw/vote_revealed.parquet (round ids)
Output : data/raw/round_state.parquet

    python scripts/05_pull_round_state.py
"""
from __future__ import annotations

import re

import pandas as pd

from pmvotes import RAW, ROOT
from pmvotes.chain import VOTING_V2, get_abi, keccak256, load_env, rpc

WANT = {"minparticipationrequirement", "minagreementrequirement", "cumulativestakeatround"}


def decode_word(word: str, ty: str):
    if ty == "address":
        return "0x" + word[-40:]
    if ty == "bool":
        return bool(int(word, 16))
    if re.fullmatch(r"int\d*", ty):
        bits = int(ty[3:] or 256)
        v = int(word, 16)
        return v - (1 << bits) if v >= (1 << (bits - 1)) else v
    if re.fullmatch(r"uint\d*", ty):
        return int(word, 16)
    if re.fullmatch(r"bytes\d+", ty):
        return "0x" + word[:2 * int(ty[5:])]
    raise SystemExit(f"no decoder for ABI type {ty!r}")


def main() -> int:
    load_env(ROOT / ".env")
    rounds = sorted(pd.read_parquet(RAW / "vote_revealed.parquet", columns=["round_id"])
                    ["round_id"].unique().tolist())
    abi = get_abi(VOTING_V2)
    fn = [a for a in abi if a.get("type") == "function" and a.get("name") == "rounds"]
    if len(fn) != 1 or [i["type"] for i in fn[0]["inputs"]] != ["uint256"]:
        raise SystemExit("VotingV2 ABI has no unique rounds(uint256)")
    names, types = [], []
    for o in fn[0]["outputs"]:
        for c in (o.get("components") or [o]):
            names.append(c["name"])
            types.append(c["type"])
    if WANT - {n.lower() for n in names}:
        raise SystemExit(f"rounds() fields {names} lack {WANT}")
    sel = keccak256(b"rounds(uint256)")[:4].hex()
    block = int(rpc("eth_blockNumber", []), 16)
    out = []
    for i, r in enumerate(rounds, 1):
        h = rpc("eth_call", [{"to": VOTING_V2, "data": "0x" + sel + f"{int(r):064x}"}, hex(block)])
        h = h[2:]
        if len(h) != 64 * len(names):
            raise SystemExit(f"rounds({r}) returned {len(h) // 2} bytes")
        rec = {n: decode_word(h[k * 64:(k + 1) * 64], t)
               for k, (n, t) in enumerate(zip(names, types))}
        rec = {k: (str(v) if isinstance(v, int) and not isinstance(v, bool) else v)
               for k, v in rec.items()}
        rec.update(round_id=int(r), read_at_block=block)
        out.append(rec)
        if i % 50 == 0:
            print(f"  {i}/{len(rounds)}")
    pd.DataFrame(out).to_parquet(RAW / "round_state.parquet", index=False)
    print(f"wrote {len(out)} rounds read at block {block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
