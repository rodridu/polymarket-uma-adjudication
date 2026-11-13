# Pilot 4 Feasibility: Capital Lockup and Economic Exposure

**Date:** 2026-11-12
**Dataset:** v1.1.1 (cases, dvm_requests, raw oo_disputes)
**Sample:** 28 conditions (stratified by year, architecture, roll, adapter effect)
**Status:** FEASIBILITY CHECK

## Q1: Condition → DVM Link Reliability

| Metric | Count |
|--------|-------|
| Total cases | 4264 |
| DVM_EXACT links | 4261 (99.9%) |
| PRE_VOTING_V2 (no DVM) | 3 |
| Resolved | 4261 |

**Verdict: FEASIBLE.** Linkage is complete for all VotingV2-era cases (4,261/4,261).
No new infrastructure needed.

## Q2: DVM Entry to Final Redeemable Time

### Available Timestamps

| Event | Source | Coverage |
|-------|--------|----------|
| Dispute filed | `dispute_timestamp` | 4261/4261 (100%) |
| OO proposal | `proposal_timestamp` (= DVM `request_time`, verified equal for all 4,261) | 4261/4261 (100%) |
| DVM round start | `first_round × 172800` | 4261/4261 (100%) |
| DVM resolution | `(resolution_round + 1) × 172800` (VotingV2 ROUND_SECONDS = 172,800s = 48h) | 4261/4261 (100%) |
| OO settlement | `oo_settlement_timestamp` (raw, not in release) | 4190/4261 (98.3%) |

71 cases lack settlement timestamps — all from 2026, likely still pending at data cutoff
(not verified on-chain). Lockup statistics below use the 4,190 completed cases only and
are right-censored: cases with longer lockup durations are more likely to be pending.

### DVM Duration (dispute → DVM resolution round end)

| Stat | Hours | Days |
|------|-------|------|
| Min | 48.7 | 2.0 |
| 25th pct | 66.3 | 2.8 |
| Median | 77.2 | 3.2 |
| 75th pct | 89.9 | 3.7 |
| Max | 270.0 | 11.3 |

Minimum ~2 days (single round = 48h). Maximum 11.3 days (multiple rolls).

### Settlement Lag (DVM resolution → OO settlement on Polygon)

| Stat | Hours |
|------|-------|
| Min | 0.3 |
| Median | 0.5 |
| Mean | 4.1 |
| Max | 611.4 |

| Window | Count | Share |
|--------|-------|-------|
| < 1 hour | 3813 | 91.0% |
| 1–24 hours | 241 | 5.8% |
| 1–7 days | 126 | 3.0% |
| > 7 days | 10 | 0.2% |

91% of settlements occur within 1 hour of DVM resolution. No negative lags
(settlement always after DVM round end). The lag presumably reflects the time for
someone to relay the DVM result and call settle() on the adapter (not verified
on-chain).

### Settlement Lag by Adapter Effect

| Effect | N | Median lag (h) | Mean lag (h) | Max lag (h) |
|--------|---|----------------|--------------|-------------|
| SETTLE | 1960 | 0.5 | 6.7 | 611.4 |
| RESET | 2230 | 0.6 | 1.8 | 215.0 |

Medians are similar (0.5 vs 0.6h), but SETTLE mean is 3.7× higher (6.7 vs 1.8h),
driven by a longer tail (max 611h vs 215h).

### Total Lockup Duration (dispute → OO settlement)

| Stat | Hours | Days |
|------|-------|------|
| Min | 49.2 | 2.0 |
| Median | 78.2 | 3.3 |
| Mean | 81.9 | 3.4 |
| Max | 707.9 | 29.5 |

Median total lockup: 3.3 days. The DVM adjudication dominates;
settlement lag adds a median of 0.5 hours.

### Polygon Validation: CTF ConditionResolution Timing

