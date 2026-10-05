# Limitations

## What this data cannot tell you

- **Who is behind an address.** One entity can use many addresses; delegation (`voter` vs
  `caller`) routes votes through an intermediary. Address-level analysis is not person-level
  analysis.

- **Whether a vote or outcome was correct.** The dataset records what voters chose and what the
  protocol resolved. Normative evaluation is outside scope.

- **Commit-stage participation.** v1.0 covers revealed ballots only. Voters who committed but
  did not reveal are invisible. Planned for v1.1.

- **Trading, prices, or redemption.** This dataset does not include market prices, order fills,
  or CTF redemption amounts. See `docs/JOINING.md` for interoperability with datasets that do.

## Known data gaps

- **427 null condition_ids.** NegRisk v4 cases (`0x69c47de9…` adapter) have
  `condition_id_status = OPERATOR_PROVENANCE_UNVERIFIED`. The operator/adapter pair is
  unconfirmed from first-party source. Ballots and DVM requests are unaffected.

- **3 pre-VotingV2 cases.** Disputes before VotingV2's first observed round were adjudicated
  under the legacy Voting architecture. They appear in `cases.parquet` with
  `dvm_link_status = PRE_VOTING_V2` but have no ballots or DVM request.

- **Snapshot boundaries.** The OO universes and DVM request list are snapshots with different
  cutoff times. v1.0.0 contains zero `DVM_NOT_FOUND` rows. In a future incremental run,
  disputes after the DVM snapshot cutoff may temporarily appear unlinked until refreshed.

## What raw logs do not tell you without reconstruction

- A DVM ruling is not the same as the condition's final payoff. `int256.min` (P4) triggers an
  adapter reset, not a settlement.
- A rolled request votes in multiple consecutive rounds. The resolution round is not the only
  round with ballots.
- A multi-request resolution transaction emits logs for all requests in the batch. Matching by
  position rather than by identifier misattributes resolutions.
