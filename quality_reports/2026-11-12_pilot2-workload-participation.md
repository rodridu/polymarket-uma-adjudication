# Pilot 2: Workload × Participation

**Date:** 2026-11-12
**Dataset:** v1.1.1 (commits, participation, voter_request_incentives, rounds)
**Status:** FROZEN (R4 verified clean: 0C + 0R)
**Review:** R3 complete (0C + 0R remaining after triage). Fixes applied through R3.
**Data cutoff:** through August 2026 (v1.1.1 dataset).

## Definitions

**Workload** (`n_requests_to_vote`): total open UMA requests voters face in a round, read
from the VotingV2 contract. Range: 1–101. For 81% of rounds (378/467),
`n_requests_to_vote == n_linked_requests` (all requests are Polymarket-linked). In the
remaining 89 rounds, 1–8 unlinked requests raise the workload above the linked count.
Workload buckets use `n_requests_to_vote`; all-linked uses `n_linked_requests` as
denominator. In 19% of rounds these differ.

**Workload buckets:** 1, 2–5, 6–10, 11–20, 21–50, 51+.

**Active voters:** voters who appear in the participation table (committed or revealed at
least once in the round). The UMA protocol requires a commit before a reveal, so
revealed ⊆ committed. Stakers who neither committed nor revealed are absent from this
table — the denominator gap documented in Pilot 1.

**All-linked:** voter committed to every linked request in the round
(`n_committed == n_linked_requests`). Trivially satisfied at WL=1 (can only commit to
one request). All-linked is mechanically harder to satisfy as `n_linked_requests` grows:
a single missed request fails the criterion regardless of how many others were committed.

**VoterSlashed (VS) stakers:** voters with at least one VoterSlashed event for a linked
request resolved in a given round. VoterSlashed is emitted for all tracked stakers
(correct, wrong, and DID_NOT_VOTE), not only penalized voters. Not a complete
eligible-staker census: events are emitted only when `updateTrackers()` is called.
Wrong-vote pair-level coverage is 86.4%, voter-level mean coverage is 70.8% (see
`quality_reports/2026-11-12_slashing-coverage-metric.md`).

**Weighting abbreviations:** VR = voter-round weighted; VE = voter-equal weighted.

**Partial commit:** voter committed to some but not all linked requests in a round
(`0 < n_committed < n_linked_requests`).

**Reveal rate:** share of voter-rounds (or voters) with at least one reveal event.

## Table 1: Voter-Round Weighted Participation (active voters only)

| Workload | Voter-rounds | All-linked | All-linked rate | Partial | Revealed | Reveal rate |
|----------|-------------|------------|------|---------|----------|-------------|
| 1        | 8,128       | 8,128      | 100.0% | 0     | 7,669    | 94.4% |
| 2–5      | 40,565      | 39,927     | 98.4% | 638    | 38,467   | 94.8% |
| 6–10     | 30,386      | 29,406     | 96.8% | 980    | 28,727   | 94.5% |
| 11–20    | 49,133      | 47,278     | 96.2% | 1,855  | 47,048   | 95.8% |
| 21–50    | 31,856      | 30,683     | 96.3% | 1,173  | 30,805   | 96.7% |
| 51+      | 2,731       | 2,686      | 98.4% | 45     | 2,693    | 98.6% |
| **Total**| **162,799** | **158,108**| **97.1%** | **4,691** | **155,409** | **95.5%** |

WL≥2 only: 154,671 voter-rounds, 149,980 all-linked (97.0%), 4,691 partial (3.0%).

Conditional on appearing in the participation table, all-linked rate is 96–100% across
all workload buckets. No monotonic decline with workload. WL=1 is trivially 100%.
Among WL≥2 buckets, 51+ and 2–5 both round to 98.4%.

The 51+ bucket rests on 5 rounds (2,731 voter-rounds).

**Commit fraction** (n_committed / n_linked_requests per voter-round) among WL≥2:
5th percentile = 1.0, median = 1.0, mean = 0.985.

These rates condition on participation (Tables 1–2 exclude non-participants). The
extensive margin — whether stakers participate at all — is captured in Table 3.

## Table 2: Voter-Equal Weighted Participation (active voters only)

Each voter's per-round outcomes are averaged, then voters are averaged equally.
Voters appear in multiple workload buckets (voter counts sum to 19,476 across buckets
vs 8,416 unique). The Total row computes each voter's mean across all rounds regardless
of bucket, then averages voters.

