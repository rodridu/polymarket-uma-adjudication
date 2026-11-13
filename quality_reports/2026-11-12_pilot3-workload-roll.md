# Pilot 3: Workload × Roll (GAT/SPAT Decomposition)

**Date:** 2026-11-12
**Dataset:** v1.1.1 (dvm_requests, rounds, ballots)
**Status:** FROZEN (R4 verified clean: 0C + 0R)
**Review:** R3 complete (0C + 0R remaining after triage). Fixes applied through R3.

## Definitions

**Workload** (`n_requests_to_vote`): total open UMA requests voters face in a round, read
from the VotingV2 contract. Range: 1–101. Workload buckets: 1, 2–5, 6–10, 11–20, 21–50,
51+.

**Roll:** a request that does not resolve in a given round and moves to the next round.
UMA protocol checks two thresholds before resolving:

1. **GAT (Global Activity Threshold):** total revealed weight must meet
   `min_participation_raw`. In this dataset, GAT = 5,000,000 UMA (constant across all 467
   rounds). If GAT fails, the request rolls regardless of agreement.

2. **SPAT (Support Price Agreement Threshold):** agreement weight for the winning price
   must meet `min_agreement_raw`. The threshold is an absolute weight:
   `min_agreement_raw = spat_ratio × cumulative_stake_raw`, where `cumulative_stake_raw`
   is the total staked UMA at the round (both fields read directly from VotingV2
   contract's `rounds()` view function via `rounds.parquet`). The `spat_ratio` is not
   stored on-chain as a named field; it is inferred empirically as
   `min_agreement_raw / cumulative_stake_raw`. Two distinct ratios are observed in the
   data (regime boundaries and dates are empirical observations, not contract parameters):
   - Rounds ≤ 10097 (before 2025-04-16): ratio = 0.50 (223 rounds)
   - Rounds ≥ 10100 (after 2025-04-22): ratio = 0.65 (244 rounds)
   - Rounds 10098–10099 not in dataset.

   Because the threshold is a fraction of total staked weight (not revealed weight), a
   round where all revealers agree can still fail SPAT if the revealed pool is a small
   fraction of the staked pool.

**Protocol decision order:** GAT checked first, then SPAT. A request that fails both is
classified as GAT failure.

**SPAT margin:** `(agreement_weight − min_agreement_raw) / min_agreement_raw`. Positive =
passed with margin; negative = failed (rolled).

**GAT margin:** `(total_revealed_weight − min_participation_raw) / min_participation_raw`.

**Request-round pair:** each request appears in one or more rounds (first_round through
latest_round). Each non-resolution appearance is a roll. Total: 4,341 request-round pairs
(4,261 resolved + 80 rolled). Outcomes within a round are not independent — multiple
requests share the same voter pool and stake environment.

**Three mutually exclusive states:**
- **Resolved:** request resolves in this round (passes both GAT and SPAT)
- **GAT failure:** GAT not met (rolls regardless of SPAT)
- **SPAT failure:** GAT met but SPAT not met

## Result: All 80 Rolls Are SPAT Failures

| Outcome | Request-round pairs | Share |
|---------|-------------------|-------|
| Resolved | 4,261 | 98.2% |
| GAT failure | 0 | 0.0% |
| SPAT failure | 80 | 1.8% |
| **Total** | **4,341** | |

GAT never fails in this sample (0 of 4,341 request-round pairs). This reflects the
observed data; rounds where GAT failure caused a roll still appear in the dataset
(the request carries to the next round and we observe all rounds from first_round
through latest_round). Minimum GAT margin is +0.64 (total revealed weight = 1.64×
GAT threshold). All 80 rolls are SPAT failures.

## Table 1: SPAT Failure Rate by Workload (request-round level)

| Workload | Pairs | Resolved | Rolled | Roll rate |
|----------|-------|----------|--------|-----------|
| 1        | 65    | 59       | 6      | 9.2% |
| 2–5      | 523   | 504      | 19     | 3.6% |
| 6–10     | 575   | 564      | 11     | 1.9% |
| 11–20    | 1,245 | 1,211    | 34     | 2.7% |
| 21–50    | 1,584 | 1,574    | 10     | 0.6% |
| 51+      | 349   | 349      | 0      | 0.0% |
| **Total**| **4,341** | **4,261** | **80** | **1.8%** |

SPAT failure rate is higher at low workloads and lower at high workloads, but the
pattern is not strictly monotonic (WL=11–20 at 2.7% vs WL=6–10 at 1.9%). The WL=51+
bucket has 0 rolls from 349 pairs across 5 rounds — a small sample that cannot
establish a zero-roll rate.

Request-round pairs are clustered by round: outcomes in the same round share the same
voter pool and stake. The effective sample is closer to 467 rounds than 4,341 pairs,
especially for the 51+ bucket (5 rounds).

## Table 2: Round-Level Roll Rate by Workload

| Workload | Rounds | Has roll | Mean roll frac | Max roll frac |
|----------|--------|----------|----------------|---------------|
| 1        | 65     | 6        | 9.2%           | 100.0% |
| 2–5      | 175    | 15       | 4.2%           | 100.0% |
| 6–10     | 77     | 6        | 2.2%           | 33.3% |
| 11–20    | 90     | 12       | 2.9%           | 66.7% |
| 21–50    | 55     | 6        | 0.7%           | 10.5% |
| 51+      | 5      | 0        | 0.0%           | 0.0% |
| **Total**| **467**| **45**   | **3.8%**       | **100.0%** |

45 of 467 rounds (9.6%) had at least one roll. "Has roll" mechanically increases with
request count (more chances for at least one failure). "Mean roll fraction" is the
comparable metric across buckets. The total-row 3.8% (round-weighted) differs from
Table 1's 1.8% (request-weighted) because these are different units.

## Table 3: SPAT Failure Rate by Year

| Year | Pairs | Rolled | Rate |
|------|-------|--------|------|
| 2023 | 81    | 8      | 9.9% |
| 2024 | 413   | 19     | 4.6% |
| 2025 | 1,326 | 42     | 3.2% |
| 2026 | 2,521 | 11     | 0.4% |
| **Total** | **4,341** | **80** | **1.8%** |

Round-level: rounds with at least one roll = 8 (2023), 11 (2024), 19 (2025), 7 (2026).

## Year × Workload Cross-Tab (SPAT failure rate)

| Year | WL=1 | 2–5 | 6–10 | 11–20 | 21–50 | 51+ |
|------|------|-----|------|-------|-------|-----|
| 2023 | 15.4% (4/26) | 8.5% (4/47) | 0.0% (0/8) | — | — | — |
| 2024 | 6.5% (2/31) | 4.6% (10/218) | 1.3% (1/77) | 6.9% (6/87) | — | — |
| 2025 | 0.0% (0/8) | 2.2% (5/228) | 2.7% (10/375) | 5.7% (26/456) | 0.4% (1/259) | — |
| 2026 | — | 0.0% (0/30) | 0.0% (0/115) | 0.3% (2/702) | 0.7% (9/1,325) | 0.0% (0/349) |

Workload is strongly confounded with calendar time (see Pilot 2 for round counts per
cell). WL=1 is concentrated in 2023–2024; WL=21+ is almost entirely 2025–2026.
Within-year, the workload gradient is inconsistent: 2024 shows 6.9% at WL=11–20 but
1.3% at WL=6–10; 2025 shows increasing rates from WL=2–5 (2.2%) to WL=11–20 (5.7%).
Many cells have few observations.

## Table 4: SPAT Failure by Regime

| SPAT regime | Pairs | Rolled | Rate |
|-------------|-------|--------|------|
| 0.50 (rounds ≤ 10097) | 823 | 27 | 3.3% |
| 0.65 (rounds ≥ 10100) | 3,518 | 53 | 1.5% |

The stricter 0.65 regime has a lower SPAT failure rate (1.5% vs 3.3%). This is
counterintuitive — raising the agreement threshold should make it harder to resolve.
The comparison is confounded with time (the 0.65 regime started April 2025) and with
changes in pool size and voter composition. Not evidence that raising the
threshold reduces failures.

## SPAT Margin Analysis

### Resolved requests

| Statistic | Value |
|-----------|-------|
| Total resolved with ballots | 4,261 |
| Close calls (margin < 0.10) | 30 (0.7%) |
| Minimum margin | +0.0019 |
| 25th percentile | +0.4410 |
| Median | +0.4844 |
| Mean | +0.4965 |

Most resolved requests pass SPAT with substantial margin (median +0.48, i.e. agreement
weight 48% above the threshold). 30 resolved requests (0.7%) cleared the threshold by
less than 10%.

### Rolled requests

| Statistic | Value |
|-----------|-------|
| Total rolled with ballots | 80 |
| Within 10% of threshold (margin > −0.10) | 35 (43.8%) |
| Minimum margin | −0.7919 |
| Median margin | −0.1169 |
| Maximum margin | −0.0021 |

35 of 80 rolled request-rounds fell within 10% of the SPAT threshold (the 10% cutoff
is arbitrary). Margin range is wide: from −0.79 (agreement weight was 21% of threshold)
to −0.002 (missed by 0.2%). Together with the 30 resolved close calls, there are 65
request-rounds within ±10% of the threshold — but resolved and rolled requests are
different populations and the near-threshold density on each side is not directly
comparable.

## GAT Analysis

| Statistic | Value |
|-----------|-------|
| GAT threshold | 5,000,000 UMA (constant) |
| GAT failures | 0 / 4,341 |
| Minimum GAT margin | +0.6441 (weight = 1.64× GAT) |
| 25th percentile margin | +2.6553 |
| Median margin | +2.8588 |
| Mean margin | +2.9973 |

GAT is not binding for Polymarket-linked requests in this sample. The closest a
request came to GAT failure had total revealed weight at 1.64× the threshold. The
median request has 3.86× the threshold. The GAT parameter (5M UMA) is far below the observed revealed weight in this sample.

## Round 9745: Unanimous Voters, SPAT Failure

Round 9745 (WL=1, 2023) had 54 voters who unanimously agreed on the resolved price
(100% agreement by voter count). The request rolled because:

- Total revealed weight: 8.22M UMA (GAT passes: 8.22M > 5.00M GAT threshold)
- Cumulative staked weight: 21.24M UMA
- SPAT threshold: 10.62M UMA (0.50 × 21.24M)
- Agreement weight: 8.22M UMA < 10.62M threshold → SPAT failure (margin = −0.23)

Only 38.7% of staked weight was revealed. All revealers agreed, but the revealed pool
was too small relative to total staked weight. This illustrates that SPAT is a
stake-weighted threshold: a round where all voters agree can still fail when revealed
turnout is insufficient. Voter count unanimity and weight-based resolution are distinct.

## Roll Event Distribution

63 of 4,261 distinct requests (1.5%) rolled at least once (each request resolves
exactly once, so the 4,261 count equals both the distinct request count and the
resolved request-round pair count). Of those:
- 48 rolled once
- 13 rolled twice
- 2 rolled three times

80 total roll events across 45 distinct rounds. The largest single-round cluster observed is round 10185 (8 rolls)
(WL=12, 2025): 8 requests rolled in a single round, with 464–465 voters. Agreement
weight was 40–41% of staked weight, below the 0.65 × cumulative_stake threshold. Round 10185 contributes 8/80 = 10% of all rolls from a single round.

## Assessment

1. **GAT is not binding in this sample.** Zero GAT failures across 4,341 request-round
   pairs. The three-state decomposition reduces to two states: Resolved vs SPAT failure.

2. **SPAT failure rate is higher at low workloads and lower at high workloads in the
   cross-section.** This gradient is confounded with calendar time (see Year × Workload
   cross-tab). Within-year, the pattern is inconsistent. Whether the cross-sectional
   association reflects a workload mechanism, a time trend, or compositional change is
   not determined.

3. **SPAT failure rate decreases over time.** 9.9% (2023) → 0.4% (2026). Confounded
   with regime change, pool growth, and workload composition.

4. **The stricter SPAT regime has a lower observed failure rate.** Counterintuitive but
   confounded with time. Not evidence that raising the threshold reduces failures.

5. **SPAT is a stake-weighted threshold.** Round 9745 illustrates that unanimous voter
   agreement can fail SPAT when total revealed weight is below the threshold (a fraction
   of cumulative staked weight). Conceptually, SPAT failures could mix two patterns:
   low revealed turnout (sufficient agreement among revealers, but insufficient total
   weight) and genuine disagreement (sufficient turnout, but insufficient agreement).
   The 80 rolls have not been formally classified by type; this decomposition is a
   hypothesis, not a result.

6. **35 of 80 rolled request-rounds fell within 10% of the SPAT threshold.** The 10%
   cutoff is arbitrary. The margin density near zero includes both narrow passes (30
   resolved) and narrow failures (35 rolled).

## Limitations

- **Workload–time confounding:** workload and calendar era are strongly associated (see
  Pilot 2 year × workload cross-tab). Cross-sectional workload gradients should not
  be read as causal.
- **Non-independence:** request-round outcomes are clustered by round. The effective
  sample for the 51+ bucket is 5 rounds, not 349 pairs. No confidence intervals
  reported.
- **Scope:** Polymarket-linked requests only. GAT and SPAT behavior for non-linked
  requests is not observed.
- **Endogenous workload:** rolled requests from round *t* appear in round *t+1*'s
  `n_requests_to_vote`, creating a lagged mechanical link between the outcome (roll)
  and the regressor (workload in the next round). If rolls cluster in time (i.e.
  roll in round *t* predicts roll in round *t+1*), this would attenuate the
  cross-sectional association between workload and roll rate. Whether that condition
  holds is not tested here.
- **Resolved sample includes re-rolled requests:** requests that resolved on a second
  or third attempt are in the resolved sample. Their margins may differ systematically
  from first-attempt resolutions.
- **Single protocol, single parameter setting:** only two SPAT regimes observed. External
  validity to other thresholds or protocols is unknown.

## Raw Numbers

- 467 rounds, 4,341 request-round pairs (4,261 resolved, 80 rolled)
- 63 requests rolled (48 once, 13 twice, 2 three times)
- 45 rounds had at least one roll
- SPAT regimes: 0.50 (223 rounds, 823 pairs) and 0.65 (244 rounds, 3,518 pairs)
- GAT: 5,000,000 UMA constant, minimum margin +0.64, never fails
- SPAT threshold = spat_ratio × cumulative_stake_raw
