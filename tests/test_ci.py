"""CI-safe tests that run without release parquets.

These verify package structure, semantics, registry schemas, and basic
invariants on committed mini fixtures. Full 2M-row regression is in
test_regression.py (skipped in CI when release parquets are absent).
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
import yaml

MINI = Path(__file__).resolve().parent / "fixtures" / "mini_release"
MINI_TABLES = {
    name: pd.read_parquet(MINI / f"{name}.parquet")
    for name in ("cases", "dvm_requests", "rounds", "ballots", "crosswalk")
}
_COMMIT_LAYER_NAMES = ("commits", "participation", "voter_request_incentives")
_HAS_COMMIT_LAYER = all((MINI / f"{n}.parquet").exists() for n in _COMMIT_LAYER_NAMES)
if _HAS_COMMIT_LAYER:
    for n in _COMMIT_LAYER_NAMES:
        MINI_TABLES[n] = pd.read_parquet(MINI / f"{n}.parquet")


class TestPackageImport:
    def test_root_resolves(self):
        from pmvotes import ROOT
        assert (ROOT / "pyproject.toml").exists()

    def test_release_resolves(self):
        from pmvotes import RELEASE
        assert RELEASE.is_dir()

    def test_raw_path_shape(self):
        from pmvotes import RAW, ROOT
        assert RAW == ROOT / "data" / "raw"


class TestSemantics:
    def test_p1(self):
        from pmvotes.semantics import classify
        cls, payout, effect = classify(0)
        assert cls == "P1"
        assert payout == "[0,1]"
        assert effect == "SETTLE"

    def test_p2(self):
        from pmvotes.semantics import classify
        cls, payout, effect = classify(10**18)
        assert cls == "P2"
        assert payout == "[1,0]"
        assert effect == "SETTLE"

    def test_p4_too_early(self):
        from pmvotes.semantics import classify
        cls, _, effect = classify(-(2**255))
        assert cls == "P4_TOO_EARLY"
        assert effect == "RESET"

    def test_nonstandard(self):
        from pmvotes.semantics import classify
        cls, _, effect = classify(42)
        assert cls == "NONSTANDARD"
        assert effect == "ADAPTER_REVERT"

    def test_signed256(self):
        from pmvotes.semantics import signed256
        assert signed256(0) == 0
        assert signed256(2**255) == -(2**255)
        assert signed256(2**256 - 1) == -1


class TestRegistrySchemas:
    def test_adapters_yaml_parses(self):
        from pmvotes import ROOT
        with open(ROOT / "registry" / "adapters.yaml") as f:
            data = yaml.safe_load(f)
        assert "adapters" in data
        for a in data["adapters"]:
            assert "address" in a
            assert "architecture" in a

    def test_oracle_deployments_yaml_parses(self):
        from pmvotes import ROOT
        with open(ROOT / "registry" / "oracle_deployments.yaml") as f:
            data = yaml.safe_load(f)
        assert "oracles" in data

    def test_voting_contracts_yaml_parses(self):
        from pmvotes import ROOT
        with open(ROOT / "registry" / "voting_contracts.yaml") as f:
            data = yaml.safe_load(f)
        assert "voting_contracts" in data


INT_RE = re.compile(r"^-?\d+$")


class TestMiniFixtureInvariants:
    """C1, C2, C7 on committed mini fixtures."""

    def test_c1_cases_pk(self):
        assert not MINI_TABLES["cases"]["oo_request_id"].duplicated().any()

    def test_c1_dvm_pk(self):
        assert not MINI_TABLES["dvm_requests"]["dvm_request_id"].duplicated().any()

    def test_c1_rounds_pk(self):
        assert not MINI_TABLES["rounds"]["round_id"].duplicated().any()

    def test_c1_ballots_pk(self):
        b = MINI_TABLES["ballots"]
        assert not b.duplicated(subset=["dvm_request_id", "round_id", "voter"]).any()

    def test_c2_ballot_request_exists(self):
        ballot_ids = set(MINI_TABLES["ballots"]["dvm_request_id"])
        dvm_ids = set(MINI_TABLES["dvm_requests"]["dvm_request_id"])
        assert ballot_ids <= dvm_ids

    def test_c2_ballot_round_exists(self):
        ballot_rounds = set(MINI_TABLES["ballots"]["round_id"])
        round_ids = set(MINI_TABLES["rounds"]["round_id"])
        assert ballot_rounds <= round_ids

    def test_c2_dvm_request_has_case(self):
        dvm_ids = set(MINI_TABLES["dvm_requests"]["dvm_request_id"])
        case_dvm_ids = set(MINI_TABLES["cases"]["dvm_request_id"].dropna())
        assert dvm_ids <= case_dvm_ids

    def test_c7_raw_integers(self):
        for col in ["bond_raw", "proposed_price_raw"]:
            vals = MINI_TABLES["cases"][col].dropna()
            assert all(INT_RE.match(str(v)) for v in vals), f"{col} has non-integer"

        for col in ["resolved_price_raw"]:
            vals = MINI_TABLES["dvm_requests"][col].dropna()
            assert all(INT_RE.match(str(v)) for v in vals), f"{col} has non-integer"

        for col in ["price_raw", "num_tokens_raw"]:
            vals = MINI_TABLES["ballots"][col].dropna()
            assert all(INT_RE.match(str(v)) for v in vals), f"{col} has non-integer"

    def test_crosswalk_matches_cases(self):
        xw_ids = set(MINI_TABLES["crosswalk"]["oo_request_id"])
        case_ids = set(MINI_TABLES["cases"]["oo_request_id"])
        assert xw_ids == case_ids

    def test_pre_voting_v2_has_no_dvm(self):
        pre = MINI_TABLES["cases"][
            MINI_TABLES["cases"]["dvm_link_status"] == "PRE_VOTING_V2"
        ]
        assert len(pre) == 1
        assert pre["dvm_request_id"].isna().all()

    def test_fixture_nonempty(self):
        assert len(MINI_TABLES["cases"]) == 4
        assert len(MINI_TABLES["dvm_requests"]) == 3
        assert len(MINI_TABLES["rounds"]) == 3
        assert len(MINI_TABLES["ballots"]) == 621
        assert len(MINI_TABLES["crosswalk"]) == 4


_skip_commit = pytest.mark.skipif(not _HAS_COMMIT_LAYER,
                                  reason="commit-layer mini fixtures not present")


@_skip_commit
class TestCommitLayerMiniFixtures:
    """C11-C13, C15 on committed mini fixtures (when present)."""

    def test_c11_commits_pk(self):
        cm = MINI_TABLES["commits"]
        assert not cm.duplicated(subset=["dvm_request_id", "round_id", "voter",
                                          "tx_hash", "log_index"]).any()

    def test_c11_participation_pk(self):
        pt = MINI_TABLES["participation"]
        assert not pt.duplicated(subset=["dvm_request_id", "round_id", "voter"]).any()

    def test_c11_incentives_pk(self):
        vi = MINI_TABLES["voter_request_incentives"]
        assert not vi.duplicated(subset=["voter", "dvm_request_id"]).any()

    def test_c12_commit_request_exists(self):
        commit_ids = set(MINI_TABLES["commits"]["dvm_request_id"])
        dvm_ids = set(MINI_TABLES["dvm_requests"]["dvm_request_id"])
        assert commit_ids <= dvm_ids

    def test_c12_participation_round_exists(self):
        part_rounds = set(MINI_TABLES["participation"]["round_id"])
        round_ids = set(MINI_TABLES["rounds"]["round_id"])
        assert part_rounds <= round_ids

    def test_c13_reveal_subset_of_commit(self):
        b = MINI_TABLES["ballots"]
        cm = MINI_TABLES["commits"]
        revealed = set(zip(b["dvm_request_id"], b["round_id"], b["voter"]))
        committed = set(zip(cm["dvm_request_id"], cm["round_id"], cm["voter"]))
        assert revealed <= committed

    def test_c15_slashed_tokens_raw_integers(self):
        vi = MINI_TABLES["voter_request_incentives"]
        vals = vi["slashed_tokens_raw"].dropna()
        assert all(INT_RE.match(str(v)) for v in vals)

    def test_orthogonal_classification(self):
        vi = MINI_TABLES["voter_request_incentives"]
        assert set(vi["participation_class"]) <= {"CORRECT_VOTE", "WRONG_VOTE", "DID_NOT_VOTE", "UNKNOWN"}
        assert set(vi["reward_class"]) <= {"POSITIVE_REWARD", "NEGATIVE_SLASH", "ZERO_CHANGE", "NOT_OBSERVED"}
        has_tokens = vi["slashed_tokens_raw"].notna()
        pos = vi[has_tokens & vi["slashed_tokens_raw"].map(
            lambda s: int(s) > 0 if pd.notna(s) else False)]
        assert pos["participation_class"].eq("CORRECT_VOTE").all()
        assert pos["reward_class"].eq("POSITIVE_REWARD").all()

    def test_commit_layer_nonempty(self):
        assert len(MINI_TABLES["commits"]) > 0
        assert len(MINI_TABLES["participation"]) > 0
        assert len(MINI_TABLES["voter_request_incentives"]) > 0


class TestUsdcAmountConversion:
    """USDC raw → Decimal conversion: 6 decimals, exact arithmetic, no float."""

    def test_known_sample_752(self):
        from pmvotes.semantics import usdc_amount
        assert usdc_amount(752_000_000) == Decimal("752")

    def test_zero(self):
        from pmvotes.semantics import usdc_amount
        assert usdc_amount(0) == Decimal("0")

    def test_one_cent(self):
        from pmvotes.semantics import usdc_amount
        assert usdc_amount(10_000) == Decimal("0.01")

    def test_one_usdc(self):
        from pmvotes.semantics import usdc_amount
        assert usdc_amount(1_000_000) == Decimal("1")

    def test_not_nine_decimals(self):
        """752000000 / 10^9 = 0.752 — wrong. Must be 752."""
        from pmvotes.semantics import usdc_amount
        result = usdc_amount(752_000_000)
        assert result != Decimal("0.752"), "Using 10^9 decimals instead of 10^6"

    def test_result_is_decimal_not_float(self):
        from pmvotes.semantics import usdc_amount
        result = usdc_amount(752_000_000)
        assert isinstance(result, Decimal)

    def test_rejects_negative(self):
        from pmvotes.semantics import usdc_amount
        with pytest.raises(ValueError):
            usdc_amount(-1)

    def test_rejects_non_int(self):
        from pmvotes.semantics import usdc_amount
        with pytest.raises(TypeError):
            usdc_amount(752.0)

    def test_rejects_bool(self):
        from pmvotes.semantics import usdc_amount
        with pytest.raises(TypeError):
            usdc_amount(True)


class TestSettlementFields:
    """v1.2.0 settlement timestamp fields on mini fixtures."""

    def test_cases_has_settlement_columns(self):
        c = MINI_TABLES["cases"]
        assert "oo_settlement_timestamp" in c.columns
        assert "oo_settlement_price_raw" in c.columns

    def test_dvm_has_resolution_timestamp(self):
        assert "dvm_resolution_timestamp" in MINI_TABLES["dvm_requests"].columns

    def test_settlement_null_consistency(self):
        c = MINI_TABLES["cases"]
        assert (c["oo_settlement_timestamp"].isna() == c["oo_settlement_price_raw"].isna()).all()

    def test_fixture_has_both_settled_and_unsettled(self):
        c = MINI_TABLES["cases"]
        assert c["oo_settlement_timestamp"].notna().any(), "no settled cases in fixture"
        assert c["oo_settlement_timestamp"].isna().any(), "no unsettled cases in fixture"

    def test_settlement_timestamp_range(self):
        c = MINI_TABLES["cases"]
        ts = pd.to_numeric(c["oo_settlement_timestamp"].dropna())
        assert (ts >= 1_600_000_000).all()
        assert (ts <= 2_000_000_000).all()

    def test_settlement_price_raw_integer(self):
        c = MINI_TABLES["cases"]
        vals = c["oo_settlement_price_raw"].dropna()
        assert all(INT_RE.match(str(v)) for v in vals), "non-integer settlement price"

    def test_dvm_resolution_timestamp_coverage(self):
        q = MINI_TABLES["dvm_requests"]
        resolved = q[q["resolution_status"].eq("RESOLVED")]
        assert resolved["dvm_resolution_timestamp"].notna().all()


class TestClassificationEdgeCases:
    """Synthetic edge cases: classification must handle all boundary conditions."""

    def test_four_boundary_records(self):
        import numpy as np

        REQ_ID, RES_ROUND = "TEST_REQ", 100
        RESOLVED_PRICE, WRONG_PRICE = "1000000000000000000", "0"

        vs = pd.DataFrame({
            "dvm_request_id": [REQ_ID] * 3,
            "voter": ["0xCorrectZero", "0xWrongZero", "0xDidNotVote"],
            "slashed_tokens_raw": ["0", "0", "0"],
        })
        res_reveal = pd.DataFrame({
            "dvm_request_id": [REQ_ID] * 3,
            "voter": ["0xCorrectZero", "0xWrongZero", "0xBallotOnly"],
            "_revealed_price": [RESOLVED_PRICE, WRONG_PRICE, WRONG_PRICE],
        })
        resolved_map = {REQ_ID: RESOLVED_PRICE}

        # VoterSlashed classification
        tokens_int = vs["slashed_tokens_raw"].map(lambda s: int(s))
        vs["reward_class"] = np.where(
            tokens_int > 0, "POSITIVE_REWARD",
            np.where(tokens_int < 0, "NEGATIVE_SLASH", "ZERO_CHANGE"))
        vs = vs.merge(res_reveal, on=["dvm_request_id", "voter"], how="left")
        vs["_resolved"] = vs["dvm_request_id"].map(resolved_map)
        has_reveal = vs["_revealed_price"].notna()
        can_compare = has_reveal & vs["_resolved"].notna()
        voted_correct = can_compare & (vs["_revealed_price"].astype(str)
                                       == vs["_resolved"].astype(str))
        voted_wrong = can_compare & ~voted_correct
        vs["participation_class"] = np.where(
            voted_correct, "CORRECT_VOTE",
            np.where(voted_wrong, "WRONG_VOTE",
                     np.where(~has_reveal, "DID_NOT_VOTE", "UNKNOWN")))

        # Ballot-only classification
        vs_keys = set(zip(vs["dvm_request_id"], vs["voter"]))
        bo = res_reveal[[
            (r, v) not in vs_keys
            for r, v in zip(res_reveal["dvm_request_id"], res_reveal["voter"])
        ]].copy()
        bo["_resolved"] = bo["dvm_request_id"].map(resolved_map)
        bo_correct = bo["_revealed_price"].astype(str) == bo["_resolved"].astype(str)
        bo["participation_class"] = np.where(bo_correct, "CORRECT_VOTE", "WRONG_VOTE")
        bo["reward_class"] = "NOT_OBSERVED"

        idx = vs.set_index("voter")
        # Case 1: correct vote + zero slashing
        assert idx.loc["0xCorrectZero", "participation_class"] == "CORRECT_VOTE"
        assert idx.loc["0xCorrectZero", "reward_class"] == "ZERO_CHANGE"
        # Case 2: wrong vote + zero slashing
        assert idx.loc["0xWrongZero", "participation_class"] == "WRONG_VOTE"
        assert idx.loc["0xWrongZero", "reward_class"] == "ZERO_CHANGE"
        # Case 3: wrong vote + no VoterSlashed event
        bo_idx = bo.set_index("voter")
        assert bo_idx.loc["0xBallotOnly", "participation_class"] == "WRONG_VOTE"
        assert bo_idx.loc["0xBallotOnly", "reward_class"] == "NOT_OBSERVED"
        # Case 4: no reveal + VoterSlashed (eligibility confirmed)
        assert idx.loc["0xDidNotVote", "participation_class"] == "DID_NOT_VOTE"
        assert idx.loc["0xDidNotVote", "reward_class"] == "ZERO_CHANGE"


class TestTrackedReleaseArtifacts:
    """Tests on release files that ARE tracked in git (crosswalk + manifest)."""

    @pytest.mark.skipif(
        not json.load(open(Path(__file__).resolve().parent.parent / "release" / "manifest.json"))
        .get("sha256", {}).get("crosswalk.parquet"),
        reason="crosswalk not in manifest (v1.1+)")
    def test_crosswalk_manifest_hash(self):
        import hashlib
        from pmvotes import RELEASE
        manifest = json.load(open(RELEASE / "manifest.json"))
        actual = hashlib.sha256(
            (RELEASE / "crosswalk.parquet").read_bytes()
        ).hexdigest()
        assert actual == manifest["sha256"]["crosswalk.parquet"]

    @pytest.mark.skipif(
        not json.load(open(Path(__file__).resolve().parent.parent / "release" / "manifest.json"))
        .get("sha256", {}).get("crosswalk.parquet"),
        reason="crosswalk not in manifest (v1.1+)")
    def test_crosswalk_row_count(self):
        from pmvotes import RELEASE
        manifest = json.load(open(RELEASE / "manifest.json"))
        xw = pd.read_parquet(RELEASE / "crosswalk.parquet")
        assert len(xw) == manifest["rows"]["cases"]
