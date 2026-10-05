# Adversarial on-chain validation audit -- v1.0.0

**Date:** 2026-10-05 01:24 UTC
**Seed:** 20261004
**Method:** field-level decoding of on-chain VoteRevealed and RequestResolved events

## Summary

- **31 cases** across 9 strata
- **28 DVM-linked** cases verified, 3 PRE_VOTING_V2
- **200 ballot events** decoded from tx receipts: 200 field-matched, 0 mismatched/error
- **1800 field comparisons** across all decoded ballots, 0 mismatched
- **28 resolution events** verified: 28 price+round matched
- **40 rounds** across all audited cases (cross-checked against n_rounds in dvm_requests)

Fields compared per ballot (9): `voter`, `caller`, `price` (int256), `numTokens` (uint256),
`roundId`, `blockNumber`, `identifier` (bytes32), `time` (request identity), `ancillaryData` (request identity).
Fields compared per resolution: `price` (int256), `roundId`. Resolution log matched by identifier + time + ancillaryData.

## Strata

| stratum | N | intent |
|---|---:|---|
| oov2_single_round | 5 | baseline OO -> DVM identity |
| managed_single_round | 5 | Managed OOV2 linkage |
| rolled_multi_round | 5 | multi-round ballot coverage |
| p4_too_early | 4 | int256.min semantic decoding + RESET |
| multi_request_condition | 4 | request generation not collapsed |
| regime_boundary | 3 | OOV2 -> Managed transition edge |
| pre_voting_v2 | 3 | version boundary, timestamp verified pre-VotingV2 |
| high_ballot_count | 1 | large ballot set precision |
| low_ballot_count | 1 | small-N edge case |

## Per-case results

### [PASS] YES_OR_NO_QUERY-1720259833-0x6e5e112a81833a372629a0a2641b446
- stratum: `oov2_single_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1720267815-0x713a207469746c653a2057686f20776`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 90, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=9956, tx=0x354408470411154c...)

### [PASS] YES_OR_NO_QUERY-1719446735-0xd8e539895dd5f2adf71c413608c8ea9
- stratum: `oov2_single_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1719540306-0x713a207469746c653a2044656261746`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 86, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=9952, tx=0xa403b3e0eb69cfbd...)

### [PASS] YES_OR_NO_QUERY-1733779906-0xacc81aba8dbcbb6116c79367c25f252
- stratum: `oov2_single_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1734966489-0x713a207469746c653a2057696c6c204`
- resolved: P1 (raw=0)
- ballots: 424, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=0, round=10041, tx=0xf95d4d4a8c334857...)

### [PASS] YES_OR_NO_QUERY-1746658896-0xfe98d3cb5fba915525da572489284db
- stratum: `oov2_single_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1746833061-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 198, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10110, tx=0xfe5f093b5941adf3...)

### [PASS] YES_OR_NO_QUERY-1695233375-0x7419c97370a5faf09c4baf3e2ed2492
- stratum: `oov2_single_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1701740087-0x713a207469746c653a2047544120362`
- resolved: P2 (raw=1000000000000000000)
- ballots: 68, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=9849, tx=0x052a9f310b80fba6...)

### [PASS] YES_OR_NO_QUERY-1778334981-0xe7e36b0edde5e19f0f913b0cfe8c64d
- stratum: `managed_single_round`
- oo_contract: MANAGED_OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1780759351-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 583, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10306, tx=0x6a5b991b8a3584d4...)

### [PASS] YES_OR_NO_QUERY-1778022020-0x1d2310a55fb5ef471bd5735d4617bbe
- stratum: `managed_single_round`
- oo_contract: MANAGED_OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1778083479-0x616e63696c6c6172794461746148617`
- resolved: P1 (raw=0)
- ballots: 353, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=0, round=10290, tx=0xbf46ad4d63ad5022...)

### [PASS] YES_OR_NO_QUERY-1771247447-0x0980e1cb8bb6accc07f56a00d365a6a
- stratum: `managed_single_round`
- oo_contract: MANAGED_OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1771557590-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 661, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10253, tx=0xd188420c80f77b2e...)

### [PASS] YES_OR_NO_QUERY-1777403068-0x6f35fe445c46dde5fb234597521b7a9
- stratum: `managed_single_round`
- oo_contract: MANAGED_OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1781598631-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 559, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10311, tx=0xfc9f8d72fa84cc9c...)

### [PASS] YES_OR_NO_QUERY-1769203394-0xee8f6e94c3bd6091fc8f7934d4d956f
- stratum: `managed_single_round`
- oo_contract: MANAGED_OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1770599779-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 452, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10247, tx=0xc16e26aa2c58bc25...)

