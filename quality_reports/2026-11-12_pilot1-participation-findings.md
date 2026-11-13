# Pilot 1: Same-Round Selective Participation — Preliminary Findings

**Date:** 2026-11-12
**Status:** PRELIMINARY — denominator gap unresolved
**Review rounds:** 7 (R1: 7C+7R. R2: 5C+9R. R3: 1C+4R. R4: 4C+9R. R5: 4C+9R+5m. R6: 4C+3R+4m. R7: 0C+3R+3m.)

## Research Question

> 投票者是否在不同裁决请求之间选择性分配注意力？
> (Do voters selectively allocate attention across different adjudication requests within the same round?)

## Preliminary finding

Among the 162,799 voter-rounds observed in the participation table (which records only
voters who committed at least once), 97.1% committed to every linked request
in their round (voter-round-weighted; voter-level mean: 76.8%). Non-participating
stakers — those eligible but never committing — are not in this table and cannot be
assessed here.

Whether the predominantly all-linked commit pattern reflects individual behavioral
choice or a tooling artifact (hypothesis: batch-commit interfaces — not verified) is
not determined by this data.

---

## Table 1: Round Workload Distribution (n=467 rounds)

| Statistic | Value |
|-----------|-------|
| Mean requests per round | 9.7 |
| Median | 5 |
| 25th percentile | 2 |
| 75th percentile | 12 |
| Max | 101 |
| Rounds with ≥2 requests | 402 (86.1%) |
| Linked requests / total UMA requests | 95.7% mean, 100% median |

Right-skewed. Middle 50% of rounds have 2-12 requests; a few exceed 50.
Our linked requests account for 95.7% of total UMA requests per round on average.
The remaining ~4.3% are unlinked UMA requests not in this dataset; whether they
cluster in specific rounds or periods has not been tested.

## Table 2: Within-Round Participation Pattern (n=162,799 voter-rounds)

Base: all unique (round_id, voter) pairs in the participation table. Every row in the
table has committed=True (0 rows with committed=False). A voter-round with fewer committed
requests than the round's linked total appears as having rows for only the committed subset.

