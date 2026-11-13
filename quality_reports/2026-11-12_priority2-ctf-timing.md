# Priority 2: CTF Resolution Timing and Payout Consistency

**Date:** 2026-11-12
**Status:** CLOSED (R7 — mechanism audit complete; Standard 3/3, NegRisk 15/15; USDC unit validation added)
**Scope:** All 3,248 unique DVM-escalated conditions on Polygon

## Executive Summary

61.5% of DVM-escalated conditions had their CTF (Conditional Tokens Framework) resolved
**before DVM adjudication began**. Of those, **1,355 conditions (67.8%) show CTF payouts
whose direction disagrees with the eventual DVM outcome direction**. The hypothesized
mechanism is cross-request: after a dispute, `_reset()` creates a new OO request
(Request B) whose settlement drives the CTF, while the DVM adjudicates the original
request (Request A). This is supported by sample audits and contract code but not
verified at population level.

A 3-case post-reset audit (R4, Standard architecture) confirmed that `_reset()`
creates a new OO Request B with `requestTimestamp = block.timestamp = T₁`,
where T₁ ≠ T₀ (gaps: 63–256 hours). A 15-case NegRisk audit (R5) verified
the full evidence chain through the NegRisk Operator's dual-identifier mapping
(requestId → questionId → conditionId): the operator's reported result matches
the CTF payout direction in 15/15 cases across all strata.

Request B's propose-and-settle lifecycle is recovered in 3/3 Standard cases (R6):
creation (RequestPrice at T₁), proposal (ProposePrice), and settlement (Settle)
all found in OOv2 events on Polygon. OOv2 settled price matches the adapter's
QuestionResolved price in 3/3 cases, and all 3 settled without dispute
(disputer = 0x0). The adapter's `settleAndGetPrice(T₁)` call is inferred from
contract code and supported by the price match. NegRisk result transmission is confirmed in 15/15 sampled
cases (R5). In no sampled case does the CTF payout contradict the result
reported by the adapter pipeline. The 1,355 figure is a descriptive statistic
(CTF payout direction ≠ DVM outcome direction), not a count of confirmed
cross-request events — population-level verification has not been performed.

**Summary statement (Standard architecture, 3-case):** In three audited Standard-adapter
cases, a post-reset OO request settled without dispute, and its settled price matched the
price emitted by the adapter when resolving the CTF condition.

**Summary statement (NegRisk architecture, 15-case):** In fifteen audited NegRisk-adapter
cases, the NegRisk Operator's reported result matched the CTF payout direction, and the
full conditionId → questionId → requestId linkage was reconstructed from on-chain events.

**Remaining limitations:** The 1,355 cross-request disagreement figure is descriptive;
population-level verification has not been performed. The `settleAndGetPrice` call is
inferred from contract code and supported by price match, not independently observed.
The `oo_settlement_timestamp` field semantics remain unresolved (Priority 3).

**Revision history:**
- R1: Stated 544 (27.2%) inconsistent. Caused by P1/P2 namespace inversion.
- R2: Corrected to 1,355 (67.8%), labeled "cross-request disagreement."
- R3: Request linkage found 26/30 timestamp+questionID matches; hypothesized same-request.
- R4: OOv2 contract review + 3-case post-reset audit confirms cross-request mechanism.
  `_reset()` creates Request B at T₁ ≠ T₀; CTF uses Request B, DVM adjudicates Request A.
- R5: Check B NegRisk 15-case audit complete. Full linkage reconstructed in
  15/15 cases. NegRisk pipeline correctly transmits OO result to CTF in all cases.
  NegRisk dual-identifier architecture verified: requestId (OO) ≠ questionId (CTF).
- R6: Request B settlement recovered for 3/3 Standard cases. OOv2
  ProposePrice and Settle events found at T₁. Settled price matches adapter's
  QuestionResolved price in 3/3. All 3 Request B proposals settled undisputed.
- R7 (final): Priority 2 closed. USDC unit validation test added to CI.
  No new evidence; this revision adopts clean summary wording and marks completion.

## Data Sources

- **Table 1 (CTF Resolution):** Etherscan V2 getLogs for ConditionResolution events
  on Gnosis CTF contract `0x4D97DC...` (Polygon, chainid=137). 3,248 queries, 0 errors.
- **Table 2 (OO Settlement History):** Merged from existing release tables + CTF data.
- **Table 3 (Timing Classification):** Computed from Tables 1+2 + DVM round boundaries.
- **Payout Consistency:** Re-queried 1,998 pre-DVM conditions for payoutNumerators from
  ConditionResolution event data, compared with DVM `resolved_adapter_effect`.