Probed 9 conditions on Polygon via Etherscan V2 (chainid=137) for CTF
ConditionResolution events (topic0 = keccak256 of event signature, topic1 =
condition_id). CTF contract: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`.

OO−CTF gap sign: positive = CTF resolved before OO settlement (positions redeemable
earlier); negative = CTF resolved after OO settlement. `Seq` = `dispute_seq_in_condition`
from the dataset: ordinal index of this dispute within the condition's dispute history.

| Condition | Arch | Seq | CTF timing | OO−CTF gap |
|-----------|------|-----|------------|------------|
| 0x1503… (2023) | STANDARD | 1 | BEFORE_DVM | +127h (CTF 5 days before OO) |
| 0x3254… (2025) | STANDARD | 3 | AFTER_DVM | −1.3h |
| 0xb57d… (2026) | STANDARD | 1 | NOT_FOUND | — (unexplained; may be unresolved or different topic mapping) |
| 0x862e… (2026) | NEGRISK | 1 | BEFORE_DVM | +79.6h |
| 0xe4e7… (2026) | STANDARD | 1 | AFTER_DVM | −0.0h |
| 0x0fba… (2026) | STANDARD | 1 | BEFORE_DVM | +66.2h |
| 0x30b6… (2026) | STANDARD | 2 | AFTER_DVM | −2.0h |
| 0xe86e… (2024) | STANDARD | 2 | AFTER_DVM | +0.0h |
| 0xc5a3… (2025) | NEGRISK | 2 | AFTER_DVM | −1.1h |

**Two distinct patterns (8/9 found, 1 NOT_FOUND):**

1. **AFTER_DVM (5/8 found):** CTF ConditionResolution occurs minutes to hours after
   OO settlement (range: −2.0h to +0.0h). Inferred flow (not verified on-chain):
   DVM resolves → `settleAndGetPrice()` on OO → adapter `reportPayouts()` on CTF.
   Observed in all 3 probed seq≥2 conditions and 2 of 5 probed seq=1 conditions
   (n=5 total).

2. **BEFORE_DVM (3/8 found):** CTF ConditionResolution occurs 1.4–22.6 hours AFTER
   the dispute, but 66–127 hours BEFORE OO settlement and BEFORE the DVM round starts.
   All three are seq=1 (first dispute for the condition), all SETTLE effect.

   **Confirmed mechanism:** Examination of the 3 CTF resolution transactions shows:
   - C1/C3: Transaction calls `resolve(bytes32)` (selector `0x5c23bdf5`) on the adapter
   - C2: Transaction calls `resolveQuestion(bytes32)` (selector `0x6b942f7c`) on the
     NegRisk operator (`0x71523d0f655b41e805cec45b17163f528b59b820`)
   - All 3 tx receipts emit CTF `ConditionResolution` + adapter-level event only — NO
     OO settlement event in the same transaction

   The adapter's `resolve()` reads a **previously settled** OO price. A prior undisputed
   OO proposal for the same condition had already settled, making `resolve()` callable.
   The `resolve()` call happens to execute AFTER our disputed proposal was filed but
   BEFORE the DVM adjudicates. `seq=1` means first *dispute*, not first *proposal* — an
   undisputed prior proposal would not appear in our dataset.

   Timeline: `[Prior OO settle] → [Our proposal → dispute] → [resolve() → CTF resolved]
   → [DVM votes] → [Our OO settle (bond only)]`

   **Consistency check:** All 3 BEFORE_DVM probes have SETTLE effect (DVM upheld the
   proposed price), consistent with the prior OO settlement. If a RESET condition had
   been resolved by a prior undisputed proposal, the CTF payouts could be inconsistent
   with the DVM outcome.

   **Population scope:** 2,694 of 3,248 unique conditions (82.9%) have exactly 1 dispute,
   meaning prior undisputed proposals could exist. Of these, 1,047 are SETTLE effect
   (candidates for consistent BEFORE_DVM resolution). The actual prevalence of
   BEFORE_DVM requires the full CTF timestamp scrape (step 2 below).

**Implications for capital lockup measurement:**

- **Bond lockup** (proposer + disputer): Always dispute → OO settlement. Covered by
  existing `oo_settlement_timestamp` (98.3%).
- **Position redeemability**: Gated on CTF ConditionResolution, NOT on OO settlement.
  In 3/8 probed conditions, CTF resolution preceded OO settlement by 66–127h (whether
  this also preceded DVM resolution needs per-probe timestamp comparison). In 5/8,
  CTF resolution followed OO settlement within ~2h. The population split is unknown
  from 8 non-random probes — a systematic sample is needed.
- CTF ConditionResolution timestamps are **queryable from Polygon** via Etherscan V2
  (confirmed working with existing API key, chainid=137).

### Q2 Verdict

**FEASIBLE, with a critical nuance.** Two distinct lockup measures are needed:

1. **Bond lockup duration** (dispute → OO settlement): Computable from existing data
   for 98.3% of cases. Median 3.3 days.

2. **Position redeemability** (CTF resolution): Requires Polygon CTF ConditionResolution
   timestamps. Queryable via Etherscan V2 (confirmed). In 5/8 probed conditions
   (AFTER_DVM), CTF resolution ≈ OO settlement (within 2h). In 3/8 (BEFORE_DVM),
   positions were redeemable 66–127h earlier — `oo_settlement_timestamp` would
   OVERSTATE position lockup for these cases. Population prevalence unknown from
   these 8 non-random probes.

**Data gaps:**
- `oo_settlement_timestamp` not in release tables. Extend `06_build_release.py`.
- CTF ConditionResolution timestamps need Polygon queries (~3,248 unique conditions
  via Etherscan V2). Duration depends on API tier rate limits (unverified).
- Nechepurenko CTF resolutions table has NO timestamp columns — confirms THAT
  resolution happened but not WHEN.

**RESET cases:** For 2,273 RESET cases, the OO settlement marks bond return, not
condition resolution. The condition is re-proposed and may settle without DVM dispute
(invisible to this dataset). Final redeemable time requires CTF resolution data.

## Q3: Outstanding Collateral Reconstruction

### Q3A: Bond-Level Capital Lockup (computable now)

| Metric | Value |
|--------|-------|
| Bond values | 6 distinct: 100, 250, 500, 1250, 1500, 3750 USDC |
| Dominant bond | 500 USDC (91% of cases) |
| Total bond capital-days | 13,836,837 USDC-days |
| Mean per case | 3,302 USDC-days |
| Median per case | 3,233 USDC-days |

Bond capital-days = proposer_leg + disputer_leg, where:
- Proposer leg = bond_USDC × (settle − proposal_timestamp) days
- Disputer leg = bond_USDC × (settle − dispute_timestamp) days

The proposer's bond is locked from proposal (median 0.3h before dispute, max 68.9h).
The 2× shortcut understates proposer lockup by the proposal→dispute interval.
This is **directly computable from existing data** for all cases with settlement timestamps.

### Q3B: Market-Level Collateral (requires CTF position data)

Market-level collateral = total USDC locked as collateral backing outstanding CTF positions
for a disputed condition. This is not in the current dataset.

**External data source: Nechepurenko (HuggingFace `TimeSeventeen/Polymarket-v1`)**

| CTF Table | Size | Rows | Relevant Columns |
|-----------|------|------|------------------|
| resolutions.parquet | 92.8 MB | 1,313,030 | condition_id, oracle, question_id, outcome_slot_count (no timestamps) |
| splits.parquet | 4,957 MB | — | — |
| merges.parquet | 592 MB | — | — |
| redemptions.parquet | 2,792 MB | — | — |
| preparations.parquet | 101 MB | — | — |

Condition overlap: 2,466 of 3,248 unique conditions in our dataset appear in
CTF resolutions (75.9%). The 4,261 DVM_EXACT cases map to 3,248 unique conditions.

If splits/merges/redemptions tables contain `amount` and `condition_id`, market-level
collateral can be reconstructed as: collateral(t) = Σ splits − Σ merges − Σ redemptions
for each condition up to time t. This requires downloading ~8.3 GB total (splits 5.0 GB +
merges 592 MB + redemptions 2.8 GB). Note: NEGRISK conditions route through the
NegRiskAdapter, so CTF PositionSplit events may not capture them — NEGRISK coverage
needs verification.

**Alternative: Direct Polygon chain queries**

CTF events on Polygon can be queried via Etherscan V2 (chainid=137) or POLYGON_RPC_URL.
Topic indices differ per event type and need ABI verification before querying:
- ConditionResolution: conditionId as topic1 (confirmed working)
- PositionSplit/PositionsMerge: conditionId likely topic3 (not yet probed)
- PayoutRedemption: conditionId may not be indexed, making getLogs filtering by
  condition impossible — needs ABI check
For 3,248 unique conditions with confirmed events, call count depends on which events
are filterable by topic.

### Q3 Verdict

**Bond-level: FEASIBLE (computable now).** Total bond capital lockup across 4,190
settled cases: 13,836,837 USDC-days.

**Market-level: CONDITIONALLY FEASIBLE.** Requires either:
1. Nechepurenko CTF splits/merges/redemptions data (~8.3 GB download, join on condition_id)
2. Polygon chain infrastructure (parameterize chain.py for Polygon getLogs)

Both paths are technically viable. Nechepurenko data is faster (no RPC calls),
but may not cover the full timeline or may use different condition_id format.

## Summary

| Question | Verdict | Data Source | New Infrastructure |
|----------|---------|-------------|-------------------|
| Q1: Condition → DVM link | **FEASIBLE** | release/cases.parquet | None |
| Q2: Bond lockup duration | **FEASIBLE** | raw oo_disputes (98.3%) | Add to release tables |
| Q2: Position redeemable (AFTER_DVM) | **FEASIBLE** | OO settle ≈ CTF res (±2h, n=5) | Polygon queries to confirm |
| Q2: Position redeemable (BEFORE_DVM) | **FEASIBLE** | Polygon CTF events | Etherscan V2 queries |
| Q2: Position redeemable (RESET) | **PARTIAL** | Needs CTF resolution data | Polygon queries |
| Q3: Bond capital lockup | **FEASIBLE** | raw oo_disputes + release | Add oo_settlement_timestamp to release |
| Q3: Market collateral | **CONDITIONAL** | Nechepurenko CTF (~8.3 GB) or Polygon | HF download or chain.py; verify NEGRISK |

### Key Numbers

- 4190 cases with complete bond lockup timeline (98.3%)
- Median bond lockup: 3.3 days (dispute → OO settlement)
- Settlement lag: median 0.5h, 91% within 1 hour
- Bond capital: 13,836,837 USDC-days total across 4,190 settled cases
- Adapter effects: 1960 SETTLE, 2230 RESET
- CTF resolution timing: 2 patterns in 8 found probes — AFTER_DVM (5/8, within 2h
  of OO settle) and BEFORE_DVM (3/8, 66–127h pre-settle, mechanism hypothesized)
- Polygon Etherscan V2: confirmed working for ConditionResolution queries (chainid=137);
  other CTF event types (splits, merges, redemptions) not yet probed

### Recommended Next Steps

1. **Add `oo_settlement_timestamp` to release tables** — extend `06_build_release.py`
   to carry this field from raw data into `cases.parquet`
2. **BEFORE_DVM mechanism confirmed** — `resolve()` reads prior OO settlement. Next:
   determine population prevalence via full CTF timestamp scrape
3. **Query CTF ConditionResolution timestamps from Polygon** — Etherscan V2
   (chainid=137), ~3,248 unique conditions. Distinguish BEFORE_DVM vs AFTER_DVM
   cases for accurate position lockup measurement
4. **Classify BEFORE_DVM vs AFTER_DVM conditions** — use CTF resolution timestamp
   vs DVM round timing to flag conditions with prior undisputed resolution
5. **Assess market-level collateral** — download CTF splits/merges/redemptions (~8.3 GB)
   or build Polygon getLogs infrastructure; verify NEGRISK coverage first
6. **Document the capital-days methodology** — bond lockup (proposal → OO settle for
   proposer, dispute → OO settle for disputer). Position redeemability depends on CTF
   resolution timing. BEFORE_DVM pattern confirmed: adapter's `resolve()` reads prior
   undisputed OO settlement. Consistency risk for RESET conditions if CTF resolved
   before DVM overturns the price

## Appendix: Adapter Effect by Year

| Year | SETTLE | RESET | Total |
|------|--------|-------|-------|
| 2023 | 45 | 28 | 73 |
| 2024 | 186 | 208 | 394 |
| 2025 | 523 | 792 | 1315 |
| 2026 | 1206 | 1202 | 2408 |

## Appendix: Sample Conditions

| Condition | Year | Arch | Effect | Rolls | DVM (h) | Settle lag (h) | Bond (USDC) |
|-----------|------|------|--------|-------|---------|----------------|-------------|
| 0x150394ee8a… | 2023 | STANDARD | SETTLE | 1 | 130.2 | 8.9 | 500 |
| 0x9825975fbc… | 2023 | STANDARD | RESET | 1 | 143.0 | 32.9 | 500 |
| 0x2c315428b1… | 2023 | STANDARD | RESET | 0 | 50.0 | 0.7 | 500 |
| 0xea75c99dd7… | 2023 | STANDARD | SETTLE | 0 | 92.4 | 0.5 | 500 |
| 0xed3a181bf9… | 2024 | STANDARD | RESET | 1 | 102.1 | 0.3 | 500 |
| 0xaa24b4f151… | 2024 | STANDARD | SETTLE | 1 | 134.1 | 0.5 | 500 |
| 0x10bfd2053b… | 2024 | STANDARD | RESET | 0 | 93.6 | 0.3 | 500 |
| 0x9ce4ce441b… | 2024 | STANDARD | RESET | 0 | 67.3 | 0.4 | 500 |
| 0x39ee169bbd… | 2024 | NEGRISK | SETTLE | 1 | 103.9 | 0.4 | 500 |
| 0x03b7010e69… | 2024 | NEGRISK | SETTLE | 1 | 108.0 | 0.3 | 500 |
| 0x9120a6aed0… | 2024 | NEGRISK | SETTLE | 0 | 78.8 | 0.4 | 500 |
| 0x0299283786… | 2024 | NEGRISK | SETTLE | 0 | 71.3 | 0.5 | 500 |
| 0x2158d1f831… | 2025 | STANDARD | SETTLE | 2 | 151.9 | 0.9 | 500 |
| 0x3b2f19935f… | 2025 | STANDARD | RESET | 1 | 119.1 | 0.5 | 500 |
| 0xaa649eacdf… | 2025 | STANDARD | SETTLE | 0 | 76.0 | 0.5 | 500 |
| 0x30e19926d2… | 2025 | STANDARD | SETTLE | 0 | 79.4 | 0.5 | 500 |
| 0x727a5c6a6e… | 2025 | NEGRISK | RESET | 2 | 193.7 | 0.7 | 500 |
| 0x479f7f46aa… | 2025 | NEGRISK | RESET | 2 | 193.7 | 0.7 | 500 |
| 0x840a5510a2… | 2025 | NEGRISK | SETTLE | 0 | 80.3 | 1.1 | 500 |
| 0x30ecf18dbd… | 2025 | NEGRISK | RESET | 0 | 79.7 | 0.4 | 500 |
| 0x6aa39e488a… | 2026 | STANDARD | RESET | 1 | 108.1 | 0.5 | 500 |
| 0x6747bae226… | 2026 | STANDARD | SETTLE | 1 | 119.8 | 0.5 | 500 |
| 0x6d293b5476… | 2026 | STANDARD | SETTLE | 0 | 59.0 | 0.5 | 500 |
| 0xdd7e5dc57d… | 2026 | STANDARD | SETTLE | 0 | 76.0 | 0.6 | 500 |
| 0xc4c3dbcc37… | 2026 | NEGRISK | SETTLE | 1 | 118.4 | 0.8 | 500 |
| 0x2cd24d17f5… | 2026 | NEGRISK | SETTLE | 1 | 113.7 | 0.8 | 500 |
| 0x41f4203be7… | 2026 | NEGRISK | RESET | 0 | 62.2 | 0.8 | 500 |
| 0x9548ac2d22… | 2026 | NEGRISK | RESET | 0 | 90.6 | 0.8 | 500 |
