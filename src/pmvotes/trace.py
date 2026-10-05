"""Trace a Polymarket condition through the full UMA adjudication chain.

    python -m pmvotes.trace <condition_id | oo_request_id | dvm_request_id>
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pandas as pd

from pmvotes import RELEASE


def _load():
    """Load the release parquet files needed for tracing."""
    return (
        pd.read_parquet(RELEASE / "cases.parquet"),
        pd.read_parquet(RELEASE / "dvm_requests.parquet"),
        pd.read_parquet(RELEASE / "ballots.parquet"),
    )


def _ts(val) -> str | None:
    """Unix timestamp to UTC string, or None."""
    if pd.isna(val):
        return None
    return datetime.fromtimestamp(int(val), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _pct(part, total) -> str:
    if total == 0:
        return "0.0%"
    return f"{100 * part / total:.1f}%"


def trace_case(identifier: str) -> dict | None:
    """Trace a Polymarket condition through the adjudication chain.

    Accepts a condition_id (0x...), oo_request_id (YES_OR_NO_QUERY-...),
    or dvm_request_id (YES_OR_NO_QUERY-...).

    Returns a dict with keys: case, dvm_request, rounds, resolution.
    Returns None if the identifier is not found.
    """
    cases, dvm_requests, ballots = _load()

    # --- resolve identifier to a case row
    identifier = identifier.strip()
    if identifier.startswith("0x") or identifier.startswith("0X"):
        identifier = identifier.lower()
        matches = cases[cases["condition_id"] == identifier]
    else:
        # could be oo_request_id or dvm_request_id
        matches = cases[cases["oo_request_id"] == identifier]
        if matches.empty:
            matches = cases[cases["dvm_request_id"] == identifier]
    if matches.empty:
        return None

    # a condition_id can have multiple disputes; sort by sequence
    if len(matches) > 1:
        matches = matches.sort_values("dispute_seq_in_condition")
    case = matches.iloc[0]
    n_disputes = len(matches)

    cond_id = case["condition_id"] if pd.notna(case["condition_id"]) else None
    result = {
        "case": {
            "condition_id": cond_id,
            "oo_request_id": case["oo_request_id"],
            "oo_contract": case["oo_contract"],
            "architecture": case["architecture"],
            "proposed_price_class": case.get("proposed_uma_value_class"),
            "proposal_time": _ts(case["proposal_timestamp"]),
            "dispute_time": _ts(case["dispute_timestamp"]),
            "dvm_link_status": case["dvm_link_status"],
            "dvm_request_id": case.get("dvm_request_id"),
            "n_disputes_in_condition": n_disputes,
        },
    }

    dvm_id = case.get("dvm_request_id")
    if pd.isna(dvm_id) or dvm_id is None:
        result["dvm_request"] = None
        result["rounds"] = []
        result["resolution"] = None
        return result

    # --- DVM request
    dvm_row = dvm_requests[dvm_requests["dvm_request_id"] == dvm_id]
    if dvm_row.empty:
        result["dvm_request"] = None
        result["rounds"] = []
        result["resolution"] = None
        return result
    dvm = dvm_row.iloc[0]

    result["dvm_request"] = {
        "dvm_request_id": dvm["dvm_request_id"],
        "request_time": _ts(dvm["request_time"]),
        "resolution_status": dvm["resolution_status"],
        "resolved_price_class": dvm.get("resolved_uma_value_class"),
        "resolution_tx": dvm.get("resolution_tx"),
        "n_ballots": int(dvm["n_ballots"]),
        "n_voters": int(dvm["n_voters"]) if pd.notna(dvm["n_voters"]) else 0,
        "n_rounds": int(dvm["n_rounds"]) if pd.notna(dvm["n_rounds"]) else 0,
    }

    # --- rounds with ballot summaries
    req_ballots = ballots[ballots["dvm_request_id"] == dvm_id]
    round_ids = sorted(req_ballots["round_id"].unique())
    round_details = []
    for rid in round_ids:
        rb = req_ballots[req_ballots["round_id"] == rid]
        weights = rb["num_tokens_raw"].map(int)
        total_weight = weights.sum()
        by_class = rb.assign(w=weights).groupby("uma_value_class")["w"].sum()
        weight_pcts = {cls: _pct(w, total_weight) for cls, w in by_class.items()}
        is_res = rb["is_resolution_round"].iloc[0]
        round_details.append({
            "round_id": int(rid),
            "n_ballots": len(rb),
            "is_resolution_round": bool(is_res) if pd.notna(is_res) else None,
            "weight_by_class": weight_pcts,
        })
    result["rounds"] = round_details

    # --- resolution
    if dvm["resolution_status"] == "RESOLVED":
        result["resolution"] = {
            "price_class": dvm.get("resolved_uma_value_class"),
            "adapter_effect": dvm.get("resolved_adapter_effect"),
            "tx": dvm.get("resolution_tx"),
        }
    else:
        result["resolution"] = {"status": dvm["resolution_status"]}

    return result


def format_trace(result: dict) -> str:
    """Format a trace result as a human-readable tree."""
    if result is None:
        return "Not found."

    lines = []
    c = result["case"]
    if c["condition_id"]:
        lines.append(f"Polymarket condition {c['condition_id']}")
    else:
        lines.append(f"Polymarket case {_abbrev(c['oo_request_id'])}")
    n_disp = c.get("n_disputes_in_condition", 1)
    if n_disp > 1:
        lines.append(f"  ({n_disp} disputes on this condition; showing seq 1)")
    lines.append(f"  {c['oo_contract']} request  ({c['architecture']})")
    pp = c['proposed_price_class'] or "?"
    lines.append(f"    proposed {c['proposal_time']}  price={pp}")
    lines.append(f"    disputed {c['dispute_time']}")

    dvm = result.get("dvm_request")
    if dvm is None:
        lines.append(f"  DVM link: {c['dvm_link_status']} (no DVM request)")
        return "\n".join(lines)

    lines.append("    |")
    lines.append(f"  VotingV2 request {_abbrev(dvm['dvm_request_id'])}")
    lines.append(f"    request_time {dvm['request_time']}  "
                 f"{dvm['n_ballots']} ballots across {dvm['n_rounds']} round(s)")

    for rd in result["rounds"]:
        lines.append("    |")
        res_tag = "  ** resolution round **" if rd["is_resolution_round"] else ""
        lines.append(f"  Round {rd['round_id']}{res_tag}")
        wt = "  ".join(f"{cls}={pct}" for cls, pct in rd["weight_by_class"].items())
        lines.append(f"    {rd['n_ballots']} ballots  weight: {wt}")

    res = result.get("resolution")
    if res and "price_class" in res:
        lines.append("    |")
        tx = str(res["tx"]) if pd.notna(res.get("tx")) else ""
        tx_short = tx[:10] + "..." if len(tx) > 10 else tx
        lines.append(f"  Resolved: {res['price_class']} ({res['adapter_effect']})  tx={tx_short}")
    elif res:
        lines.append(f"  Status: {res.get('status', 'unknown')}")

    return "\n".join(lines)


def _abbrev(s: str | None, max_len: int = 60) -> str:
    """Abbreviate long request IDs for display."""
    if s is None:
        return "(none)"
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pmvotes.trace <condition_id | oo_request_id | dvm_request_id>")
        sys.exit(1)
    identifier = sys.argv[1]
    result = trace_case(identifier)
    print(format_trace(result))
    sys.exit(0 if result is not None else 1)
