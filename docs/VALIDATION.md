# Validation

Three orthogonal validation layers certify each release. They answer different questions and
run independently.

## 1. Source-truth validation

Adversarial on-chain audit. A stratified random sample of cases is verified against raw
on-chain data by decoding VoteRevealed and RequestResolved events directly from transaction
receipts. Field-level comparison per ballot: voter, caller, price, numTokens, roundId, block,
identifier, time, ancillaryData.

v1.0.0: 31 cases sampled (seed 20261004), 200 ballots decoded, 9 fields per ballot,
1,800 field comparisons, 0 mismatches. 28 resolutions independently verified. 3 pre-VotingV2
cases confirmed by timestamp.

Full results: `validation/v1.0.0/AUDIT.md` and `validation/v1.0.0/audit_results.json`.

## 2. Regression protection

30 curated edge-case fixtures across 9 categories: permissionless/managed OOV2, all resolution
classes (P1/P2/P3/P4), rolled rounds, high ballot counts, PRE_VOTING_V2, NEGRISK architecture.

v1.0.0: 146 tests passed, 6 expected skips (PRE_VOTING_V2 parametrized cases have no DVM
request), 0 failures.

Run: `pytest`

## 3. Release invariants

Fixed checklist C1–C10, run by `scripts/07_validate_release.py`. A release ships only on
all PASS.

| check | what it verifies |
|---|---|
| C1 | primary keys unique |
| C2 | referential integrity (ballot → request → case; ballot round → rounds) |
| C3 | linkage injective (one case per linked DVM request) |
| C4 | request aggregates reproduce from ballots |
| C5 | resolved price == revealed-weight mode in resolution round |
| C6 | round state valid (stake > 0; agreement floor 0.50 or 0.65) |
| C7 | raw integers are exact decimal strings |
| C8 | resolved prices are standard values (P1/P2/P3/P4) |
| C9 | provenance complete (tx_hash, log_index, block_number on every ballot) |
| C10 | manifest reproduces (row counts, sha256) |

Run: `python scripts/07_validate_release.py`
