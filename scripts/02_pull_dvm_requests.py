"""02 -- every YES_OR_NO_QUERY price request that reached the UMA DVM (VotingV2), from the UMA
voting subgraph. Same query as the research pipeline (34_dvm_membership_audit.py --stage dvm).

Output: data/raw/dvm_requests.parquet
    dvm_request_id   "<identifier>-<time>-0x<ancillary hex>" (subgraph PriceRequest id)
    request_time, ancillary_hex, roll_count, is_resolved, latest_round

    python scripts/02_pull_dvm_requests.py
"""
from __future__ import annotations

import pandas as pd

from pmvotes import RAW, ROOT
from pmvotes.chain import graph, load_env

Q = """query($w: PriceRequest_filter, $n: Int!) {
  rows: priceRequests(where: $w, first: $n, orderBy: id, orderDirection: asc) {
    id time ancillaryData rollCount isResolved
    latestRound { roundId }
  } }"""


def main() -> int:
    load_env(ROOT / ".env")
    rows, last = [], ""
    while True:
        d = graph(Q, {"w": {"identifier": "YES_OR_NO_QUERY", "id_gt": last}, "n": 1000})["rows"]
        rows.extend(d)
        print(f"  {len(rows):,}", end="\r", flush=True)
        if len(d) < 1000:
            break
        last = d[-1]["id"]
    df = pd.DataFrame([{
        "dvm_request_id": r["id"],
        "request_time": int(r["time"]),
        "ancillary_hex": (r.get("ancillaryData") or "").lower().removeprefix("0x"),
        "roll_count": int(r.get("rollCount") or 0),
        "is_resolved": r.get("isResolved"),
        "latest_round": int((r.get("latestRound") or {}).get("roundId") or 0) or None,
    } for r in rows])
    if df["dvm_request_id"].duplicated().any():
        raise SystemExit("duplicate PriceRequest ids from subgraph")
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_parquet(RAW / "dvm_requests.parquet", index=False)
    print(f"\nwrote {len(df):,} DVM requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
