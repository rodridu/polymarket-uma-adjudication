# Joining with other Polymarket datasets

Existing datasets cover market metadata, trading, oracle lifecycle events, protocol resolution,
and redemption. This release adds the **ballot-level interior of DVM adjudication** — the
collective decision process between dispute escalation and oracle resolution.

```
dispute → [ round → voters → weights → revealed values → rolls ] → oracle resolution
           └──────────────── this release ────────────────────┘
```

### Upstream compatibility

Compatibility verified against:

- Jia et al., arXiv:2604.20421v2, 2026-09-25
- Nechepurenko Part I, arXiv:2609.15368v1, 2026-09-14
- Nechepurenko Part II, arXiv:2609.15373v1, 2026-09-14

See also `registry/upstream_compatibility.yaml`.

```
Jia et al.                    this release                   Nechepurenko
──────────────                ────────────                   ────────────
Market (M)                    cases                          ConditionPreparation
  condition_id  ───────────►    condition_id                   condition_id
  question_id   ───────────►    question_id                   question_id
Oracle Events (O)             dvm_requests
  condition_id  ───────────►    condition_id
  request_id    ───────────►    oo_request_id               ConditionResolution
                              rounds                          condition_id
OrderFilled (F)               ballots                       PayoutRedemption
  condition_id  ───────────►    condition_id                   condition_id
```

## Identifier formats

All identifiers in this release use lowercase hex with `0x` prefix. Normalize before joining.

| column | format | example | length |
|---|---|---|---|
| `condition_id` | `0x` + 64 hex chars | `0xf6143ad3ce7b1f3...` | 66 |
| `question_id` | `0x` + 64 hex chars | `0xa900bf2ada6ac60...` | 66 |
| `adapter_address` | `0x` + 40 hex chars | `0x6a9d222616c90f...` | 42 |
| `dvm_request_id` | `<identifier>-<time>-0x<ancillary prefix>` | `YES_OR_NO_QUERY-1720267815-0x713a2...` | variable |
| `round_id` | integer | `9956` | — |

## Join 1: Jia et al. → this release

**Source:** Jia, "Unlocking the Forecasting Economy" (arXiv:2604.20421). Market metadata, trades,
and oracle lifecycle events for Polymarket.

### By condition

```python
# Jia's Market table → our cases
jia_markets.merge(cases, on="condition_id", how="inner")

# Then reach ballots through dvm_request_id
cases.merge(ballots, on="dvm_request_id", how="inner")
```

`condition_id` is the preferred direct join key where available. Both datasets use the CTF
condition ID (`bytes32`, lowercase hex). Jia's Market table (M) and Oracle Events table (O)
both carry it.

**Join key ≠ unit of observation.** Three granularities exist:

| grain | key | note |
|---|---|---|
| contract-level | `condition_id` | preferred for market/settlement joins; null for 427 unverified NegRisk v4 cases |
| question-level | `question_id` | available even when condition_id is null; one condition can have multiple questions in NEGRISK |
| adjudication-level | `dvm_request_id` / OO request identity | unique per dispute attempt; the unit of this release |

A Polymarket condition can generate multiple disputed OO requests (reset → re-proposal →
second dispute). Our `cases` table has one row per dispute, with `dispute_seq_in_condition`
disambiguating. Join on `condition_id` alone may fan out; add
`dispute_seq_in_condition == 1` for the first dispute per condition.

**Shortcut:** `release/crosswalk.parquet` is a lightweight join table (one row per case,
10 columns, ~1.4 MB) that lets you test compatibility before pulling the full 2M-ballot dataset.

### By trade → ballot

To connect an individual trade to the adjudication that decided its condition:

```python
# 1. Jia trade → condition
trade_condition = jia_fills.merge(jia_markets[["matched_market_id", "condition_id"]],
                                  on="matched_market_id")

# 2. condition → DVM request → ballots
trade_ballots = (trade_condition
    .merge(cases[["condition_id", "dvm_request_id"]], on="condition_id")
    .merge(ballots, on="dvm_request_id"))
```

## Join 2: this release → Nechepurenko