| Workload | Voters | All-linked | Reveal rate |
|----------|--------|------------|-------------|
| 1        | 1,623  | 100.0%     | 92.1% |
| 2–5      | 4,485  | 89.2%      | 86.0% |
| 6–10     | 4,408  | 88.3%      | 80.0% |
| 11–20    | 5,054  | 81.7%      | 82.6% |
| 21–50    | 2,961  | 76.4%      | 85.3% |
| 51+      | 945    | 95.5%      | 97.4% |
| **Total**| **8,416** | **76.8%** | **76.5%** |

Commit rate (any commit in the round) is 100% across all rows by construction: the
participation table includes only voters with at least one commit or reveal event.
Column omitted.

Voter-equal all-linked is 76.8% — much lower than voter-round weighted 97.1%. The
gap is driven by voter activity: all-linked rate rises sharply with activity level
(see Table 4 below).

The workload gradient is non-monotonic: all-linked declines from 100% (WL=1, trivially)
to 76.4% (WL=21–50), then rises to 95.5% (WL=51+). The WL=51+ bucket contains 945
voters whose overall median activity is 77 rounds (mean 110.6). Their high all-linked
rate is confounded with their activity level. The all-linked metric is also mechanically
harder to satisfy at higher `n_linked_requests`, so the decline partly reflects this
structural property, not only behavioral change.

## Table 3: VS Commit Ratio by Workload

Round-level: (VS ∩ committed voters) / VS stakers. This captures the share of
VS-recorded stakers who committed.

| Workload | Rounds | Rounds w/ VS | Median VS | Median VS∩committed | Median ratio | Mean ratio |
|----------|--------|-------------|-----------|-----------------|--------------|------------|
| 1        | 65     | 59          | 147       | 79              | 52.0%        | 50.3% |
| 2–5      | 175    | 173         | 578       | 203             | 49.1%        | 46.7% |
| 6–10     | 77     | 77          | 647       | 314             | 47.0%        | 53.8% |
| 11–20    | 90     | 90          | 686       | 574             | 70.2%        | 68.9% |
| 21–50    | 55     | 55          | 685       | 587             | 88.5%        | 80.6% |
| 51+      | 5      | 5           | 529       | 505             | 95.5%        | 94.6% |
| **Total**| **467**| **459**     | **635**   | **271**         | **53.6%**    | **57.3%** |

Ratios are computed on the 459 rounds with VS data. 8 rounds (6 in WL=1, 2 in
WL=2–5) have no VoterSlashed events and are excluded from ratio computations.

The VS commit ratio rises with workload: from ~50% at WL=1–5 to ~95% at WL=51+.
However, this gradient is strongly confounded with calendar time (see Year × Workload
below). The 51+ bucket rests on 5 rounds, all in 2026.

"VS stakers" are not a verified eligible-staker population. The VS record depends on
`updateTrackers()` being called, and coverage may vary by round and era. The ratio is
not a participation rate in the population sense.

## Table 4: All-Linked by Voter Activity Tier

| Activity (total rounds) | Voters | Voter-rounds | VR all-linked | VE all-linked |
|------------------------|--------|-------------|---------------|---------------|
| 1                      | 3,559  | 3,559       | 60.9%         | 60.9% |
| 2–5                    | 2,127  | 5,943       | 82.2%         | 80.0% |
| 6–20                   | 1,051  | 11,109      | 89.0%         | 89.4% |
| 21–100                 | 1,289  | 57,993      | 99.0%         | 98.6% |
| 101+                   | 390    | 84,195      | 99.5%         | 99.4% |

All-linked rate rises sharply with voter activity: from 60.9% for one-round voters to
99.5% for 101+ round voters. The 390 voters (4.6%) with 101+ rounds contribute 84,195
voter-rounds (51.7% of all VR), disproportionately weighting the voter-round aggregate
toward high all-linked rates. This accounts for the 97.1% vs 76.8% gap between
voter-round and voter-equal weighting.

One-round voters (42.3% of voters) each contribute a single 0/1 observation. Their
60.9% all-linked rate is noisy at the individual level.

## Population Overlap

**Voter level:**

| Population | Unique voters |
|-----------|--------------|
| VoterSlashed (VS) stakers | 7,979 |
| Committed voters | 8,416 |
| VS ∩ Committed | 7,842 |
| VS never-committed | 137 |
| Committed without VS record | 574 |