## Table 1: CTF Resolution Coverage

| Status | Count | % |
|--------|-------|---|
| FOUND | 3,132 | 96.4% |
| NOT_FOUND | 116 | 3.6% |
| **Total** | **3,248** | |

116 conditions (3.6%) have no ConditionResolution event on Polygon.
These may be unresolved conditions or conditions resolved through a different mechanism.

### CTF Oracle Distribution

| Oracle | Count | % |
|--------|-------|---|
| C3 adapter v4 (`0x6507...`) | 1,584 | 50.6% |
| NegRisk adapter (`0xd91e...`) | 921 | 29.4% |
| C1 adapter v2 (`0x6a9d...`) | 543 | 17.3% |
| C3 adapter v3 (`0x157c...`) | 84 | 2.7% |

The NegRisk adapter (`0xd91e...`) is the resolver for conditions using the C2 NegRisk
architecture — it's the layer between the base adapter and the CTF, not a mismatch.

## Table 3: 5-Category Timing Classification

| Category | Count | % | Description |
|----------|-------|---|-------------|
| BEFORE_DISPUTE | 0 | 0.0% | CTF resolved before any dispute filed |
| AFTER_DISPUTE_BEFORE_DVM | 1,998 | 61.5% | CTF resolved after dispute but before DVM round started |
| DURING_DVM | 215 | 6.6% | CTF resolved during DVM adjudication |
| AFTER_DVM | 919 | 28.3% | CTF resolved after DVM completed |
| UNMATCHED | 116 | 3.6% | No CTF resolution found |

### Key Finding: Zero BEFORE_DISPUTE

All CTF resolutions occur after at least one dispute is filed. This is consistent with
the mechanism: the adapter's `resolve()` function reads a settled OO price, which requires
at least one proposal to have completed its liveness period. In practice, the dispute
triggers `_reset()`, which creates a new OO request (Request B). Request B's settlement
is what the adapter reads when calling `resolve()`.

### Timing Detail

| Category | ctf vs dispute (median) | ctf vs DVM start (median) |
|----------|------------------------|--------------------------|
| AFTER_DISPUTE_BEFORE_DVM | +3.1h | -24.5h |
| DURING_DVM | +31.2h | +8.7h |
| AFTER_DVM | +109.9h | +87.1h |

Pre-DVM conditions resolve a median of 3.1 hours after the dispute (and 24.5 hours
before DVM begins). This timing is consistent with the confirmed mechanism (R6): the
dispute triggers `_reset()` (creating Request B), and the gap represents the time
until Request B's proposal settles and `resolve()` is called. In the 3 Standard
cases with propose/settle recovery (R6), all 3 Request B proposals settled
undisputed (disputer = 0x0).

### Path x DVM Effect Cross-Tab

| Path | RESET | SETTLE | Total |
|------|-------|--------|-------|
| AFTER_DISPUTE_BEFORE_DVM | 1,133 | 865 | 1,998 |
| DURING_DVM | 166 | 49 | 215 |
| AFTER_DVM | 510 | 409 | 919 |
| UNMATCHED | 15 | 101 | 116 |

## Q1: Prevalence of Pre-DVM CTF Resolution

**1,998 / 3,248 conditions (61.5%)** had CTF resolve before DVM adjudication.

All 1,998 are single-dispute conditions (n_disputes=1). No multi-dispute condition
appears in the pre-DVM category. (Hypothesis: multi-dispute conditions have longer
dispute histories that overlap with DVM rounds.)

By DVM effect:
- RESET: 1,133 (56.7% of pre-DVM)
- SETTLE: 865 (43.3% of pre-DVM)

## Q2: Which OO Request Did CTF Use?

The CTF oracle address identifies which adapter called `resolveCondition()`.
For 70.6% of the 3,132 resolved conditions (2,211), the CTF oracle matches the
adapter that filed the OO request in our dataset. The remaining 29.4% (921) are
the NegRisk architecture, where the base adapter (`0x2f5e...`) files the OO
request but the NegRisk adapter (`0xd91e...`) is the actual oracle that resolves
the CTF.

**The adapter resolves the CTF by calling `oo.settleAndGetPrice()` with the stored
requestTimestamp** (T₁ after reset). This queries OOv2 for Request B's settled price
at call time, then forwards the result to CTF `resolveCondition()`. Request B's
full lifecycle — creation, proposal, and settlement — is confirmed in 3 sample
cases (R6): the OOv2 Settle event's price matches the adapter's QuestionResolved
price in 3/3. The DVM request in our dataset corresponds to Request A (initial,
at T₀), not Request B.