**Source:** Nechepurenko, "Automated Decoding of Polymarket Oracle Adjudication" (arXiv:2609.15368)
and "Protocol Finality and Redemption" (arXiv:2609.15373). Oracle lifecycle events and CTF
settlement/redemption.

### By condition

```python
# Our cases → Nechepurenko's ConditionResolution
cases.merge(nech_resolution, on="condition_id", how="inner")
```

`condition_id` and `question_id` are shared. Nechepurenko's oracle events use
`adapter_address + question_id` as stable identifiers for question-level matching.

### Resolution cross-check

Our `dvm_requests.resolved_price_raw` is the VotingV2-layer resolution (what DVM voters decided).
Nechepurenko's `ConditionResolution.payout_numerators` is the CTF-layer resolution (what the
adapter wrote to the CTF contract). These are related but not identical:

- UMA price `0` (P1) → CTF payout `[0, 1]`
- UMA price `1e18` (P2) → CTF payout `[1, 0]`
- UMA price `int256.min` (P4) → adapter resets the question (no CTF resolution)

Our `resolved_ctf_payout` column translates the UMA price to the expected CTF payout, which
should match Nechepurenko's `payout_numerators` for resolved cases.

## Join 3: full pipeline (Jia → this release → Nechepurenko)

```python
# Market trades + DVM adjudication interior + protocol settlement
full = (jia_fills
    .merge(jia_markets[["matched_market_id", "condition_id"]], on="matched_market_id")
    .merge(cases[["condition_id", "dvm_request_id", "dvm_link_status"]],
           on="condition_id")
    .merge(dvm_requests[["dvm_request_id", "resolved_price_raw", "resolved_uma_value_class",
                          "n_ballots", "n_rounds", "roll_count"]],
           on="dvm_request_id")
    .merge(nech_resolution[["condition_id", "payout_numerators"]],
           on="condition_id", how="left"))
```

## What this release uniquely provides

They reconstruct the lifecycle. We reconstruct the collective decision inside one lifecycle
transition. Ballot- and round-level fields below are not represented in the published schemas
documented by Jia et al. or Nechepurenko:

| layer | source | what it adds |
|---|---|---|
| **rounds** | VotingV2 `rounds(id)` | round timing, quorum thresholds, cumulative stake |
| **ballots** | VotingV2 `VoteRevealed` | individual voter, weight, price, delegation (`caller`) |
| **roll history** | ballot round IDs vs resolution round | which rounds failed quorum/agreement |

## Adapters in this release

| adapter_address | architecture | oo_contract | cases |
|---|---|---|---:|
| `0x6a9d...f74` | STANDARD | OOV2 | 725 |
| `0x2f5e...9d` | NEGRISK | OOV2 | 1,015 |
| `0x157c...a49` | STANDARD | OOV2 | 110 |
| `0x6507...a7` | STANDARD | MANAGED_OOV2 | 1,987 |
| `0x69c4...e24` | NEGRISK | MANAGED_OOV2 | 427 |

Jia and Nechepurenko may identify adapters by `oracle_address` or `source_contract`. The
`adapter_address` column here is the OO requester on Polygon (the UmaCtfAdapter instance),
not the OO contract itself.

## Gotchas

1. **`condition_id` nulls.** 427 cases have `condition_id_status = OPERATOR_PROVENANCE_UNVERIFIED`
   (NegRisk v4 where the operator mapping is unconfirmed). These have null `condition_id` and
   cannot be joined by condition. They can still be joined by `question_id` if the other dataset
   carries it.

2. **PRE_VOTING_V2 cases** (3 rows) have `dvm_link_status = PRE_VOTING_V2`. They predate
   VotingV2 and have no ballots or DVM request in this release. They will not appear in any
   ballot-level join.

3. **Fan-out on condition.** A condition with multiple disputes produces multiple `cases` rows.
   Filter `dispute_seq_in_condition == 1` for the canonical first dispute, or keep all for
   re-dispute analysis.

4. **Hex normalization.** This release uses lowercase `0x`-prefixed hex throughout. Other datasets
   may use checksummed (mixed-case) or un-prefixed hex. Normalize with:
   ```python
   df["condition_id"] = df["condition_id"].str.lower().str.strip()
   ```
