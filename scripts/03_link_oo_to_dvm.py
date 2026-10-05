"""03 -- exact link from each disputed OO attempt to the DVM request it generated.

Ported from build_oo_dvm_linkage.py (research pipeline, block 2B). No fuzzy text, no time
tolerance. Two DVM ancillary formats exist, depending on the Polygon->mainnet relay generation:

  FULL  DVM ancillary = raw OO ancillary || ',ooRequester:..,childRequester:..,childChainId:137'
        match: dvm.request_time == oo.proposal_timestamp AND dvm.ancillary startswith oo.ancillary
  HASH  DVM ancillary = 'ancillaryDataHash:<h>,childBlockNumber:..,childOracle:..,...'
        h = keccak(raw OO ancillary || b',ooRequester:' || requester hex, lowercase, no 0x)
        match: dvm.request_time == oo.proposal_timestamp AND 'ancillaryDataHash:<h>' in dvm ancillary

Hard stop if two OO attempts land on the same DVM request.

Inputs : data/raw/oo_disputes.parquet, data/raw/dvm_requests.parquet
Output : data/raw/links.parquet  (one row per OO dispute; link_status in
         DVM_EXACT | DVM_NOT_FOUND | DVM_MULTIPLE_CANDIDATES)
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

from pmvotes import RAW
from pmvotes.chain import keccak256

MARK = "ancillarydatahash:"


def _strip(x: str) -> str:
    x = str(x).strip().lower()
    return x[2:] if x.startswith("0x") else x


def link(oo: pd.DataFrame, dvm: pd.DataFrame) -> pd.DataFrame:
    idx = defaultdict(list)
    for rid, t, anc in zip(dvm["dvm_request_id"], dvm["request_time"], dvm["ancillary_hex"]):
        anc = _strip(anc)
        try:
            ascii_ = bytes.fromhex(anc).decode("utf-8", "ignore").lower()
        except ValueError:
            ascii_ = ""
        idx[int(t)].append((rid, anc, ascii_))

    rows = []
    for oid, pt, anc, req in zip(oo["oo_request_id"], oo["proposal_timestamp"],
                                 oo["ancillary_hex"], oo["adapter_address"]):
        anc = _strip(anc)
        stamped = keccak256(bytes.fromhex(anc) + b",ooRequester:" + _strip(req).encode()).hex()
        full, hsh = [], []
        for rid, danc, dascii in idx.get(int(pt), []) if pd.notna(pt) else []:
            if danc.startswith(anc):
                full.append(rid)
            elif (MARK + stamped) in dascii:
                hsh.append(rid)
        m = full + hsh
        status = "DVM_EXACT" if len(m) == 1 else ("DVM_NOT_FOUND" if not m else "DVM_MULTIPLE_CANDIDATES")
        rows.append({"oo_request_id": oid,
                     "dvm_request_id": m[0] if len(m) == 1 else None,
                     "link_status": status,
                     "link_format": ("FULL" if full else "HASH") if len(m) == 1 else None})
    L = pd.DataFrame(rows)
    ex = L[L["link_status"] == "DVM_EXACT"]
    if ex["dvm_request_id"].duplicated().any():
        raise SystemExit("two OO attempts linked to one DVM request -- linkage is not injective")
    return L


def main() -> int:
    oo = pd.read_parquet(RAW / "oo_disputes.parquet")
    dvm = pd.read_parquet(RAW / "dvm_requests.parquet")
    L = link(oo, dvm)
    L.to_parquet(RAW / "links.parquet", index=False)
    tab = L.merge(oo[["oo_request_id", "oo_contract"]], on="oo_request_id")
    print(pd.crosstab(tab["oo_contract"], tab["link_status"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