## Q3: Payout Consistency (Cross-Request Disagreement)

Full population: 1,998 pre-DVM conditions re-queried for payoutNumerators.
Direction derived from price (0→NO, 1e18→YES) and payouts ([0,1]→NO, [1,0]→YES).

| DVM Effect | Total | Consistent | Disagreement | CTF 50-50 | P3/Unknown |
|------------|-------|------------|-------------|-----------|------------|
| RESET | 1,133 | 134 (11.8%) | 981 (86.6%) | 8 (0.7%) | 10 (0.9%) |
| SETTLE | 865 | 404 (46.7%) | 374 (43.2%) | 63 (7.3%) | 24 (2.8%) |
| **Total** | **1,998** | **538 (26.9%)** | **1,355 (67.8%)** | **71 (3.6%)** | **34 (1.7%)** |

### Bug Disclosure: P1/P2 Namespace Inversion

The R1 report (now superseded) stated 544 INCONSISTENT (27.2%). This was caused by
a labeling bug in `ctf_direction()` which mapped payout [1,0]→P1 and [0,1]→P2.
The project's authoritative convention in `semantics.py` is the opposite:
P1 = price(0) with payout [0,1], P2 = price(1e18) with payout [1,0].

Comparing P1/P2 labels from these two incompatible namespaces inverted every result:
what was labeled CONSISTENT was actually disagreement, and vice versa.

**Fix:** The corrected check compares YES/NO directions directly (price 0→NO,
1e18→YES; payout [0,1]→NO, [1,0]→YES), bypassing the P1/P2 label system entirely.

### 30-Case Conflict Audit

To validate the corrected numbers, a 30-case audit examined CTF resolution tx receipts
on Polygon. Sample: 15 old-"INCONSISTENT"/SETTLE + 10 old-"INCONSISTENT"/RESET +
5 old-"CONSISTENT" controls, all Standard architecture.

**Evidence chain per case:**

1. **CTF payout vector:** Decoded from ConditionResolution event data (payoutNumerators)
2. **Adapter's settled price:** From QuestionResolved event, topic[2] (indexed int256).
   Event signature confirmed: `QuestionResolved(bytes32,int256,uint256[])`, not
   the initially assumed `(bytes32,int256,bytes,uint256)`.
3. **Same-question confirmation:** Adapter questionID (topic[1]) matches the questionID
   embedded in the DVM-linked `oo_request_id` in 30/30 cases (23 single-condition txs,
   7 batch txs with per-condition event matching).
4. **Zero OO settlement events:** 0/30 tx receipts contain Settle, ProposalSettled,
   or PriceSettled events. The adapter always reads a previously settled OO result.

**Audit results by group:**

| Group | n | Adapter == Proposed | Adapter ≠ Proposed | True Label |
|-------|---|---------------------|---------------------|------------|
| old-INCONSISTENT/SETTLE | 15 | 15 | 0 | All CONSISTENT |
| old-INCONSISTENT/RESET | 10 | 0* | 10 | All CONSISTENT |
| old-CONSISTENT/control | 5 | 0 | 5 | All DISAGREEMENT |

*After proper batch-tx event matching. Initial audit had 1 apparent mismatch
from taking the wrong QuestionResolved event in a 15-condition batch tx.

The audit confirms the label inversion: every old-INCONSISTENT case is actually
consistent, and every old-CONSISTENT control shows genuine disagreement.

### Interpretation

**1,355 conditions (67.8% of pre-DVM)** show cross-request disagreement:
Request B's settlement (used by CTF) has a different direction from Request A's
DVM-confirmed outcome.

**RESET disagreement (981 cases, 86.6%):** Request B's settlement direction
matched Request A's disputed proposal direction. The DVM rejected the disputed
proposal (RESET = incorrect), so the CTF payout (following Request B) disagrees
with DVM. In the 3-case R6 audit, Request B's settled price is directly confirmed
from OOv2 Settle events. At population level, this interpretation relies on
the CTF payout direction matching the rejected proposal direction.

**SETTLE disagreement (374 cases, 43.2%):** Request B's settlement direction
was opposite to Request A's disputed proposal. DVM confirmed the disputed proposal
was correct (SETTLE). The CTF payout follows Request B, which disagrees with DVM.
At population level, this interpretation has not been confirmed from OOv2 settlement
records beyond the 3-case sample.

**Consistent (538 cases, 26.9%):** Request B's settlement happened to agree with
the eventual DVM outcome. For RESET: Request B opposed the (wrong) proposal.
For SETTLE: Request B matched the (correct) proposal.