**Voter-round level:**

| Population | Voter-rounds |
|-----------|-------------|
| VS staker voter-rounds | 279,401 |
| Committed voter-rounds | 162,799 |
| Overlap (VS ∩ committed) | 160,428 |
| VS non-commit from never-committed voters (137 voters) | 4,728 |
| VS non-commit from sometimes-committed voters (7,842 voters) | 114,245 |
| Total VS non-commit voter-rounds | 118,973 (42.6% of VS VR) |
| Committed without VS record | 2,371 |

Most VS non-commit voter-rounds (114,245 / 118,973 = 96.0%) come from voters who
committed in other rounds but not in that particular round. Only 137 voters (4,728 VR)
never committed in any round. The participation table cannot distinguish between
stakers who chose not to vote and stakers whose eligibility status is uncertain
(VoterSlashed is not a complete eligibility record).

574 voters committed in at least one round but have zero VoterSlashed events across
the entire dataset (contributing 2,371 committed voter-rounds without VS match). This
is consistent with `updateTrackers()` never being called for these voters, though the
absence is ambiguous: a voter without a VS record may also have never been staked in
a resolution round. Wrong-vote pair-level coverage is 86.4%; voter-level mean coverage
is 70.8% (see `quality_reports/2026-11-12_slashing-coverage-metric.md`).

## Year × Workload Cross-Tab (rounds)

| Year | WL=1 | 2–5 | 6–10 | 11–20 | 21–50 | 51+ | Total |
|------|------|-----|------|-------|-------|-----|-------|
| 2023 | 26   | 19  | 1    | 0     | 0     | 0   | 46 |
| 2024 | 31   | 77  | 11   | 7     | 0     | 0   | 126 |
| 2025 | 8    | 71  | 51   | 35    | 9     | 0   | 174 |
| 2026 | 0    | 8   | 14   | 48    | 46    | 5   | 121 |
| Total| 65   | 175 | 77   | 90    | 55    | 5   | 467 |

Workload is strongly confounded with calendar time. WL=1 rounds are concentrated in
2023–2024 (57/65 = 88%). WL=21–50 and WL=51+ rounds are almost entirely 2026
(51/60 = 85%). The workload gradient in Tables 1–3 cannot be separated from time
trends, voter pool composition changes, and VS coverage variation across eras.

VS commit ratio by year × workload (median per cell):

| Year | WL=1 | 2–5 | 6–10 | 11–20 | 21–50 | 51+ |
|------|------|-----|------|-------|-------|-----|
| 2023 | 57.7% (22) | 56.9% (19) | 58.1% (1) | — | — | — |
| 2024 | 51.4% (29) | 50.7% (75) | 51.5% (11) | 47.2% (7) | — | — |
| 2025 | 36.0% (8) | 37.7% (71) | 44.8% (51) | 49.4% (35) | 51.1% (9) | — |
| 2026 | — | 84.2% (8) | 88.0% (14) | 89.2% (48) | 90.1% (46) | 95.5% (5) |

Cell counts in parentheses. 8 rounds (4 in 2023, 2 in 2024 WL=1, 2 in 2024 WL=2–5)
have no VS data and are excluded from this table but included in the round-count
cross-tab above.

Within-year patterns vary. 2023 (57–58%) and 2024 (47–52%) show no clear workload
gradient. 2025 shows a monotone positive gradient (36% at WL=1 → 51% at WL=21–50,
~15pp span). 2026 is uniformly high (84–96%) across all available workloads. The
cross-sectional gradient in Table 3 is confounded with year; within-year evidence is
mixed (absent in 2023–2024, ~15pp monotone in 2025, flat-high in 2026).

## Year Trends

| Year | Voter-rounds | Voters* | VR all-linked | VR reveal | VE all-linked | VE reveal |
|------|-------------|---------|---------------|-----------|---------------|-----------|
| 2023 | 3,372       | 178    | 99.7%         | 93.8%     | 97.5%         | 80.4% |
| 2024 | 18,211      | 1,752  | 97.6%         | 93.3%     | 89.5%         | 83.4% |
| 2025 | 68,201      | 5,290  | 97.1%         | 95.2%     | 83.5%         | 82.6% |
| 2026 | 73,015      | 3,683  | 96.8%         | 96.3%     | 72.0%         | 72.0% |

