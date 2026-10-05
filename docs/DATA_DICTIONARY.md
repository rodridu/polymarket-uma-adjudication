# Data dictionary

Class: **raw** = value as emitted on chain or by the UMA/OO subgraph · **protocol** = follows
from contract rules · **linkage** = produced by this repo's exact joins · **interp** = our label.
All `*_raw` integers are decimal strings (uint256/int256 do not fit int64). Timestamps are Unix
seconds. Addresses are lowercase hex.

## cases.parquet — one row per disputed OO request on a Polymarket binary adapter

| column | class | meaning |
|---|---|---|
| oo_request_id | raw | OO subgraph request id (Polygon) |
| oo_contract | raw | `OOV2` or `MANAGED_OOV2` |
| adapter_address | raw | OO requester = Polymarket UMA adapter |
| architecture, adapter_version | interp | from `registry/adapters.yaml` (first-party Polymarket source) |
| condition_id | linkage | CTF condition; STANDARD closed form, NEGRISK via NegRiskOperator.questionIds |
| condition_id_status | linkage | how condition_id was derived, or why it is null |
| question_id | linkage | adapter question id (STANDARD: keccak(ancillary); NEGRISK: operator mapping) |
| dispute_seq_in_condition | linkage | 1 = first disputed request of the condition, 2 = second, … |
| ancillary_hex / ancillary_text | raw | question as the adapter submitted it (text = UTF-8 decode) |
| request_timestamp | raw | OO request time |
| proposer, proposed_price_raw, proposal_timestamp, proposal_tx | raw | the challenged proposal |
| proposed_uma_value_class | interp | see value classes |
| disputer, dispute_timestamp, dispute_tx | raw | the dispute |
| bond_raw | raw | proposer bond (collateral base units) |
| dvm_link_status | linkage | `DVM_EXACT`, `PRE_VOTING_V2`, `DVM_NOT_FOUND`, `DVM_MULTIPLE_CANDIDATES` |
| dvm_link_format | linkage | `FULL` (DVM ancillary carries OO ancillary) or `HASH` (carries its stamped hash) |
| dvm_request_id | linkage | key into dvm_requests |

## dvm_requests.parquet — one row per DVM request exactly linked to a case

| column | class | meaning |
|---|---|---|
| dvm_request_id | raw | `<identifier>-<time>-0x<ancillary>` (UMA voting subgraph PriceRequest id) |
| oo_request_id, condition_id | linkage | back to the case |
| request_time, ancillary_hex | raw | DVM request key parts (mainnet) |
| roll_count, latest_round | raw | subgraph; rolled = no quorum/agreement, moved to next round |
| first_round | protocol | latest_round − roll_count |
| resolution_status | interp | `RESOLVED`, `RESOLVED_PRICE_MISSING`, `UNRESOLVED_AT_SOURCE`, `STATUS_UNKNOWN` |
| resolution_round, resolved_price_raw, resolution_tx | raw | from VotingV2 `RequestResolved` |
| resolved_uma_value_class, resolved_ctf_payout, resolved_adapter_effect | interp | see value classes |
| resolution_source | linkage | `VotingV2.RequestResolved` (or `LEGACY_SNAPSHOT` in preview builds) |
| ballot_status | interp | `OK` or `NO_REVEALS` |
| n_ballots, n_voters, n_rounds, revealed_weight_raw, first/last_reveal_ts | protocol | aggregates of ballots |

## rounds.parquet — one row per VotingV2 round holding a linked ballot

| column | class | meaning |
|---|---|---|
| round_id | raw | VotingV2 round |
| round_start_ts, reveal_start_ts, round_end_ts | protocol | id × 172,800; +86,400; +172,800 |
| cumulative_stake_raw | raw | `rounds(id).cumulativeStakeAtRound` |
| min_participation_raw, min_agreement_raw | raw | quorum and agreement thresholds (UMA wei) |
| n_requests_to_vote, slashing_library | raw | `rounds(id)` members |
| state_read_block | raw | mainnet block of the `rounds()` read |
| n_linked_requests | linkage | linked requests with ballots in this round |

## ballots.parquet — one row per VoteRevealed event for a linked request

| column | class | meaning |
|---|---|---|
| dvm_request_id, round_id | raw | request and round of the reveal |
| condition_id | linkage | Polymarket condition |
| voter, caller | raw | voter address (delegators vote through `caller`); an address is not a person |
| price_raw | raw | revealed int256 |
| uma_value_class, ctf_payout, adapter_effect | interp | see value classes; for a ballot these are what the adapter *would* do had this value resolved |
| num_tokens_raw | raw | revealed voting weight (UMA wei) |
| is_resolution_round | linkage | ballot cast in the round that resolved the request |
| block_number, block_timestamp, tx_hash, log_index | raw | event provenance |

## Value classes (`pmvotes/semantics.py`)

| price_raw | uma_value_class | ctf_payout | adapter_effect |
|---|---|---|---|
| 0 | P1 | [0,1] | SETTLE |
| 1e18 | P2 | [1,0] | SETTLE |
| 5e17 | P3_UNKNOWN | [1,1] | SETTLE |
| −2²⁵⁵ (int256 min) | P4_TOO_EARLY | — | RESET |
| anything else | NONSTANDARD | — | ADAPTER_REVERT |

UMA layer: YES_OR_NO_QUERY defaults (p1–p4). Adapter layer: `UmaCtfAdapter._constructPayouts` /
`_ignorePrice`. Payout slot 0 is whatever outcome the market lists first (often "Yes", sometimes a
team); read `ancillary_text` for the labels. Never read `P2` as "YES" without checking.
