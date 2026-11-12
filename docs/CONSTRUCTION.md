# Construction

## Pipeline

```
01_prepare_oo_disputes   OO request universes (OOV2 + Managed OOV2, Polygon) → disputed requests
                         on Polymarket binary adapters, with condition ids
02_pull_dvm_requests     UMA voting subgraph → every YES_OR_NO_QUERY DVM request
03_link_oo_to_dvm        exact OO → DVM link (time equality + ancillary prefix or stamped hash)
04_pull_votes            VotingV2 VoteRevealed + RequestResolved logs, every round of each request
04b_pull_commits         VoteCommitted logs, per-request identifier-topic-filtered (v1.1)
04c_pull_slashing        VoterSlashed via resolution tx receipts (v1.1)
05_pull_round_state      VotingV2 rounds(id) for each round with a ballot
06_build_release         seven tables + manifest.json (four v1.0, three v1.1 commit-layer)
07_validate_release      fixed checklist C1–C16; release only on all PASS
```

Inputs to 01 are OO request-universe parquets in UMA OO subgraph schema, one per oracle
contract. They are pulled once and recorded with their sha256 in the release notes. 01 itself does
not pull them.

04b mirrors 04's architecture: per-request, identifier-topic-filtered, checkpoint-resumable.
`VoteCommitted` has the same indexed identifier as `VoteRevealed`, so the same topic filter works.
Multiple commits per (request, round, voter) are kept (re-commits allowed by VotingV2).

04c uses a receipt-based approach because `VoterSlashed` lacks an identifier topic.
Resolution txs are batch operations (459 unique txs for 4,261+ resolved requests), so fetching
receipts is efficient. Each receipt's `RequestResolved` logs provide the
`resolvedPriceRequestIndex → dvm_request_id` mapping; `VoterSlashed` logs reference that index.

## Why the link is exact

A disputed OO request on Polygon is relayed to the mainnet DVM. The DVM request's `time` equals
the OO proposal timestamp. Its ancillary data is either the OO ancillary with relay fields
appended (FULL) or a stamp containing `keccak(OO ancillary || ',ooRequester:' || requester)`
(HASH). The link requires equality on both. No text similarity and no time window are used, and
the run stops if two OO requests map to one DVM request.

## Release unit

The unit is the DVM request. A condition can generate more than one disputed request (reset →
re-proposal → second dispute), and a rolled request votes in more than one round. Both are kept
as rows, never collapsed.

## Known limitations

- **Commit layer (v1.1).** `VoteCommitted` events and `VoterSlashed` incentives were added in v1.1.
  Commits carry no direction or weight (encrypted). `participation_class` in
  `voter_request_incentives` uses request-level reveal status, not resolution-round-specific.
- **Address ≠ person.** One entity can use many addresses; delegation routes votes through
  `caller`.
- **Pre-VotingV2 disputes** (before round 9715, 2023-03-14). 3 cases predate VotingV2 and therefore
  have no VotingV2-linked request in this release; they were adjudicated under the legacy Voting
  architecture, which is outside v1.0.0 scope.
- **Slot labels.** `ctf_payout` says which outcome slot was paid, not what the slot is called.
- **NegRisk v4 condition ids** stay null (`OPERATOR_PROVENANCE_UNVERIFIED`) until the
  operator/adapter pair for `0x69c47de9…` is confirmed from first-party source. Ballots and DVM
  requests are unaffected; the condition is enrichment.
- **Snapshot dates.** The OO universes and the DVM request list are snapshots with different
  cutoff times. In a future incremental run, disputes after the DVM snapshot cutoff may appear
  as `DVM_NOT_FOUND` if the DVM request list has not been refreshed. `manifest.json`
  records the coverage window. v1.0.0 contains zero such rows — all 4,261 DVM-linked cases
  matched exactly.

## Validation history

The ballot layer was rebuilt from raw logs after a control failure. A frozen analytical voter
panel recorded 6 voters for one request-round, and the chain showed 262. The rebuild filters
events by the exact request key. Two checks are used: a held-out FULL-format control, which
reproduced exactly, and agreement between the revealed-weight mode and the protocol's resolved
price. On the legacy build that agreement holds for all 1,605 resolved requests (C5).