### [PASS] YES_OR_NO_QUERY-1761082541-0x3c4d1dd7aeba90b79ae176d5ef0ec63
- stratum: `rolled_multi_round`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1762002731-0x616e63696c6c6172794461746148617`
- resolved: P1 (raw=0)
- ballots: 736, rounds: 2, roll_count: 1
- ballot spot-check: **10/10** events field-matched (90 fields compared)
- round count: PASS (2 rounds in ballots, n_rounds=2)
- resolution: PASS (chain_price=0, round=10198, tx=0xc68204dc85609d70...)

### [PASS] YES_OR_NO_QUERY-1758654991-0xa00d6c774b99c7dc8a98885a38760ea
- stratum: `rolled_multi_round`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1759784402-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 1717, rounds: 3, roll_count: 2
- ballot spot-check: **15/15** events field-matched (135 fields compared)
- round count: PASS (3 rounds in ballots, n_rounds=3)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10187, tx=0xed940a93ae98ec45...)

### [PASS] YES_OR_NO_QUERY-1754454719-0x36479210450fd601aec0b57320d5d25
- stratum: `rolled_multi_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1754795199-0x616e63696c6c6172794461746148617`
- resolved: P1 (raw=0)
- ballots: 980, rounds: 4, roll_count: 3
- ballot spot-check: **20/20** events field-matched (180 fields compared)
- round count: PASS (4 rounds in ballots, n_rounds=4)
- resolution: PASS (chain_price=0, round=10159, tx=0xb647e149b121dbf0...)

### [PASS] YES_OR_NO_QUERY-1712459681-0xcc0cf893c080914eb02f9c4265ad081
- stratum: `rolled_multi_round`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1719407590-0x713a207469746c653a2057696c6c206`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 257, rounds: 3, roll_count: 2
- ballot spot-check: **15/15** events field-matched (135 fields compared)
- round count: PASS (3 rounds in ballots, n_rounds=3)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=9953, tx=0xf2a7d7546b9a592a...)

### [PASS] YES_OR_NO_QUERY-1753376328-0xe6fc21249e08ddfc69bc5427efaa6ab
- stratum: `rolled_multi_round`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1753502405-0x616e63696c6c6172794461746148617`
- resolved: P2 (raw=1000000000000000000)
- ballots: 422, rounds: 2, roll_count: 1
- ballot spot-check: **10/10** events field-matched (90 fields compared)
- round count: PASS (2 rounds in ballots, n_rounds=2)
- resolution: PASS (chain_price=1000000000000000000, round=10149, tx=0xad4fedf4b5378a71...)

### [PASS] YES_OR_NO_QUERY-1749508861-0x89179b36af27a0fc068160182b76fc4
- stratum: `p4_too_early`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1750118689-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 284, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10129, tx=0x3b7b640cd8227e77...)

### [PASS] YES_OR_NO_QUERY-1771945638-0x2deb41cbba7414f443f6b2c9591a94f
- stratum: `p4_too_early`
- oo_contract: MANAGED_OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1773038517-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 637, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10261, tx=0x9fd9491989867fb6...)

### [PASS] YES_OR_NO_QUERY-1778358912-0x8bc9027b23d6c3355a7d087d3f2f4ee
- stratum: `p4_too_early`
- oo_contract: MANAGED_OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1778634161-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 579, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10294, tx=0xe6dae6657f486f00...)

### [PASS] YES_OR_NO_QUERY-1730477228-0xfc44006ca290702d981782ed4796109
- stratum: `p4_too_early`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1730522938-0x713a207469746c653a2043656c74696`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 436, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10015, tx=0x7cc9da72d5d0a1d1...)

### [PASS] YES_OR_NO_QUERY-1750869573-0x3c9e14b38d8bced615c4610841419a5
- stratum: `multi_request_condition`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1750880454-0x616e63696c6c6172794461746148617`
- resolved: P2 (raw=1000000000000000000)
- ballots: 284, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=10133, tx=0x1c0282dd9118600f...)

### [PASS] YES_OR_NO_QUERY-1752596076-0xe4e10666dd9f8dfd82a20311f903bf4
- stratum: `multi_request_condition`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1753941461-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 254, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10151, tx=0xe7877732b2c45a08...)

### [PASS] YES_OR_NO_QUERY-1716493645-0x451d786bd0189ae3c30bacaf637ee1e
- stratum: `multi_request_condition`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1716687509-0x713a207469746c653a2057696c6c204`
- resolved: P2 (raw=1000000000000000000)
- ballots: 76, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=9935, tx=0x4ecd439f6b4a354a...)