### Check A: Request Linkage (30-Case Audit)

For each of 30 previously audited cases, recovered the adapter's `requestTimestamp`
from `QuestionInitialized` events on Polygon. Compared with the DVM request's
timestamp (extracted from `oo_request_id`).

**Event signature discovery:** The Polymarket adapters emit
`QuestionInitialized(bytes32 indexed questionID, uint256 indexed requestTimestamp,
address indexed creator, bytes ancillaryData, address rewardToken, uint256 reward,
uint256 liveness)` — topic0 = `0xeee0897a...`. This differs from the generic UMA
adapter's 7-param signature (topic0 = `0x9501bedc...`).

| Result | Count | % |
|--------|-------|---|
| SAME_TIMESTAMP_QUESTIONID* | 26 | 87% |
| SAME timestamp, different questionID | 1 | 3% |
| DIFFERENT timestamp | 3 | 10% |

*Reclassified from "SAME" (R3) to `SAME_TIMESTAMP_QUESTIONID_UNVERIFIED_REQUEST`
(R4): initial timestamp matches DVM request, but active request at CTF resolution
time may differ due to `_reset()`. See "Framing" section below.

Note: the `oo_request_id` third field is the questionID (bytes32), not the full
ancillaryData. The adapter's QuestionInitialized event carries the full question
text as ancillaryData (decoded as ASCII "q: title: ..."). Full ancillaryData
comparison has not been performed.

**By audit group:**

| Group | SAME ts+qid | SAME ts only | DIFFERENT ts | Total |
|-------|-------------|--------------|--------------|-------|
| SETTLE_mismatch | 15 | 0 | 0 | 15 |
| RESET_mismatch | 6 | 1 | 3 | 10 |
| CONSISTENT_control | 5 | 0 | 0 | 5 |

**4 non-matching cases:**
- 0x034f: SAME timestamp but different questionID (0xd853 vs 0x7864) — UNCERTAIN
- 0x063f: 321s gap — near-match, explanation unclear
- 0x0cbc: -3083s (adapter 51 min AFTER DVM) — unusual ordering, 0 resets
- 0x0dea: 468,283s (130h/5.4 days gap) — multi-request, 0 resets

**Chronological verification (26 SAME ts+qid cases):**
- 26/26: QuestionInitialized block < CTF resolution block (init first)
- 26/26: QuestionReset block < CTF resolution block (reset before CTF)

**Sample composition note:** 21/26 timestamp-matching cases are CONSISTENT (15 SETTLE
+ 6 RESET after P1/P2 correction). Only 5 are DISAGREEMENT (controls). The
initial-timestamp match is well-established for CONSISTENT cases but has limited
DISAGREEMENT coverage (n=5, all controls).

### Framing: Request Identity Unresolved (R4)

Check A found that 26/30 cases share identical initial `requestTimestamp` AND
`questionID`. However, OOv2 contract review (R4) clarifies:

1. **OOv2 finality is absolute:** `requestPrice()` requires `Invalid` state.
   A settled request cannot accept new proposals on the same
   (requester, identifier, timestamp, ancillaryData) key.

2. **`_reset()` creates a new OO request:** The adapter's `_reset()` sets
   `questionData.requestTimestamp = block.timestamp` and calls `requestPrice()`
   with the new timestamp. This is a different OO key from the initial request.

3. **Check A recovered T₀, not T₁:** The `QuestionInitialized` timestamp is the
   initial request timestamp (T₀). After `QuestionReset`, the active timestamp
   changes to T₁ = block.timestamp of the reset transaction. Check A did not
   recover T₁.

4. **The 26 "SAME" labels are misleading:** The timestamp match reflects the
   initial request matching the DVM request, not the active request at CTF
   resolution time. These are reclassified as
   `SAME_TIMESTAMP_QUESTIONID_UNVERIFIED_REQUEST`.

5. **Sample composition note:** The 30-case sample was designed for the R2 audit
   (old inverted labels). After correction, 20/26 SAME cases are CONSISTENT and
   only 5 are DISAGREEMENT. The sample is not representative of the 1,355
   disagreement population.

### Confirmed Mechanism: Cross-Request (3-Case Post-Reset Audit, R4)

A 3-case deep dive examined the full tx receipt of each QuestionReset transaction.
Cases selected for adapter diversity (C1v2 + C3v4) and audit group diversity
(CONSISTENT_control, RESET_mismatch, SETTLE_mismatch).

