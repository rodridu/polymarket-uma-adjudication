# Slashing Coverage Report: v1.1.1

**Date:** 2026-11-12
**Metric:** Coverage_wrong = (wrong voters with VoterSlashed) / (all identifiable wrong voters)

## Summary

| Level | Fully covered | Partially covered | Zero coverage | Coverage rate |
|-------|--------------|-------------------|---------------|---------------|
| (voter, request) pairs | 63,238 | — | 9,983 | **86.4%** |
| Requests (3,082 with wrong voters) | 2,029 (65.8%) | 909 (29.5%) | 144 (4.7%) | mean 84.4% |
| Voters (5,018 with wrong votes) | 3,287 (65.5%) | 411 (8.2%) | 1,320 (26.3%) | mean 70.8% |
| Voting rounds (410 with wrong votes) | median 100% | — | — | mean 90.7% |

## Interpretation

Using VoterSlashed events to measure economic penalties for wrong voters captures 86.4% of
identifiable wrong-vote instances. The 13.6% gap (9,983 rows) is consistent with UMA's
lazy `updateTrackers()` design, where slashing accounting runs only when that function is
called — but the absence of an event alone does not confirm the mechanism for every case.

This is a **non-random event observability** problem: VoterSlashed events are emitted only
when `updateTrackers()` is called, so the absence of an event does not reveal the voter's
actual slashing outcome. Researchers using `reward_class` to study slashing incentives
should be aware that the observed sample may not be representative of all wrong voters.

## By Request

- **2,029 requests (65.8%)**: every wrong voter has an observed VoterSlashed event
- **909 requests (29.5%)**: some wrong voters observed, some not (partial coverage)
- **144 requests (4.7%)**: no wrong voter has an observed slashing event

The 144 zero-coverage requests are spread across 50 distinct rounds (not concentrated),
with only 327 total wrong voters — mostly small-turnout disputes. The largest cluster
is 17 requests in round 10281.

Request-level coverage distribution:
- 25th percentile: 0.845
- Median: 1.000
- 75th percentile: 1.000
- Mean: 0.844

## By Voter

- **3,287 voters (65.5%)**: all wrong votes have observed slashing
- **411 voters (8.2%)**: some wrong votes observed, some not
- **1,320 voters (26.3%)**: no wrong votes have observed slashing

Of the 1,320 zero-coverage voters:
- 969 have no matching VoterSlashed events for any request
- 351 have VoterSlashed for other requests (correct/DID_NOT_VOTE) but not for their wrong votes

The median zero-coverage voter has 2 wrong votes (IQR: 1-4, max: 38).

Voter-level coverage distribution:
- 25th percentile: 0.000
- Median: 1.000
- 75th percentile: 1.000
- Mean: 0.708

## By Voting Round (top 10 by wrong-vote volume)

| Round | Observed | Total | Coverage | Unobserved |
|-------|----------|-------|----------|------------|
| 10217 | 4,353 | 7,566 | 57.5% | 3,213 |
| 10228 | 1,991 | 2,663 | 74.8% | 672 |
| 10223 | 984 | 1,842 | 53.4% | 858 |
| 10075 | 1,738 | 1,766 | 98.4% | 28 |
| 10317 | 1,669 | 1,691 | 98.7% | 22 |
| 10211 | 1,081 | 1,609 | 67.2% | 528 |
| 10229 | 1,284 | 1,556 | 82.5% | 272 |
| 10227 | 1,156 | 1,524 | 75.9% | 368 |
| 10220 | 1,523 | 1,523 | 100.0% | 0 |
| 10270 | 981 | 1,279 | 76.7% | 298 |

Round-level coverage distribution:
- 25th percentile: 0.935
- Median: 1.000
- Mean: 0.907

Round 10217 is the largest gap: 3,213 wrong voters unobserved in a single round
(32.2% of all unobserved wrong votes). See investigation below.

## Round 10217 Investigation

**Date:** 2025-12-12 to 2025-12-14 (UTC)
**Requests resolved:** 39 (all RESOLVED, all OK ballots)
**n_requests_to_vote:** 40

The 3,213 unobserved wrong-vote rows come from **90 distinct voters**, each voting wrong
on nearly all 39 requests (~35-39 wrong votes per voter). Key facts:

| Fact | Value |
|------|-------|
| Unique NOT_OBSERVED wrong voters | 90 |
| Overlap with observed wrong voters | 0 (completely disjoint sets) |
| Voters with ANY VoterSlashed event (across all rounds) | 4 of 90 |
| Voters with ZERO VoterSlashed events ever | 86 of 90 |
| Median ballot rounds per voter | 1 |
| Voters who voted in ANY subsequent round | 0 of 90 |

**Assessment:** No evidence of join errors or event extraction problems. The pattern is
consistent with one-time participants: 90 voters entered round 10217, voted wrong on
most requests, and never participated again. Since `updateTrackers()` is called during
subsequent voting, voters who do not return never have their slashing events emitted.
The 4 voters with some VoterSlashed events are the exception — they had partial tracker
updates from other rounds.

**Sensitivity:** Excluding round 10217, coverage rises from 86.4% to 89.7%
(58,885 / 65,655). The round contributes disproportionately (32.2% of the gap) but
does not represent a distinct failure mode — it is the same observability pattern
concentrated in a large cohort of one-time voters.

## Implication for Research

When using this dataset to study UMA slashing incentives:

1. **For behavioral analysis** (`participation_class`): no coverage issue. Every
   resolution-round voter is classified by price comparison — independent of slashing.

2. **For economic analysis** (`reward_class`, `slashed_tokens_raw`): the 13.6% NOT_OBSERVED
   gap means the observed slashing sample is not a random draw from all wrong voters.
   Whether and how this affects specific estimates depends on the research design.

3. **Testable hypothesis**: if infrequent voters are less likely to have their trackers
   updated, the observed slashing panel would overrepresent active voters. This can be
   checked by comparing the participation history of observed vs. NOT_OBSERVED wrong
   voters — but is not established by the coverage metric alone.
