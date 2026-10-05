# Lineage audit (2026-10-01)

Scope: certify what v1 can claim, from the research pipeline as it stood on
2026-10-01. Six questions, each answered from code and artifacts, not from drafts.

## 1. 1,845 linked requests → raw VotingV2 logs → 644,911 reveals

Traceable end to end.

| step | script | output | count |
|---|---|---|---|
| exact OO→DVM link | legacy linker | linkage parquet | 1,850 attempts; 1,845 `DVM_EXACT`, 5 `DVM_NOT_FOUND` |
| reveals, 159 legacy-panel pairs | legacy reveal builder (shadow) | shadow reveals parquet | 254 requests, 62,070 reveals |
| reveals, remaining pairs | legacy reveal builder (bulk) | bulk reveals parquet | 1,591 requests, 582,841 reveals |

Both reveal builders call Etherscan `getLogs` on VotingV2 (`0x004395ed…`) and keep a log only if
its decoded `(roundId, time, ancillaryData)` equals the request. Bulk status: 1,591 success, 0
empty, 0 identity mismatch, 0 fetch failure.

Checks run on 2026-10-01 against the combined 644,911 rows:
- no duplicate `(request, round, voter)`;
- for all 1,605 requests with a resolution price, the revealed-weight mode equals the resolved
  price (smallest winning share 54.6%). This covers the P4 resolutions as well, which the research
  panel's `resolution_match` did not test (it returned `N/A` for non-binary outcomes).
- The ported linker (`scripts/03_link_oo_to_dvm.py`) reproduces all 1,850 legacy link rows exactly:
  same status, same DVM request, same format.

What the legacy pull lacks for a public release:
- per-ballot `tx_hash`, `log_index`, `block_number`, `caller` were never stored;
- only the **resolving** round was read. 52 requests rolled at least once (37 once, 13 twice,
  2 three times), and their earlier-round reveals are absent.
`scripts/04_pull_votes.py` fixes both.

The old 140,392-reveal panel is superseded. The chain showed it under-attributed voters (one
control pair had 6 frozen voters against 262 on chain; `_probe_rpc_reveal_feasibility.txt`).

## 2. 644,911 reveals → 1,619 condition-round panel

`build_governance_panel.py`. The pair key is `(condition_id, resolved round)`. 1,621 frame rows
reduce to 1,619 because two rows were the same request matched under an alternate round
convention (`phantom_map.csv`). 224 pairs carry two requests. The release does **not** use the
pair panel or its `BINARY_DECISION` label (466), which is paper-specific. The release unit is the
DVM request; the pair is derivable as `(condition_id, resolution_round)`.

## 3. Round-state reads

Done. `round_state/round_state.parquet`: 383 rounds, all `valid_state`, read 2026-09-06 at
mainnet block 25,915,074–80. Verify stage passed on the 236 previously covered rounds with zero
mismatch. **Gap:** 6 linked requests (1,145 ballots) sit in 6 rounds that were never read (e.g.
10190, 10060). `scripts/05_pull_round_state.py` reads every round that holds a ballot.

## 4. The 231 requests without a resolution

Not missing on chain. The research panel took the resolution price from a local DVM
snapshot that stops before round 10237. All 231 sit in rounds
10237–10333. The 9 labelled `UNRESOLVED` by that snapshot are also marked resolved by the newer
subgraph pull (`probe_dvm_requests.csv`, 2026-08-11). So all 240 are resolved requests whose price
the snapshot lacks.
Release label: `RESOLVED_PRICE_MISSING` until `04_pull_votes.py` reads `RequestResolved`.

## 5. Coverage misses

**The 5 `DVM_NOT_FOUND`.** Three were disputed between Dec 2022 and Feb 2023, before VotingV2's
first round (9715 starts 2023-03-14). They went to the previous Voting contract. Two were disputed
on 2026-08-12, after the DVM request list was pulled (2026-08-11).

**The 470 of 1,444 (and, more broadly, 1,243 of 2,299 disputed first proposals) missing from
the frame.** The frame is built from `oo_v2_request_universe` only, which is the non-managed
OptimisticOracleV2. Polymarket's v4 adapters (`0x65070be9…` standard, `0x69c47de9…` NegRisk) request
through **Managed OOV2** (`0x2c0367a9…`), whose universe was pulled separately
(`managed_oo_v2_request_universe`, 2,063,737 requests, 2,414 disputes) but never linked.

On the DVM side, `probe_dvm_requests.csv` holds 3,995 YES_OR_NO_QUERY requests relayed from
Polygon. 2,137 carry `childRequester = 0x2c0367a9…` (Managed OOV2) and none of them is linked.
Linked share by quarter: 2025Q2 250/250, 2025Q4 193/425, 2026Q1 263/931, 2026Q2 51/846.
In short: the legacy linkage covered permissionless OOV2 only, so after Polymarket moved to
Managed OOV2, its requests dropped out of the frame mechanically. The omission is structural, not
random. **Without Managed OOV2, the dataset covers fewer than half of Polymarket's DVM requests, and almost
none after 2025Q3.** `scripts/01_prepare_oo_disputes.py` takes both universes, and the match rule
in `03` is unchanged. Whether Managed OOV2 stamps the HASH-format ancillary identically has to be
confirmed by the match rate on first run.

Small residue: 11 HASH-format requests via the standard child tunnel and 2 FULL-format requests
from adapter v1 (`ooRequester 0xcb182285…`, `childRequester 0xbb1a8db2…`) are unlinked
(2,137 + 11 + 2 = 2,150 = 3,995 − 1,845). They are listed in coverage, not chased.

## 6. Field classes

Every release column is tagged in `DATA_DICTIONARY.md` as **raw** (an on-chain or subgraph value,
as emitted), **protocol** (follows from contract rules, e.g. round start = id × 172,800),
**linkage** (our exact join), or **interpretation** (our label, e.g. `uma_value_class`).

## Corrections to earlier notes

- `int256.min` is UMA's P4 / "too early" default for YES_OR_NO_QUERY. Polymarket's `UmaCtfAdapter`
  treats it as `_ignorePrice()` and resets the question. The research label `IGNORE_SENTINEL` was
  half right. an earlier research note described INT256_MIN as "DisputeRejected"; that is wrong for
  ballots and DVM resolutions.
- `1e18` is not "YES". Under the adapter it maps to payout `[1,0]`, which is outcome slot 0. The
  ancillary data names that slot (`p2`), and in sports markets it is a team name. Example in the
  probe: `p1: Grizzlies, p2: Mavericks`. The release carries `ctf_payout` and the ancillary text,
  never a YES/NO label.
- The adapter mapping above is verified for `UmaCtfAdapter`. For the NegRisk UMA adapter it is
  assumed identical and should be checked against its source before v1.0.
