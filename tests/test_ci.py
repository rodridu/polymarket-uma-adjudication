"""CI-safe tests that run without release parquets.

These verify package structure, semantics, registry schemas, and basic
invariants on committed mini fixtures. Full 2M-row regression is in
test_regression.py (skipped in CI when release parquets are absent).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

MINI = Path(__file__).resolve().parent / "fixtures" / "mini_release"
MINI_TABLES = {
    name: pd.read_parquet(MINI / f"{name}.parquet")
    for name in ("cases", "dvm_requests", "rounds", "ballots", "crosswalk")
}


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
        assert len(MINI_TABLES["cases"]) == 3
        assert len(MINI_TABLES["dvm_requests"]) == 2
        assert len(MINI_TABLES["rounds"]) == 2
        assert len(MINI_TABLES["ballots"]) == 40
        assert len(MINI_TABLES["crosswalk"]) == 3


class TestTrackedReleaseArtifacts:
    """Tests on release files that ARE tracked in git (crosswalk + manifest)."""

    def test_crosswalk_manifest_hash(self):
        import hashlib
        from pmvotes import RELEASE
        manifest = json.load(open(RELEASE / "manifest.json"))
        actual = hashlib.sha256(
            (RELEASE / "crosswalk.parquet").read_bytes()
        ).hexdigest()
        assert actual == manifest["sha256"]["crosswalk.parquet"]

    def test_crosswalk_row_count(self):
        from pmvotes import RELEASE
        manifest = json.load(open(RELEASE / "manifest.json"))
        xw = pd.read_parquet(RELEASE / "crosswalk.parquet")
        assert len(xw) == manifest["rows"]["cases"]