*Voter counts sum to 10,903 (voters span multiple years; a voter active in 2024 and
2025 is counted in both rows). 2026 is a partial year (data cutoff: August 2026,
per v1.1.1 dataset).

Voter-round all-linked is stable (96.8–99.7%). Voter-equal all-linked declines from
97.5% (2023) to 72.0% (2026). The 2026 VE all-linked (72.0%) coincidentally equals VE
reveal (72.0%) — verified, not a copy-paste error. Conjecture: the VE decline reflects
accumulation of new low-activity entrants (few rounds, noisy 0/1 all-linked outcomes).
Not tested.

VS commit ratio by year (round-level median): 57.7% (2023) → 51.3% (2024) → 44.1%
(2025) → 89.6% (2026). The 2026 jump coincides with both higher workloads and
potential VS coverage changes. Whether this reflects behavioral change, compositional
change in the staker pool, or VS coverage artifacts is not determined.

## Voter Activity Distribution

| Rounds participated | Voters | Share |
|-------------------|--------|-------|
| 1                 | 3,559  | 42.3% |
| 2–10              | 2,778  | 33.0% |
| 11–100            | 1,689  | 20.1% |
| 101+              | 390    | 4.6%  |
| **Total**         | **8,416** | |

Median rounds per voter: 2. Mean: 19.3. The 390 voters (4.6%) with 101+ rounds
contribute 51.7% of all voter-rounds, disproportionately weighting voter-round
aggregates toward high all-linked rates (Table 4).

## Assessment

1. **Conditional on participating, all-linked rates are high (voter-round weighted
   97.1%, voter-equal 76.8%).** The gap is driven by voter activity: 101+ round voters
   are 99.5% all-linked vs 60.9% for one-round voters. These rates exclude the
   extensive margin (stakers who never committed).

2. **The VS commit ratio shows a positive workload gradient, but it is confounded with
   calendar time.** Within-year, the gradient varies: absent in 2023–2024, monotone
   positive in 2025 (~15pp span), and flat-high in 2026. The cross-sectional gradient
   (Table 3) is confounded with year; within-year evidence is mixed (absent 2023–2024,
   ~15pp in 2025, flat-high 2026). The 51+
   bucket rests on 5 rounds, all in 2026.

3. **Reveal rates are slightly lower than all-linked rates.** 95.5% of active
   voter-rounds (VR weighted) have at least one reveal; 76.5% voter-equal weighted.
   The VR/VE gap parallels the all-linked gap.

4. **The denominator gap is large.** 118,973 VS voter-rounds (42.6%) represent stakers
   without commits. 96% of these come from voters who committed in other rounds.
   The participation table cannot determine whether non-commitment reflects choice,
   inactivity, or eligibility uncertainty.

5. **Year trends diverge by weighting.** Voter-round all-linked is stable. Voter-equal
   all-linked declines, potentially reflecting the accumulating share of low-activity
   entrants.

## Limitations

- **Selection on participation:** Tables 1–2 condition on appearing in the participation
  table (committed or revealed). The extensive margin is in Table 3, which uses VS
  stakers as a proxy for eligibility — but VS is not a verified eligible-staker census.
- **Workload–time confounding:** workload and calendar era are nearly collinear. Within-year
  gradients are weak. Cross-sectional workload gradients should not be read as causal.
- **VS coverage variation:** VoterSlashed events depend on `updateTrackers()`. If coverage
  varies by era, the VS commit ratio may reflect coverage artifacts, not participation
  changes. By-year coverage is not computed here; the slashing coverage report
  (`quality_reports/2026-11-12_slashing-coverage-metric.md`) provides round-level
  distributions but not a year-stratified breakdown.
- **Ecological inference:** round-level gradients (VS ratio) do not establish individual
  voter propensities. An individual voter's behavior in low-WL versus high-WL rounds
  is not examined.
- **Scope:** Polymarket-linked requests only. 89 of 467 rounds include unlinked requests
  not captured in `n_linked_requests`.

## Raw Numbers

- 467 rounds, 4,261 resolved requests, 162,799 committed voter-rounds
- 8,416 unique committed voters, 7,979 unique VS stakers, 7,842 overlap
- 279,401 VS voter-rounds, 160,428 overlapping, 118,973 VS non-commit
- Participation table denominator: committed or revealed voters only