**Key test:** Does the QuestionReset transaction emit a new OO `RequestPrice` event
with `requestTimestamp = T₁ = block.timestamp`?

| Case | Adapter | T₀ | T₁ | Gap | Reset tx has T₁ event? |
|------|---------|----|----|-----|----------------------|
| 0x000c (CONSISTENT/RESET) | C3v4 | 2026-03-07 | 2026-03-14 | 167h | YES |
| 0x03d9 (RESET_mismatch) | C1v2 | 2025-05-04 | 2025-05-06 | 63h | YES |
| 0x006f (SETTLE_mismatch) | C3v4 | 2026-07-01 | 2026-07-11 | 256h | YES |

**3/3 confirmed.** Every QuestionReset transaction contains:

1. An OOv2 event (4 topics) referencing T₀ — settling or disputing Request A
2. An OOv2 event (2 topics, topic0=`0xf1679315...`) referencing T₁ — new
   `RequestPrice` for Request B at `block.timestamp`
3. USDC transfers (bond movements)
4. The adapter's `QuestionReset` event

**OOv2 contract addresses identified:**
- C1v2 adapter → `0xeE3Afe347D5C74317041E2618C49534Daf887c24`
- C3v4 adapter → `0x2C0367A9dB231DdEBd88A94b4F6461A6E47C58b1`

**QuestionResolved tx does NOT contain T₀ or T₁ as explicit event parameters.**
The adapter's `_resolve()` calls `oo.settleAndGetPrice(identifier,
questionData.requestTimestamp, questionData.ancillaryData)` — it uses the stored
requestTimestamp (T₁ after reset) and ancillaryData as parameters to query OOv2,
not a pre-stored price. OOv2 returns Request B's settled price at call time.

```
Timeline (3/3 cases — confirmed steps marked ✓, inferred steps marked ~):

  ✓ QuestionInitialized: OO Request A at T₀
     |
  ✓ Request A: proposal disputed → DVM queue
     |
  ✓ QuestionReset tx (single atomic transaction):
     ├── ✓ OOv2: settle/dispute Request A (references T₀)
     ├── ✓ Adapter: _reset() → requestTimestamp = block.timestamp = T₁
     ├── ✓ OOv2: RequestPrice for Request B at T₁ (new OO key)
     ├── ✓ USDC: bond transfers
     └── ✓ Adapter: QuestionReset event
     |
  ✓ Request B: proposed undisputed, settled (price X)
     |  (R6: ProposePrice + Settle events recovered from OOv2 at T₁; disputer=0x0 in 3/3)
     |
  ✓ QuestionResolved + CTF Resolution (same block):
  ~ Adapter _resolve() calls oo.settleAndGetPrice(T₁) → gets Request B's price X → CTF payout(X)
     |  (inferred from contract code; supported by R6 price match: OOv2 Settle price == adapter price 3/3)
     |
  [Later] DVM resolves Request A → outcome may differ from X
  CTF already paid based on Request B → DISAGREEMENT if DVM(A) ≠ X
```

**What this proves (3 cases):** The `_reset()` → new OO request mechanism is
confirmed. Request B is created at T₁ in the same transaction as QuestionReset.

**What this does NOT prove:** That all 1,355 outcome disagreements are explained
by this mechanism. The 1,355 figure remains a **descriptive statistic** — the count
of conditions where CTF payout direction differs from the associated DVM outcome
direction. The cross-request mechanism is confirmed end-to-end in 3 Standard cases
and consistent with contract code, but not verified at population level.

**Linkage status (R6):** Request B's complete lifecycle — creation (RequestPrice),
proposal (ProposePrice), and settlement (Settle) — has been independently recovered
from OOv2 events for 3/3 Standard cases. OOv2's settled price matches the adapter's
QuestionResolved price in 3/3. See "Check C: Request B Settlement Recovery" below.

**Scope of interpretation:** The direction comparison (YES vs NO) is a binary
encoding of OO prices (0 → NO, 1e18 → YES). Special DVM outcomes (e.g.,
ignore price, too-early price) are not separately handled. The RESET label
means DVM rejected the disputed proposal — the "correct" direction is inferred
as opposite, which is a valid encoding for binary markets but should not be
read as an economic truth claim without qualification.

### Check B: NegRisk Separate Audit (15-Case, R5)

588 pre-DVM conditions use the NegRisk architecture (ctf_oracle = `0xd91e...`).
These have a two-level adapter structure absent from Standard (C1/C3) adapters:

```
OO request → requestId → NegRiskOperator QuestionPrepared → questionId → CTF conditionId
```

**Evidence chain per case (all on Polygon, chainid=137):**

1. **CTF ConditionPreparation** — conditionId → (oracle, questionId)
2. **NegRiskOperator QuestionPrepared** — questionId → (marketId, requestId)
3. **NegRiskOperator QuestionReported** — questionId → (requestId, result)
4. **NegRiskOperator QuestionResolved** — questionId → (result)
5. **NegRisk Adapter OutcomeReported** — (marketId, questionId) → outcome
6. **CTF ConditionResolution** — conditionId → payoutNumerators

**NegRisk contract addresses:**
- Adapter: `0xd91e80cf2e7be2e162c6513ced06f1dd0da35296`
- Operator: `0x71523d0f655b41e805cec45b17163f528b59b820`
- CTF: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`