### [PASS] YES_OR_NO_QUERY-1738613595-0x96bfe57cfa7b5373eaf8fd307993960
- stratum: `multi_request_condition`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1742680702-0x713a207469746c653a20556b7261696`
- resolved: P2 (raw=1000000000000000000)
- ballots: 510, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=10085, tx=0x9de6a2dd7cb1192a...)

### [PASS] YES_OR_NO_QUERY-1753204152-0xee4b22cf9dcb7d9cbd2804f1c46940b
- stratum: `regime_boundary`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1756074631-0x616e63696c6c6172794461746148617`
- resolved: P1 (raw=0)
- ballots: 270, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=0, round=10163, tx=0x942b00f53099ca8a...)

### [PASS] YES_OR_NO_QUERY-1743019781-0xa1470db7546a10f0185f9c6aeb8c041
- stratum: `regime_boundary`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1755674409-0x616e63696c6c6172794461746148617`
- resolved: P2 (raw=1000000000000000000)
- ballots: 194, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=10161, tx=0xea5d9c69424301b2...)

### [PASS] YES_OR_NO_QUERY-1756119417-0xd435e7f9dd62bf3c6a32ad736260358
- stratum: `regime_boundary`
- oo_contract: OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1756293857-0x616e63696c6c6172794461746148617`
- resolved: P4_TOO_EARLY (raw=-57896044618658097711785492504343953926634992332820282019728792003956564819968)
- ballots: 779, rounds: 3, roll_count: 2
- ballot spot-check: **15/15** events field-matched (135 fields compared)
- round count: PASS (3 rounds in ballots, n_rounds=3)
- resolution: PASS (chain_price=-57896044618658097711785492504343953926634992332820282019728792003956564819968, round=10166, tx=0x4fb7dd43e130578f...)

### [PASS] YES_OR_NO_QUERY-1778990666-0x4695b89ddb81ff47d1dcaf1de7ac9e0
- stratum: `high_ballot_count`
- oo_contract: MANAGED_OOV2, architecture: NEGRISK
- dvm_request_id: `YES_OR_NO_QUERY-1779234469-0x616e63696c6c6172794461746148617`
- resolved: P1 (raw=0)
- ballots: 1164, rounds: 2, roll_count: 1
- ballot spot-check: **10/10** events field-matched (90 fields compared)
- round count: PASS (2 rounds in ballots, n_rounds=2)
- resolution: PASS (chain_price=0, round=10298, tx=0x9876203d4a600a73...)

### [PASS] YES_OR_NO_QUERY-1683746410-0x4032dd7140c7cf9b9ec86cf4187f56e
- stratum: `low_ballot_count`
- oo_contract: OOV2, architecture: STANDARD
- dvm_request_id: `YES_OR_NO_QUERY-1686660186-0x713a207469746c653a2057696c6c205`
- resolved: P2 (raw=1000000000000000000)
- ballots: 64, rounds: 1, roll_count: 0
- ballot spot-check: **5/5** events field-matched (45 fields compared)
- round count: PASS (1 rounds in ballots, n_rounds=1)
- resolution: PASS (chain_price=1000000000000000000, round=9761, tx=0x4f30d471321fa57c...)

### [PASS] YES_OR_NO_QUERY-1672249334-0xa900bf2ada6ac60d324488464b0cbed
- stratum: `pre_voting_v2`
- oo_contract: OOV2, architecture: STANDARD
- Pre-VotingV2 dispute (ts=1672439560, before VotingV2 start=1678591726)

### [PASS] YES_OR_NO_QUERY-1677294550-0x79dc2af696825da90ce6c52a3d2a1e4
- stratum: `pre_voting_v2`
- oo_contract: OOV2, architecture: STANDARD
- Pre-VotingV2 dispute (ts=1677306797, before VotingV2 start=1678591726)

### [PASS] YES_OR_NO_QUERY-1677097718-0xdbf7c79caec1c4908ca047c57a3b8ed
- stratum: `pre_voting_v2`
- oo_contract: OOV2, architecture: STANDARD
- Pre-VotingV2 dispute (ts=1677312039, before VotingV2 start=1678591726)

## Conclusion

31/31 audited cases passed.

28 VotingV2 cases were verified against on-chain adjudication records; 3 pre-VotingV2 cases were independently confirmed to predate the VotingV2 deployment boundary.

- 200/200 sampled ballot events matched on all 9 fields (voter, caller, price, numTokens, roundId, block, identifier, time, ancillaryData).
- 1800 individual field comparisons, 0 mismatched.
- 28/28 resolution events matched on price and roundId (log found by identifier + time + ancillaryData).

**Audit: PASS**

This audit is independent of C1-C10 automated validation. It verifies that the
frozen release parquets faithfully reproduce raw on-chain event data, not just that
they are internally consistent.