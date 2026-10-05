"""Adversarial stratified audit for v1.0.0.

Samples 30 cases by stratum (fixed seed), then verifies each case against raw
on-chain data by decoding VoteRevealed and RequestResolved event fields from
tx receipts. Field-level comparison per ballot: voter, price, numTokens, roundId,
block, identifier, time, ancillaryData. Per resolution: price, roundId, identifier.

    python scripts/audit_v1.py
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone

import pandas as pd

from pmvotes import RAW, RELEASE, ROOT
from pmvotes.chain import (VOTING_V2, decode_log, event_info, get_abi,
                           identifier_topic, load_env, rpc)

SEED = 20261004
YES_OR_NO_QUERY_IDENTIFIER = identifier_topic("YES_OR_NO_QUERY")


def _norm_hex(s: str) -> str:
    s = str(s).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return s


def load_release():
    return {k: pd.read_parquet(RELEASE / f"{k}.parquet")
            for k in ("cases", "dvm_requests", "rounds", "ballots")}


def get_tx_receipt(tx_hash: str) -> dict:
    return rpc("eth_getTransactionReceipt", [tx_hash])


def decode_reveal_from_receipt(receipt: dict, log_index: int, ev_rev: dict) -> dict | None:
    v2 = VOTING_V2.lower()
    topic0 = ev_rev["topic0"].lower()
    for lg in receipt.get("logs", []):
        topics = lg.get("topics", [])
        if (topics
                and int(lg["logIndex"], 16) == log_index
                and lg["address"].lower() == v2
                and topics[0].lower() == topic0):
            return decode_log(lg, ev_rev)
    return None


def decode_resolved_from_receipt(receipt: dict, ev_res: dict,
                                  request_time: int,
                                  ancillary_hex: str,
                                  expected_ident: str) -> dict | None:
    v2 = VOTING_V2.lower()
    topic0 = ev_res["topic0"].lower()
    anc_norm = _norm_hex(ancillary_hex)
    ident_norm = _norm_hex(expected_ident)
    for lg in receipt.get("logs", []):
        topics = lg.get("topics", [])
        if not topics:
            continue
        if lg["address"].lower() == v2 and topics[0].lower() == topic0:
            decoded = decode_log(lg, ev_res)
            if int(decoded["time"]) != request_time:
                continue
            chain_anc = _norm_hex(decoded.get("ancillaryData", ""))
            chain_ident = _norm_hex(decoded.get("identifier", ""))
            if chain_anc == anc_norm and chain_ident == ident_norm:
                return decoded
    return None


def sample_cases(T: dict, seed: int = SEED) -> tuple[list[dict], pd.DataFrame]:
    c, q = T["cases"], T["dvm_requests"]
    cq = c.merge(q, on="dvm_request_id", how="left", suffixes=("", "_dvm"))
    rng = random.Random(seed)
    picks = []
    taken = set()

    def pick(mask, n, stratum):
        pool = cq[mask].index.tolist()
        rng.shuffle(pool)
        added = 0
        for idx in pool:
            if added >= n:
                break
            oid = cq.at[idx, "oo_request_id"]
            if oid in taken:
                continue
            taken.add(oid)
            picks.append({"idx": idx, "stratum": stratum})
            added += 1
        if added < n:
            print(f"  WARNING: stratum '{stratum}' got {added}/{n} picks (pool exhausted)")

    m = (cq["oo_contract"] == "OOV2") & (cq["dvm_link_status"] == "DVM_EXACT") & (cq["roll_count"] == 0)
    pick(m, 5, "oov2_single_round")

    m = (cq["oo_contract"] == "MANAGED_OOV2") & (cq["dvm_link_status"] == "DVM_EXACT") & (cq["roll_count"] == 0)
    pick(m, 5, "managed_single_round")

    m = (cq["dvm_link_status"] == "DVM_EXACT") & (cq["roll_count"] > 0)
    pick(m, 5, "rolled_multi_round")

    m = (cq["dvm_link_status"] == "DVM_EXACT") & (cq["resolved_uma_value_class"] == "P4_TOO_EARLY")
    pick(m, 4, "p4_too_early")

    cond_counts = cq.loc[cq["dvm_link_status"] == "DVM_EXACT"].groupby("condition_id").size()
    multi_conds = cond_counts[cond_counts > 1].index
    m = (cq["dvm_link_status"] == "DVM_EXACT") & cq["condition_id"].isin(multi_conds)
    pick(m, 4, "multi_request_condition")

    managed_times = pd.to_numeric(cq.loc[cq["oo_contract"] == "MANAGED_OOV2", "dispute_timestamp"])
    if len(managed_times):
        boundary = managed_times.min()
        m = (cq["dvm_link_status"] == "DVM_EXACT") & (
            pd.to_numeric(cq["dispute_timestamp"]).between(boundary - 604800, boundary + 604800))
        pick(m, 3, "regime_boundary")

    m = (cq["dvm_link_status"] == "DVM_EXACT") & (cq["n_ballots"] > 1000)
    pick(m, 1, "high_ballot_count")

    # Lowest-ballot DVM_EXACT case
    exact = cq[cq["dvm_link_status"] == "DVM_EXACT"]
    if len(exact):
        lowest_idx = exact["n_ballots"].astype(int).nsmallest(20).index.tolist()
        rng.shuffle(lowest_idx)
        added = 0
        for idx in lowest_idx:
            if added >= 1:
                break
            oid = cq.at[idx, "oo_request_id"]
            if oid in taken:
                continue
            taken.add(oid)
            picks.append({"idx": idx, "stratum": "low_ballot_count"})
            added += 1

    m = cq["dvm_link_status"] == "PRE_VOTING_V2"
    pick(m, min(3, int(m.sum())), "pre_voting_v2")

    return picks, cq


def audit_case(case_row, T: dict, stratum: str, ev_rev: dict, ev_res: dict,
               votingv2_start_ts: int) -> dict:
    oid = case_row["oo_request_id"]
    result = {
        "oo_request_id": oid,
        "stratum": stratum,
        "oo_contract": case_row["oo_contract"],
        "architecture": case_row["architecture"],
        "dvm_link_status": case_row["dvm_link_status"],
        "ballot_checks": [],
        "resolution_check": None,
        "round_count_check": None,
        "mismatches": [],
        "status": "PASS",
    }

    if case_row["dvm_link_status"] == "PRE_VOTING_V2":
        disp_ts = int(pd.to_numeric(case_row["dispute_timestamp"]))
        if disp_ts >= votingv2_start_ts:
            result["status"] = "FAIL"
            result["note"] = (f"PRE_VOTING_V2 FAIL: dispute ts={disp_ts} "
                              f">= votingv2 start={votingv2_start_ts}")
            result["mismatches"].append(
                f"PRE_VOTING_V2 but dispute_timestamp {disp_ts} >= votingv2 start {votingv2_start_ts}")
        else:
            result["note"] = (f"Pre-VotingV2 dispute (ts={disp_ts}, "
                              f"before VotingV2 start={votingv2_start_ts})")
        b = T["ballots"]
        if len(b[b["dvm_request_id"] == case_row.get("dvm_request_id", "___")]):
            result["status"] = "FAIL"
            result["mismatches"].append("PRE_VOTING_V2 case has ballots in release")
        return result

    dvm_id = case_row["dvm_request_id"]
    q = T["dvm_requests"]
    dvm_row = q[q["dvm_request_id"] == dvm_id].iloc[0]
    b = T["ballots"]
    ballots = b[b["dvm_request_id"] == dvm_id].sort_values(["round_id", "block_number", "log_index"])

    result["dvm_request_id"] = dvm_id
    result["n_ballots_release"] = len(ballots)
    result["n_rounds"] = int(dvm_row["n_rounds"]) if pd.notna(dvm_row.get("n_rounds")) else 0
    result["roll_count"] = int(dvm_row["roll_count"])
    result["resolved_class"] = str(dvm_row.get("resolved_uma_value_class", ""))
    result["resolved_price_raw"] = str(dvm_row.get("resolved_price_raw", ""))

    req_time = int(dvm_row["request_time"])
    anc_hex = str(dvm_row.get("ancillary_hex", ""))

    rounds_in_ballots = sorted(ballots["round_id"].unique())

    # Cross-check round count
    rel_n_rounds = int(dvm_row["n_rounds"]) if pd.notna(dvm_row.get("n_rounds")) else 0
    rounds_match = len(rounds_in_ballots) == rel_n_rounds
    result["round_count_check"] = {
        "release_rounds": len(rounds_in_ballots),
        "expected_n_rounds": rel_n_rounds,
        "match": rounds_match,
        "round_ids": [int(r) for r in rounds_in_ballots],
    }
    if not rounds_match:
        result["status"] = "FAIL"
        result["mismatches"].append(
            f"round count: ballots have {len(rounds_in_ballots)} rounds vs n_rounds={rel_n_rounds}")

    # Cross-check ballot count
    rel_n_ballots = int(dvm_row["n_ballots"])
    if len(ballots) != rel_n_ballots:
        result["status"] = "FAIL"
        result["mismatches"].append(
            f"ballot count: {len(ballots)} in ballots table vs n_ballots={rel_n_ballots}")

    # -- Ballot field-level verification --
    for rid in rounds_in_ballots:
        rb = ballots[ballots["round_id"] == rid].reset_index(drop=True)
        indices = [0, len(rb) - 1]
        interior = list(range(1, len(rb) - 1))
        if len(interior) > 3:
            rng = random.Random(f"{SEED}-{dvm_id}-{rid}")
            interior = rng.sample(interior, 3)
        indices.extend(interior)
        indices = sorted(set(i for i in indices if 0 <= i < len(rb)))

        for i in indices:
            row = rb.iloc[i]
            tx_hash = row["tx_hash"]
            li = int(row["log_index"])
            check = {"round": int(rid), "ballot_idx": i, "tx": tx_hash,
                     "log_index": li, "fields": {}, "status": "PASS"}
            try:
                receipt = get_tx_receipt(tx_hash)
                if receipt is None:
                    check["status"] = "FAIL"
                    check["note"] = "null receipt"
                    result["status"] = "FAIL"
                    result["mismatches"].append(f"round {rid} idx {i}: null receipt")
                    result["ballot_checks"].append(check)
                    continue

                decoded = decode_reveal_from_receipt(receipt, li, ev_rev)
                if decoded is None:
                    check["status"] = "FAIL"
                    check["note"] = "VoteRevealed log not found at expected index"
                    result["status"] = "FAIL"
                    result["mismatches"].append(f"round {rid} idx {i}: log not found")
                    result["ballot_checks"].append(check)
                    continue

                fields = {}

                # voter
                chain_voter = decoded["voter"].lower()
                rel_voter = row["voter"].lower()
                fields["voter"] = {"chain": chain_voter, "release": rel_voter,
                                   "match": chain_voter == rel_voter}

                # caller
                chain_caller = decoded["caller"].lower()
                rel_caller = row["caller"].lower()
                fields["caller"] = {"chain": chain_caller, "release": rel_caller,
                                    "match": chain_caller == rel_caller}

                # price
                chain_price = str(decoded["price"])
                rel_price = str(row["price_raw"])
                fields["price"] = {"chain": chain_price, "release": rel_price,
                                   "match": chain_price == rel_price}

                # numTokens
                chain_tokens = str(decoded["numTokens"])
                rel_tokens = str(row["num_tokens_raw"])
                fields["numTokens"] = {"chain": chain_tokens, "release": rel_tokens,
                                       "match": chain_tokens == rel_tokens}

                # roundId
                chain_round = int(decoded["roundId"])
                rel_round = int(row["round_id"])
                fields["roundId"] = {"chain": chain_round, "release": rel_round,
                                     "match": chain_round == rel_round}

                # block number
                chain_block = int(receipt["blockNumber"], 16)
                rel_block = int(row["block_number"])
                fields["block"] = {"chain": chain_block, "release": rel_block,
                                   "match": chain_block == rel_block}

                # identifier (bytes32)
                chain_ident = _norm_hex(decoded.get("identifier", ""))
                expected_ident = _norm_hex(YES_OR_NO_QUERY_IDENTIFIER)
                fields["identifier"] = {
                    "chain": chain_ident[:40] + "..." if len(chain_ident) > 40 else chain_ident,
                    "expected": expected_ident[:40] + "...",
                    "match": chain_ident == expected_ident,
                }

                # request identity: time
                chain_time = int(decoded["time"])
                fields["time"] = {"chain": chain_time, "release": req_time,
                                  "match": chain_time == req_time}

                # request identity: ancillaryData
                chain_anc = _norm_hex(decoded.get("ancillaryData", ""))
                rel_anc = _norm_hex(anc_hex)
                fields["ancillaryData"] = {
                    "chain": chain_anc[:40] + "..." if len(chain_anc) > 40 else chain_anc,
                    "release": rel_anc[:40] + "..." if len(rel_anc) > 40 else rel_anc,
                    "match": chain_anc == rel_anc,
                }

                check["fields"] = fields
                mismatched = [k for k, v in fields.items() if not v["match"]]
                if mismatched:
                    check["status"] = "FAIL"
                    check["note"] = f"field mismatch: {', '.join(mismatched)}"
                    result["status"] = "FAIL"
                    result["mismatches"].append(
                        f"round {rid} idx {i}: {', '.join(mismatched)} mismatch")
            except Exception as e:
                check["status"] = "ERROR"
                check["note"] = str(e)[:120]
                result["status"] = "FAIL"
                result["mismatches"].append(f"round {rid} idx {i}: ERROR {str(e)[:80]}")

            result["ballot_checks"].append(check)

    if not result["ballot_checks"]:
        result["status"] = "FAIL"
        result["mismatches"].append("no ballot checks performed for DVM_EXACT case")

    # -- Resolution verification --
    res_tx = dvm_row.get("resolution_tx")
    if pd.notna(res_tx) and str(res_tx) not in ("", "nan", "None"):
        try:
            receipt = get_tx_receipt(str(res_tx))
            if receipt is None:
                result["resolution_check"] = {"status": "FAIL", "note": "null receipt"}
                result["status"] = "FAIL"
            else:
                decoded = decode_resolved_from_receipt(
                    receipt, ev_res, req_time, anc_hex, YES_OR_NO_QUERY_IDENTIFIER)
                if decoded is None:
                    result["resolution_check"] = {"status": "FAIL",
                                                   "note": "RequestResolved not found for identifier+time+ancillary"}
                    result["status"] = "FAIL"
                else:
                    chain_price = str(decoded["price"])
                    rel_price = str(dvm_row["resolved_price_raw"])
                    price_match = chain_price == rel_price

                    chain_rid = int(decoded["roundId"])
                    rel_rid = int(dvm_row["resolution_round"]) if pd.notna(dvm_row.get("resolution_round")) else None
                    if rel_rid is None:
                        round_match = False
                    else:
                        round_match = chain_rid == rel_rid

                    ok = price_match and round_match
                    result["resolution_check"] = {
                        "status": "PASS" if ok else "FAIL",
                        "chain_price": chain_price, "release_price": rel_price,
                        "chain_round": chain_rid,
                        "release_round": rel_rid,
                        "price_match": price_match,
                        "round_match": round_match,
                        "tx": str(res_tx)[:18] + "...",
                    }
                    if not ok:
                        result["status"] = "FAIL"
                        if not price_match:
                            result["mismatches"].append(
                                f"resolution price: chain={chain_price} vs release={rel_price}")
                        if not round_match:
                            result["mismatches"].append(
                                f"resolution round: chain={chain_rid} vs release={rel_rid}")
        except Exception as e:
            result["resolution_check"] = {"status": "ERROR", "note": str(e)[:120]}
            result["status"] = "FAIL"
            result["mismatches"].append(f"resolution: ERROR {str(e)[:80]}")
    else:
        result["resolution_check"] = {"status": "FAIL", "note": "no resolution_tx in release"}
        result["status"] = "FAIL"
        result["mismatches"].append("missing resolution_tx for DVM_EXACT case")

    return result


def generate_report(results: list[dict]) -> str:
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_pre_v2 = sum(1 for r in results if r["stratum"] == "pre_voting_v2")
    n_linked = len(results) - n_pre_v2
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")

    # Count actual field comparisons (only ballots that reached field comparison)
    total_field_comparisons = 0
    total_field_mismatches = 0
    total_ballots_checked = sum(len(r["ballot_checks"]) for r in results)
    total_ballots_pass = 0
    for r in results:
        for bc in r["ballot_checks"]:
            if bc["fields"]:
                total_field_comparisons += len(bc["fields"])
                total_field_mismatches += sum(1 for v in bc["fields"].values() if not v["match"])
                if bc["status"] == "PASS":
                    total_ballots_pass += 1

    total_ballots_fail = total_ballots_checked - total_ballots_pass
    total_resolutions_checked = sum(1 for r in results
                                     if r.get("resolution_check")
                                     and r["resolution_check"]["status"] in ("PASS", "FAIL"))
    total_resolutions_pass = sum(1 for r in results
                                  if r.get("resolution_check") and r["resolution_check"]["status"] == "PASS")
    total_rounds = sum(len(r.get("round_count_check", {}).get("round_ids", []))
                       for r in results if r.get("round_count_check"))

    lines = [
        "# Adversarial on-chain validation audit -- v1.0.0",
        "",
        f"**Date:** {now}",
        f"**Seed:** {SEED}",
        f"**Method:** field-level decoding of on-chain VoteRevealed and RequestResolved events",
        "",
        "## Summary",
        "",
        f"- **{len(results)} cases** across {len(set(r['stratum'] for r in results))} strata",
        f"- **{n_linked} DVM-linked** cases verified, {n_pre_v2} PRE_VOTING_V2",
        f"- **{total_ballots_checked} ballot events** decoded from tx receipts: "
        f"{total_ballots_pass} field-matched, "
        f"{total_ballots_fail} mismatched/error",
        f"- **{total_field_comparisons} field comparisons** across all decoded ballots, "
        f"{total_field_mismatches} mismatched",
        f"- **{total_resolutions_checked} resolution events** verified: "
        f"{total_resolutions_pass} price+round matched",
        f"- **{total_rounds} rounds** across all audited cases "
        f"(cross-checked against n_rounds in dvm_requests)",
        "",
        "Fields compared per ballot (9): `voter`, `caller`, `price` (int256), "
        "`numTokens` (uint256),",
        "`roundId`, `blockNumber`, `identifier` (bytes32), `time` (request identity), "
        "`ancillaryData` (request identity).",
        "Fields compared per resolution: `price` (int256), `roundId`. "
        "Resolution log matched by identifier + time + ancillaryData.",
        "",
    ]

    if n_fail > 0:
        lines.append(f"**{n_fail} FAILURE(S) -- see details below.**")
        lines.append("")

    lines.extend([
        "## Strata",
        "",
        "| stratum | N | intent |",
        "|---|---:|---|",
    ])
    from collections import Counter
    strata = Counter(r["stratum"] for r in results)
    intent_map = {
        "oov2_single_round": "baseline OO -> DVM identity",
        "managed_single_round": "Managed OOV2 linkage",
        "rolled_multi_round": "multi-round ballot coverage",
        "p4_too_early": "int256.min semantic decoding + RESET",
        "multi_request_condition": "request generation not collapsed",
        "regime_boundary": "OOV2 -> Managed transition edge",
        "high_ballot_count": "large ballot set precision",
        "low_ballot_count": "small-N edge case",
        "pre_voting_v2": "version boundary, timestamp verified pre-VotingV2",
    }
    for s, n in strata.most_common():
        lines.append(f"| {s} | {n} | {intent_map.get(s, '')} |")

    lines.extend(["", "## Per-case results", ""])
    for r in results:
        icon = "PASS" if r["status"] == "PASS" else "**FAIL**"
        lines.append(f"### [{icon}] {r['oo_request_id'][:60]}")
        lines.append(f"- stratum: `{r['stratum']}`")
        lines.append(f"- oo_contract: {r['oo_contract']}, architecture: {r['architecture']}")

        if r.get("note"):
            lines.append(f"- {r['note']}")
            lines.append("")
            continue

        lines.append(f"- dvm_request_id: `{r['dvm_request_id'][:60]}`")
        lines.append(f"- resolved: {r.get('resolved_class', '')} "
                     f"(raw={r.get('resolved_price_raw', '')})")
        lines.append(f"- ballots: {r.get('n_ballots_release', 0)}, "
                     f"rounds: {r.get('n_rounds', 0)}, roll_count: {r.get('roll_count', 0)}")

        bc = r["ballot_checks"]
        n_ok = sum(1 for c in bc if c["status"] == "PASS")
        n_fields = sum(len(c.get("fields", {})) for c in bc)
        lines.append(f"- ballot spot-check: **{n_ok}/{len(bc)}** events field-matched "
                     f"({n_fields} fields compared)")

        rcc = r.get("round_count_check")
        if rcc:
            lines.append(f"- round count: {'PASS' if rcc.get('match', True) else 'FAIL'} "
                        f"({rcc['release_rounds']} rounds in ballots, n_rounds={rcc['expected_n_rounds']})")

        rc = r.get("resolution_check")
        if rc:
            lines.append(f"- resolution: {rc['status']} "
                        f"(chain_price={rc.get('chain_price', '?')}, "
                        f"round={rc.get('chain_round', '?')}, tx={rc.get('tx', '?')})")

        if r["mismatches"]:
            for mm in r["mismatches"]:
                lines.append(f"  - MISMATCH: {mm}")
        lines.append("")

    lines.extend(["## Conclusion", ""])
    if n_fail == 0:
        lines.extend([
            f"{len(results)}/{len(results)} audited cases passed.",
            "",
            f"{n_linked} VotingV2 cases were verified against on-chain adjudication records; "
            f"{n_pre_v2} pre-VotingV2 cases were independently confirmed to predate the "
            "VotingV2 deployment boundary.",
            "",
            f"- {total_ballots_pass}/{total_ballots_checked} sampled ballot events matched on all "
            "9 fields (voter, caller, price, numTokens, roundId, block, identifier, time, ancillaryData).",
            f"- {total_field_comparisons} individual field comparisons, {total_field_mismatches} mismatched.",
            f"- {total_resolutions_pass}/{total_resolutions_checked} resolution events matched on "
            "price and roundId (log found by identifier + time + ancillaryData).",
            "",
            "**Audit: PASS**",
            "",
            "This audit is independent of C1-C10 automated validation. It verifies that the",
            "frozen release parquets faithfully reproduce raw on-chain event data, not just that",
            "they are internally consistent.",
        ])
    else:
        lines.append(f"**{n_fail} case(s) FAILED. v1.0.0 tag blocked.**")

    return "\n".join(lines)


def main() -> int:
    load_env(ROOT / ".env")
    T = load_release()
    abi = get_abi(VOTING_V2)
    ev_rev = event_info(abi, "VoteRevealed", VOTING_V2)
    ev_res = event_info(abi, "RequestResolved", VOTING_V2)

    # VotingV2 earliest request_time as PRE_VOTING_V2 boundary
    votingv2_start_ts = int(T["dvm_requests"]["request_time"].min())

    print("Sampling cases...")
    picks, cq = sample_cases(T)
    print(f"Selected {len(picks)} cases across {len(set(p['stratum'] for p in picks))} strata")

    results = []
    for i, p in enumerate(picks, 1):
        row = cq.loc[p["idx"]]
        print(f"  [{i}/{len(picks)}] {p['stratum']}: {row['oo_request_id'][:50]}", flush=True)
        r = audit_case(row, T, p["stratum"], ev_rev, ev_res, votingv2_start_ts)
        n_bc = len(r["ballot_checks"])
        n_ok = sum(1 for c in r["ballot_checks"] if c["status"] == "PASS")
        detail = f"ballots {n_ok}/{n_bc}" if n_bc else ""
        rc = r.get("resolution_check")
        if rc and rc.get("status"):
            detail += f", resolution {rc['status']}"
        print(f"    -> {r['status']}  {detail}", flush=True)
        results.append(r)

    report = generate_report(results)
    out = ROOT / "validation" / "v1.0.0" / "AUDIT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"\nWrote {out}")

    raw_out = ROOT / "validation" / "v1.0.0" / "audit_results.json"
    raw_out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {raw_out}")

    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_error = sum(1 for r in results
                  if any(bc["status"] == "ERROR" for bc in r["ballot_checks"]))
    if n_fail or n_error:
        print(f"\n*** {n_fail} FAILURE(S), {n_error} ERROR(S) -- v1.0.0 tag blocked ***")
        return 1
    print("\nAll cases PASS. v1.0.0 ready to tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