**Purposive sample (15 cases, outcome-stratified):**

| Stratum | n | Selection criterion |
|---------|---|---------------------|
| RESET × INCONSISTENT | 5 | Disputed/reset + disagreement |
| SETTLE × INCONSISTENT | 5 | Settled (no reset) + disagreement |
| CONSISTENT controls | 3 | Agreement regardless of path |
| P3_UNKNOWN (special) | 2 | Unknown DVM outcome (direction comparison N/A; tests linkage only) |

**Results:**

| Check | Result |
|-------|--------|
| Full linkage reconstructed | **15/15** |
| CTF oracle == NegRisk adapter | **15/15** |
| Operator requestId == oo_request_id field | **15/15** |
| Operator result == CTF payout direction | **15/15** (0 mismatch) |
| CTF questionId == oo_questionID | **0/15** (by design) |

Per-stratum breakdown:

| Stratum | Linkage | Result match | Mismatch |
|---------|---------|-------------|----------|
| RESET_INC | 5/5 | 5 | 0 |
| SETTLE_INC | 5/5 | 5 | 0 |
| CONSISTENT | 3/3 | 3 | 0 |
| SPECIAL | 2/2 | 2 | 0 |

**Key architectural finding: dual-identifier mapping.**

The `oo_request_id` third field has different on-chain meanings per architecture:
- **Standard (C1/C3):** equals the adapter's `questionID` (which directly maps to
  CTF conditions via `ConditionPreparation.questionId`)
- **NegRisk:** equals the NegRiskOperator's `requestId` (OO-level), which is NOT
  the CTF `questionId`. These are different identifiers connected through
  `QuestionPrepared`:

- `requestId` = OO request level (matches oo_request_id)
- `questionId` = NegRisk/CTF level (matches CTF ConditionPreparation.questionId)
- `QuestionPrepared(marketId, questionId, requestId)` provides the mapping

This two-level mapping is by design. The NegRisk Operator's `prepareQuestion()`
creates the mapping; `reportPayouts()` uses requestId; `resolveQuestion()` uses
questionId. The CTF only sees questionId.

**Completion criteria** (user-specified, verbatim):
1. "15 个样本能否完整重建 request-to-condition linkage？"
2. "所谓 disagreement 是否主要来自不同 OO requests 或 question identifiers 的错误对应？"
3. "有没有 CTF payout 与其实际授权使用的 oracle price 不一致？"

**Answers (scoped to the 15 sampled cases):**

1. **Can 15 samples reconstruct full request-to-condition linkage?** YES — 15/15.
   The chain conditionId → Operator questionId → Operator requestId is fully
   recoverable from on-chain events (CTF ConditionPreparation + Operator
   QuestionPrepared). The Operator requestId matches the stored `oo_request_id`
   third field in 15/15 cases. The OO-request end is confirmed by matching the
   stored identifier, not independently re-recovered from OOv2 events.

2. **Are disagreements mainly from wrong request/question mapping?** Not in the
   15 sampled cases. Operator requestId matches oo_request_id; Operator result
   matches CTF payouts. No NegRisk mapping error detected. Whether the disagreement
   mechanism is cross-request (as in Standard architecture) was not directly tested
   in NegRisk — Request B was not traced for these cases.

3. **Is CTF payout inconsistent with its actually-authorized oracle price?** Not in
   the 15 sampled cases. The NegRiskOperator's reported result matches the CTF
   payout direction in 15/15. Note: "authorized" is verified via the Operator's
   QuestionReported event, not cross-checked against OOv2 settlement records.

**Timeline consistency (all 15 cases):**
- QuestionReported block < QuestionResolved block (1-hour delay period)
- QuestionResolved block == CTF ConditionResolution block (same transaction)
- Adapter OutcomeReported block == QuestionResolved block (same transaction)

### Check C: Request B Settlement Recovery (3-Case, R6)

