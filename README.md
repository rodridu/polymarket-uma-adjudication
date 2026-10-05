# Polymarket–UMA Adjudication Data

A reproducible, versioned reconstruction of Polymarket-linked UMA adjudication,
connecting disputed market cases to Optimistic Oracle requests, VotingV2 rounds,
and individual revealed ballots.

> 4,264 cases · 4,261 DVM requests · 467 rounds · 2,053,728 revealed ballots · 6,992 voter addresses
>
> Case coverage: Dec 2022–Aug 2026. VotingV2 ballot coverage: Mar 2023–Aug 2026.

```
Polymarket condition
        │
        ▼
   OO dispute (Polygon)
        │
        ▼
   DVM request (mainnet)
        │
        ├── round 1 ── ballots
        │
        └── round 2 ── ballots
                │
                ▼
           resolution
```

## Quick start

```bash
pip install -e .                # installs pmvotes + dependencies
cp .env.example .env            # ETHERSCAN_API_KEY, GRAPH_GATEWAY_API_KEY, MAINNET_RPC_URL, POLYGON_RPC_URL
python scripts/01_prepare_oo_disputes.py --oo OOV2=<oov2.parquet> --oo MANAGED_OOV2=<managed.parquet>
python scripts/02_pull_dvm_requests.py
python scripts/03_link_oo_to_dvm.py
python scripts/04_pull_votes.py
python scripts/05_pull_round_state.py
python scripts/06_build_release.py
python scripts/07_validate_release.py   # must print RELEASE OK
```

For exact v1.0.0 reproduction: `pip install -r requirements-lock.txt && pip install -e . --no-deps`.

## Data tables

| file | one row per |
|---|---|
| `cases.parquet` | disputed OO request on a Polymarket binary adapter |
| `dvm_requests.parquet` | DVM request linked to a case, with resolution |
| `rounds.parquet` | VotingV2 round holding a linked ballot |
| `ballots.parquet` | `VoteRevealed` event for a linked request |
| `crosswalk.parquet` | case-level join keys for interoperability |

Counts, coverage window, and file hashes: `release/manifest.json`.

## Joining other datasets

See [`docs/JOINING.md`](docs/JOINING.md) to attach ballot-level DVM adjudication to existing
market, trading, oracle, and settlement datasets.
[`release/crosswalk.parquet`](release/crosswalk.parquet) is a lightweight join table (<1.5 MB)
for testing compatibility before pulling the full dataset.

## Documentation

| doc | answers |
|---|---|
| [`CONSTRUCTION.md`](docs/CONSTRUCTION.md) | How was it built? |
| [`DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) | What do the columns mean? |
| [`JOINING.md`](docs/JOINING.md) | How do I join it with other data? |
| [`VALIDATION.md`](docs/VALIDATION.md) | How was it validated? |
| [`limitations.md`](docs/limitations.md) | What can't I infer from this data? |
| [`PROVENANCE.md`](docs/PROVENANCE.md) | Where did this release come from? |

## License

Code: MIT. Data: research release — source records keep their original terms.
See [`LICENSE-DATA.md`](LICENSE-DATA.md).

## Citation

See [`CITATION.cff`](CITATION.cff). GitHub renders a "Cite this repository" button from it.