**Commit completeness** (relative to round's linked requests):

| Pattern | Count | % of 162,799 |
|---------|-------|---------------|
| Committed to ALL linked requests | 158,108 | 97.1% |
| Committed to a strict subset | 4,691 | 2.9% |

**Reveal completeness** (all 162,799 voter-rounds; all have commits):

| Pattern | Count | % of 162,799 |
|---------|-------|---------------|
| Revealed all committed requests | 155,359 | 95.4% |
| Partial reveal (some but not all) | 50 | 0.03% |
| No reveal (committed only) | 7,390 | 4.5% |

The 50 partial-reveal voter-rounds span 46 voters across 21 rounds. These include a
cluster in round 10262 (4 voters, each 41/83 requests — identical counts suggesting
a tooling or batch artifact). The remaining cases are unexplained.

**Scope caveat:** These patterns describe voters who appear in the participation table.
The 4,691 voter-rounds that committed to a strict subset represent observed request-level
variation; whether this reflects selection or data edge cases (e.g., commit events
near round boundaries) has not been investigated.

## Table 3: VS-Linked Commit Ratio by Workload

Numerator: committed voters who also appear in VoterSlashed for the same resolution round
(committed ∩ VS). Denominator: unique voters with VoterSlashed events per resolution round.
This matching ensures numerator ⊆ denominator. Commit Rate is the **mean of per-round
ratios**, not the ratio of column means.

n=459 rounds with VoterSlashed data. The VS-linked commit ratio is not a participation
rate — the denominator (VS stakers) reflects VoterSlashed emission, not verified eligibility.

| Workload | Rounds | Avg WL | Avg Committed∩VS | Avg VS Stakers | VS-Linked Commit Ratio |
|----------|--------|--------|-------------------|----------------|------------------------|
| 1 | 59 | 1.0 | 130 | 299 | 50.3% |
| 2-5 | 173 | 3.2 | 232 | 530 | 46.7% |
| 6-10 | 77 | 7.8 | 386 | 727 | 53.8% |
| 11-20 | 90 | 14.5 | 539 | 792 | 68.9% |
| 21-50 | 55 | 29.6 | 574 | 727 | 80.6% |
| 51+ | 5 | 69.8 | 545 | 578 | 94.6% |

Note: 51+ bucket has n=5 rounds; small-n instability applies to 21-50 (n=55) and 51+.

**Spearman(workload, VS-linked commit ratio): ρ = 0.471, p < 1e-26** (n=459 rounds,
cross-sectional, no time or era controls, rounds not independent — p-value overstates
significance; ρ describes the VS-linked ratio, not a verified participation rate).

Across rounds, higher request count is associated with a higher VS-linked commit ratio. No controls
for calendar period, contract version, or participant pool composition have been applied.

Possible explanations (all untested; data needed to discriminate in brackets):
- (a) higher-workload rounds have more at stake [per-round fee/stake data]
- (b) coordination: large rounds signal importance [external activity measures]
- (c) fee incentives increase with request count [fee schedule data]
- (d) confound: both workload and participation increase over time [era stratification]
- (e) mechanical: both numerator (committed ∩ VS) and denominator (VS stakers) derive
  from VoterSlashed emission, which scales with request count — more requests create more
  slashing opportunities and more overlap by construction, potentially inflating ρ

## Denominator Gap

The participation table records only voters with observed commits or reveals. The
VoterSlashed event set provides a broader (but incomplete) view:

| Metric | Value |
|--------|-------|
| Rounds with VoterSlashed data | 459/467 (98.3%) |
| Committed voter-rounds | 162,799 |
| VoterSlashed voter-rounds | 279,401 |
| Overlap (committed ∩ VS) | 160,428 (98.5% of committed) |
| Committed, not in VS | 2,371 (1.5% of committed) |
| VS-only, no observed commit | 118,973 (42.6% of VS) |

The 118,973 VS-only voter-rounds have a VoterSlashed event but no commit in the
participation table. The cause — non-entry by an eligible staker, missing commit rows,
or a VoterSlashed emission gap — is not distinguished.

**VoterSlashed coverage limitations:**
- VoterSlashed emission is lazy (`updateTrackers()`-dependent). Per-staker emission
  coverage across the full eligible population is unknown.
- The 86.4% coverage figure from the [slashing coverage report](2026-11-12_slashing-coverage-metric.md)
  measures coverage of identifiable wrong-vote (voter, request) pairs, not of the
  denominator population (all eligible stakers).
- Round 10217 shows a pattern consistent with participation-linked missingness:
  90 one-time voters with no later participation and no VoterSlashed events (see
  [slashing coverage report](2026-11-12_slashing-coverage-metric.md), Round 10217
  Investigation). Generality beyond this round is untested; its effect on Table 3
  direction and magnitude is unknown.

**Implication:** Table 3 uses VoterSlashed stakers as denominator. If VoterSlashed
understates the true eligible population, true participation rates would differ — but
the direction and magnitude of the bias depend on the missingness structure, which is
unresolved.

## Revealed Voting-Weight Distribution (n=6,992 revealed voters)

Based on maximum `num_tokens_raw` per voter across all revealed ballots, converted to
UMA (÷ 10^18). This is the maximum observed ballot weight, not the staked amount.

| Percentile Band | UMA Range (non-overlapping) |
|-----------------|----------------------------|
| P0-P10 | 0.00 – 0.02 |
| P10-P20 | 0.02 – 1.00 |
| P20-P30 | 1.00 – 1.67 |
| P30-P50 | 1.67 – 13.72 |
| P50-P70 | 13.72 – 189.14 |
| P70-P80 | 189.14 – 1,031.78 |
| P80-P90 | 1,031.78 – 1,058.71 |
| P90-P100 | 1,058.71 – 6,708,508 |

Heavily right-skewed: top 10% spans ~3.8 orders of magnitude. Headcount participation
rates may diverge substantially from weight-weighted rates.

## Tooling Check (added 2026-11-12)

UMA VotingV2 exposes per-request `commitVote()` (per user's review of public ABI; not
independently verified here). Batch submission paths exist (the contract or wrapping
contracts may offer `batchCommit()`, multicall, or similar), but the specific batch
function used by each transaction is not identified here — the commit event alone does
not distinguish the call path.

The protocol does not force all-linked commits. The statistics below characterize the
joint distribution of transaction structure and commit completeness. The mechanism
(tooling default, deliberate choice, or automation) is untested.

### Stat A: Transaction batching

Primary figures on rounds with ≥2 requests (402 rounds, 154,671 voter-rounds), where
single-tx and all-linked are not trivially true:

| Metric (WL≥2) | Value |
|----------------|-------|
| Voter-rounds all-linked | 149,980 (97.0%) |
| Voter-rounds single-tx | 151,908 (98.2%) |

Cross-tab (WL≥2):

|  | Multi-tx | Single-tx | Total |
|--|----------|-----------|-------|
| Partial-linked | 219 | 4,472 | 4,691 |
| All-linked | 2,544 | 147,436 | 149,980 |
| Total | 2,763 | 151,908 | 154,671 |

95.3% of WL≥2 voter-rounds are both single-tx and all-linked. The two properties differ
by 5.0pp: all-linked rate is 97.1% for single-tx voter-rounds vs 92.1% for multi-tx
(partial rate: 2.9% single-tx vs 7.9% multi-tx; unadjusted for voter activity — Stat B
shows activity strongly predicts all-linked rate). Single-tx does not imply all-linked
(4,472 single-tx partial voter-rounds); whether the association is an artifact of
activity confounding is untested.

Full dataset, all rounds (unit: commit rows, not voter-rounds — row-weighted, not
voter-round-weighted):

| Metric | Value |
|--------|-------|
| Total commit transactions | 169,428 |
| Total commit rows | 2,145,975 |
| Single-request transactions | 15,359 (9.1%) |
| Multi-request transactions | 154,069 (90.9%) |
| Rows from single-request tx | 15,360 (0.7%) |
| Rows from multi-request tx | 2,130,615 (99.3%) |
| Transactions with >1 voter | 0 |

Note: 15,360 rows from 15,359 single-request transactions (one single-request tx emits
two commit rows for the same request; cause not determined). The 99.3% row share is volume-weighted: most commit events originate
from multi-request transactions, but this does not directly measure voter-round behavior
(for that, see the WL≥2 cross-tab above).

### Stat B: Address behavior

All-linked rate by voter activity tier (voter-level mean = 76.8%; voter-round-level = 97.1%):

| Tier (rounds) | Voters | Mean All-Linked % | Median All-Linked % |
|----------------|--------|-------------------|---------------------|
| 1 | 3,559 | 60.9% | 100.0% |
| 2-5 | 2,127 | 80.0% | 100.0% |
| 6-20 | 1,051 | 89.4% | 100.0% |
| 21-100 | 1,289 | 98.6% | 100.0% |
| 101+ | 390 | 99.4% | 100.0% |

The 97.1% voter-round figure is dominated by high-activity voters; the unweighted
voter-level mean is 76.8%. 2,905 of 8,416 voters (34.5%) have ≥1 partial-commit round.

All-linked rate by caller type (activity-confounded, not controlled):

| Type | Voter-Rounds | All-Linked % |
|------|-------------|--------------|
| Self-caller (voter=caller) | 119,698 | 96.2% |
| Has delegate (voter≠caller) | 43,101 | 99.7% |

Partial-commit voters: 2,905 voters with ≥1 partial-commit round. Median total
rounds = 2, median partial rounds = 1. 1,639 voters (56%) are partial in all their
rounds. This pattern is consistent with both tooling differences (infrequent voters
using different interfaces) and behavioral differences (first-time or exploratory
participation). The data does not distinguish these.

### Stat C: Time variation

All-linked rate by half-year period:

| Period | Voter-Rounds | Rounds | Avg WL | All-Linked % | Single-Tx % | Delegation % |
|--------|-------------|--------|--------|-------------|-------------|-------------|
| 2023-H1 | 1,329 | 19 | 1.8 | 100.0% | 97.8% | 38.9% |
| 2023-H2 | 2,043 | 27 | 2.1 | 99.6% | 97.5% | 45.4% |
| 2024-H1 | 3,649 | 45 | 2.5 | 99.7% | 98.8% | 50.2% |
| 2024-H2 | 14,562 | 81 | 4.5 | 97.1% | 98.2% | 28.2% |
| 2025-H1 | 24,162 | 84 | 6.7 | 96.7% | 97.7% | 30.3% |
| 2025-H2 | 44,039 | 90 | 9.7 | 97.4% | 98.6% | 25.1% |
| 2026-H1 | 57,778 | 91 | 20.5 | 96.3% | 98.1% | 25.6% |
| 2026-H2 | 15,237 | 30 | 25.1 | 99.0% | 98.8% | 17.0% |

All-linked % by period × workload (multi-request rounds only):

| Period | 2-5 | 6-10 | 11-50 | 51+ |
|--------|-----|------|-------|-----|
| 2023-H2 | 99.2% | — | — | — |
| 2024-H1 | 99.5% | 100.0% | 100.0% | — |
| 2024-H2 | 98.5% | 93.3% | 90.4% | — |
| 2025-H1 | 98.9% | 94.6% | 94.1% | — |
| 2025-H2 | 97.7% | 97.6% | 96.7% | — |
| 2026-H1 | 97.6% | 98.1% | 95.9% | 98.2% |
| 2026-H2 | 99.8% | 99.8% | 98.9% | 98.5% |

No sustained break in the period-level all-linked rate (range: 96.3-100%; 2024-H2 shows
a 2.6pp drop from 2024-H1, coinciding with delegation decline 50%→28%, untested). Within
period × workload cells, the range is wider (90.4-100%), with 2024-H2 showing the lowest
rates at higher workloads (90.4% for 11-50 requests). Single-tx rate stable at 97-99%.
Delegation rate declined from ~50% to ~17%; aggregate all-linked rate did not change
correspondingly (hypothesis that both delegated and self-callers use batch interfaces
is untested).

### Tooling check assessment

Both single-tx and all-linked rates are high for WL≥2 voter-rounds. They differ by 5.0pp
(all-linked: 97.1% single-tx vs 92.1% multi-tx; unadjusted for voter activity).

Key rates:
- 97.0% of WL≥2 voter-rounds are all-linked (voter-round level)
- 98.2% of WL≥2 voter-rounds use a single transaction (voter-round level)
- 95.3% are both single-tx and all-linked
- All-linked rate: 97.1% single-tx vs 92.1% multi-tx (5.0pp gap, unadjusted for activity)
- 99.3% of commit rows come from multi-request transactions (row-weighted, different unit)
- Delegated callers: 99.7% all-linked (activity-confounded, not controlled)
- High-activity voters (101+ rounds): 99.4% all-linked
- 34.5% of voters (2,905) have ≥1 partial-commit round
- All-linked rate range: 90.4-100% across period × workload cells

The protocol allows per-request commits. Most voter-rounds (98.2%, WL≥2) use one
transaction; single-tx voter-rounds have a higher all-linked rate (97.1% vs 92.1%,
unadjusted — voter activity may confound). Batch-commit tooling, deliberate voter
choice, and coordination norms remain competing explanations; no mechanism is
established by these statistics.

---

## Pilot 1 — Frozen Conclusion

**Observed:** Among participating voter-rounds, 97.1% committed to all linked requests
(voter-round-weighted, including trivially-satisfied WL=1 rounds; 97.0% for WL≥2;
voter-level mean: 76.8%). Single-tx and all-linked rates are each high for WL≥2 rounds
(98.2% and 97.0%); single-tx voter-rounds have higher all-linked rate (97.1% vs 92.1%,
unadjusted for voter activity). Mechanism not identified.

**Not confirmed:** Whether the all-linked pattern reflects economic choice, automation
defaults, interface design, batch-commit tooling, or their combination. The protocol
allows per-request commits. Whether the single-tx / all-linked gap (97.1% vs 92.1%)
holds after controlling for voter activity is untested.

**Not supported from these statistics alone:** Inferences about information acquisition,
attention allocation, or participation rates among the full eligible-staker population.

**Denominator status:** VoterSlashed provides a partial view of stakers per round (42.6%
of VoterSlashed voter-rounds have no observed commit). VoterSlashed is not a random sample of eligible
stakers; its relationship to the true eligible population is unverified. No eligibility
denominator reconstruction attempted.

**Open questions preserved (per user direction):**
- If interface automation is present, does it lower participation cost, lower independent
  judgment, both, or neither?
- Competing mechanisms: economic choice, interface default, workload/coordination
  effects, mechanical VoterSlashed inflation (Table 3 hypotheses a–e).
- These are retained as interpretive frames, not new pilots.

---

## Raw Numbers for Verification

**Participation table:**
- Total voter-rounds: 162,799 (all rows committed=True; 0 committed=False)
- Committed to all linked requests: 158,108 (97.1% voter-round; 76.8% voter-level mean)
- Committed to strict subset: 4,691 (2.9%)
- Full reveal: 155,359 (95.4%)
- Partial reveal: 50 (0.03%) — 46 voters, 21 rounds
- Committed only (no reveal): 7,390 (4.5%)
- Voters with ≥1 partial-commit round: 2,905 (34.5% of 8,416)

**Denominator:**
- VoterSlashed voter-rounds: 279,401
- Committed ∩ VS: 160,428
- VS-only (no commit): 118,973 (42.6%)
- Committed, not in VS: 2,371 (1.5%)
- Rounds with ≥2 requests: 402/467
- VoterSlashed rounds: 459/467
- Spearman ρ(workload, matched VS-linked commit ratio): 0.471, n=459

**Tooling (all rounds):**
- Total commit transactions: 169,428
- Multi-request transactions: 154,069 (90.9%)
- Commit rows from multi-request tx: 2,130,615 (99.3% of 2,145,975)
- Transactions with >1 voter: 0
- Unique voters: 8,416; unique callers: 8,569
- Self-callers: 8,235 (97.8% of voters)
- Voters with >1 caller: 190

**Tooling (WL≥2 only, 402 rounds, 154,671 voter-rounds):**
- All-linked: 149,980 (97.0%)
- Single-tx: 151,908 (98.2%)
- Single-tx AND all-linked: 147,436 (95.3%)
- Single-tx AND partial: 4,472 (2.9%)
- Multi-tx AND all-linked: 2,544 (1.6%)
- Multi-tx AND partial: 219 (0.1%)