For the same 3 Standard cases in the R4 post-reset audit, queried OOv2 on Polygon
for ProposePrice and Settle events where the adapter is the requester (topic1)
and the data timestamp equals T₁. This recovers Request B's complete lifecycle.

**OOv2 event signatures (from implementation ABI at `0x8c7556a4...`):**
- `ProposePrice(address indexed requester, address indexed proposer, bytes32 identifier,
  uint256 timestamp, bytes ancillaryData, int256 proposedPrice, uint256 expirationTimestamp,
  address currency)` — topic0 = `0x6e51dd00...`
- `Settle(address indexed requester, address indexed proposer, address indexed disputer,
  bytes32 identifier, uint256 timestamp, bytes ancillaryData, int256 price, uint256 payout)`
  — topic0 = `0x3f384afb...`

**Results:**

| Case | Propose tx | Proposer | Proposed | Settle tx | Settled | Disputer | Payout (USDC) | == Adapter price? |
|------|-----------|----------|----------|-----------|---------|----------|---------------|-------------------|
| 0x000c | `0xe578...` | `0x0db5...` | YES | `0xb75b...` | YES | 0x0 (none) | 752 | YES ✓ |
| 0x03d9 | `0x4e5a...` | `0xdcde...` | YES | `0xf4fc...` | YES | 0x0 (none) | 352 | YES ✓ |
| 0x006f | `0x0173...` | `0x86cc...` | NO | `0x182b...` | NO | 0x0 (none) | 755 | YES ✓ |

**Key findings:**

1. **OOv2 settled price == adapter QuestionResolved price: 3/3.** The price returned
   by `settleAndGetPrice(T₁)` matches OOv2's own settlement record.
2. **All 3 Request B proposals settled undisputed** (disputer = 0x0). No second
   dispute escalation occurred on any Request B.
3. **Identifier = YES_OR_NO_QUERY** (`0x5945535f4f525f4e...`) in all 3 Request B
   events. (Request A's identifier was not independently recovered in this check.)
4. **Different proposers per case:** `0x0db5...` (cases 0x000c), `0xdcde...`
   (0x03d9), `0x86cc...` (0x006f) — consistent with keeper bots proposing on
   new OO requests.
5. **Case 0x000c has 2 ProposePrice + 2 Settle events at T₁:** The query filters
   on requester (adapter) and timestamp (T₁) but not ancillaryData, so a second
   request from the same adapter at T₁ also appears. Both settled YES, so the
   price match holds regardless of which is the target condition's Request B.

**Evidence chain (3/3 Standard, confirmed steps ✓, inferred ~):**

```
✓ Request A created at T₀ (QuestionInitialized)
✓ Request A disputed → DVM queue
✓ _reset() creates Request B at T₁ (RequestPrice event in reset tx)
✓ Request B proposed undisputed (ProposePrice at T₁, from OOv2)
✓ Request B settled (Settle at T₁, from OOv2; price matches adapter)
~ Adapter _resolve() reads Request B price via settleAndGetPrice(T₁) → CTF resolution
     (inferred from contract code + price match; settleAndGetPrice call not independently observed)
✓ DVM later resolves Request A → outcome may differ
```

**Additional observation (R6):** The reset tx contains a DisputePrice event
(topic0 = `0x5165909c...`, 4 topics) referencing T₀ — this is Request A being
disputed/escalated to DVM within the same `_reset()` transaction. Previously
labeled as "settle/dispute" in R4; now identified as DisputePrice from the
implementation ABI.

### CTF 50-50 (71 cases)

The CTF resolved as [1,1] (ambiguous/unknown outcome). These are excluded from the
binary consistency check and analyzed separately.

## Methodology Notes

1. **Round-to-timestamp conversion:** DVM round boundaries computed as
   `round_id * ROUND_SECONDS (172,800)`. This is approximate — actual round
   timing may vary by a few seconds.

2. **Single-dispute only for pre-DVM:** All 1,998 pre-DVM conditions have exactly
   one dispute. Multi-dispute conditions are classified as DURING_DVM or AFTER_DVM.

3. **ConditionResolution decoding:** `questionId` is indexed (topic[3]), so data field
   starts with `outcomeSlotCount`. payoutNumerators decoded from ABI-encoded dynamic
   array in the data field.

4. **QuestionResolved decoding:** Event signature is
   `QuestionResolved(bytes32 indexed questionID, int256 indexed settledPrice, uint256[] payoutNumerators)`.
   `settledPrice` is in topic[2] (indexed int256), NOT in the data field. The data
   field contains only the `payoutNumerators` array.

5. **Direction mapping (corrected):** Uses YES/NO directly:
   - UMA price 0 → NO direction → CTF payout [0,1]
   - UMA price 1e18 → YES direction → CTF payout [1,0]
   - This matches `semantics.py` convention: P1=price(0)/payout[0,1], P2=price(1e18)/payout[1,0]
   - The R1 report used an inverted P1/P2 mapping from `ctf_direction()` which assigned
     [1,0]→P1 and [0,1]→P2, contradicting the authoritative convention.

6. **Consistency criterion:** For SETTLE (DVM confirms proposed): consistent if
   CTF direction == proposed direction. For RESET (DVM rejects proposed): consistent
   if CTF direction == opposite of proposed direction.

7. **QuestionInitialized decoding:** Polymarket adapters emit
   `QuestionInitialized(bytes32 indexed, uint256 indexed, address indexed, bytes,
   address, uint256, uint256)` — topic0 = `0xeee0897a...`. The `requestTimestamp`
   is in topic[2] (indexed uint256). This differs from the generic UMA adapter event
   (7 params, 1 indexed, topic0 = `0x9501bedc...`), which does not match on-chain.

8. **Audit scope:** 30-case audit (Check A) covers Standard architecture (1,410 of 1,998
   pre-DVM conditions). 15-case audit (Check B, R5) covers NegRisk architecture
   (588 conditions) with separate request-linking logic for the two-level adapter.
   3-case audit (Check C, R6) traces Request B's full OOv2 lifecycle (propose → settle)
   for Standard architecture, closing the settlement evidence gap.

9. **UNMATCHED skew:** Of 116 UNMATCHED conditions (no CTF resolution), 101 (87%)
   are SETTLE and only 15 are RESET. These may represent conditions that were never
   resolved on-chain despite having a settled OO request — possibly abandoned markets
   or conditions resolved through alternative mechanisms.

## Files Produced

All in `scratchpad/`:
- `ctf_resolutions.parquet` — Table 1: 3,132 CTF resolutions with timestamps
- `table2_oo_settlement_history.parquet` — Table 2: 3,713 OO settlement history rows
- `table3_timing_classification.parquet` — Table 3: 3,248 timing classifications
- `payout_consistency.parquet` — Q3: 1,998 payout consistency (ORIGINAL, P1/P2 inverted)
- `payout_consistency_fixed.parquet` — Q3: 1,998 payout consistency (CORRECTED)
- `conflict_audit_results.json` — 30-case audit: tx receipt event decoding
- `check_a_request_linkage.json` — Check A: 30-case request timestamp comparison
- `post_reset_audit.json` — R4: 3-case post-reset tx receipt analysis
- `check_b_sample.json` — Check B: 15-case NegRisk stratified sample
- `check_b_results.json` — Check B: 15-case NegRisk audit results with full linkage
- `request_b_settlement.json` — Check C (R6): 3-case Request B lifecycle (propose + settle)

## Completed Audit Steps

1. ~~3-case post-reset request-key audit~~ — **DONE (R4).** Confirmed cross-request
   mechanism in 3/3 cases. T₁ matches new OO RequestPrice in all reset txs.
2. ~~Check B: NegRisk separate audit (15 cases)~~ — **DONE (R5).** 15/15 linkage
   reconstructed. Operator result == CTF payout in all cases. NegRisk dual-identifier
   architecture (requestId ≠ questionId) verified. No oracle inconsistency found.
3. ~~Recover Request B settlement~~ — **DONE (R6).** ProposePrice + Settle events
   recovered from OOv2 at T₁ for 3/3 Standard cases. OOv2 settled price matches
   adapter's QuestionResolved price. All 3 settled undisputed (disputer=0x0).
4. ~~USDC unit validation~~ — **DONE (R7).** `usdc_amount()` in `semantics.py` +
   8 tests in `test_ci.py`. Prevents repeat of 10^9 vs 10^6 decimal error.

## Deferred / Not Pursued

- **`oo_settlement_timestamp` release field** — Priority 3 (next). Requires defining
  observation unit: OO request-level vs CTF condition-level settlement time.
- **Scaling Check A** — the 30-case timestamp match is necessary but insufficient.
  Scaling to 1,410 would repeat the same limitation.
- **3 DIFFERENT timestamp cases** — especially case 3 (130h gap, 0 resets)
- **116 UNMATCHED conditions** — why no ConditionResolution event?
- **NegRisk Request B lifecycle tracing** — Check B mapping suffices for current scope.
- **Full collateral reconstruction** — separate workstream, deferred.
