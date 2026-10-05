"""Regression tests: verify release parquets reproduce expected values for curated edge cases.

Each fixture in regression_cases.json was sampled from the v1.0.0 release to cover key edge
cases (permissionless/managed OOV2, all resolution classes, rolled rounds, high ballot counts,
PRE_VOTING_V2, NEGRISK architecture).  The test reads the release parquets and asserts that
every fixture row still matches.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from pmvotes import RELEASE

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures" / "regression_cases.json"


_PARQUETS_PRESENT = all(
    (RELEASE / f"{n}.parquet").exists() for n in ("cases", "dvm_requests")
)


@pytest.fixture(scope="module")
def release_tables():
    """Load release parquets once per module."""
    if not _PARQUETS_PRESENT:
        pytest.skip("release parquets not present (large data files not in git)")
    return {
        name: pd.read_parquet(RELEASE / f"{name}.parquet")
        for name in ("cases", "dvm_requests")
    }


@pytest.fixture(scope="module")
def fixture_cases():
    """Load the curated regression fixture cases."""
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    return data["cases"]


def _get_case_row(cases_df: pd.DataFrame, oo_request_id: str) -> pd.Series:
    rows = cases_df[cases_df["oo_request_id"] == oo_request_id]
    assert len(rows) == 1, f"Expected 1 case row for {oo_request_id}, got {len(rows)}"
    return rows.iloc[0]


def _get_dvm_row(dvm_df: pd.DataFrame, dvm_request_id: str) -> pd.Series:
    rows = dvm_df[dvm_df["dvm_request_id"] == dvm_request_id]
    assert len(rows) == 1, f"Expected 1 dvm row for {dvm_request_id}, got {len(rows)}"
    return rows.iloc[0]


class TestRegressionCases:
    """Parametrised regression tests over curated fixture cases."""

    @staticmethod
    def _case_ids():
        with open(FIXTURES_PATH) as f:
            data = json.load(f)
        return [
            pytest.param(fc, id=fc["oo_request_id"][:50])
            for fc in data["cases"]
        ]

    @pytest.mark.parametrize("fc", _case_ids.__func__())
    def test_case_exists(self, release_tables, fc):
        """The OO request ID exists in the cases table."""
        cases = release_tables["cases"]
        matches = cases[cases["oo_request_id"] == fc["oo_request_id"]]
        assert len(matches) == 1

    @pytest.mark.parametrize("fc", _case_ids.__func__())
    def test_case_fields(self, release_tables, fc):
        """Case-level fields match the fixture."""
        row = _get_case_row(release_tables["cases"], fc["oo_request_id"])
        exp = fc["expected_case"]

        assert row["oo_contract"] == exp["oo_contract"]
        assert row["architecture"] == exp["architecture"]
        assert row["dvm_link_status"] == exp["dvm_link_status"]

        if exp["ancillary_hex_prefix"] is not None:
            actual_prefix = str(row["ancillary_hex"])[:40]
            assert actual_prefix == exp["ancillary_hex_prefix"]

    @pytest.mark.parametrize("fc", _case_ids.__func__())
    def test_dvm_fields(self, release_tables, fc):
        """DVM request fields match the fixture (skipped for PRE_VOTING_V2)."""
        if fc["expected_dvm"] is None:
            pytest.skip("PRE_VOTING_V2 case has no DVM request")

        row = _get_dvm_row(release_tables["dvm_requests"], fc["dvm_request_id"])
        exp = fc["expected_dvm"]

        assert row["resolution_status"] == exp["resolution_status"]
        assert row["ballot_status"] == exp["ballot_status"]
        assert int(row["n_ballots"]) == exp["n_ballots"]
        assert int(row["n_rounds"]) == exp["n_rounds"]
        assert int(row["roll_count"]) == exp["roll_count"]

        if exp["resolved_price_raw"] is not None:
            assert str(row["resolved_price_raw"]) == exp["resolved_price_raw"]
        if exp["resolved_uma_value_class"] is not None:
            assert str(row["resolved_uma_value_class"]) == exp["resolved_uma_value_class"]
        if exp["resolution_round"] is not None:
            assert int(row["resolution_round"]) == exp["resolution_round"]

    @pytest.mark.parametrize("fc", _case_ids.__func__())
    def test_linkage_consistency(self, release_tables, fc):
        """If the case is DVM_EXACT, its dvm_request_id appears in dvm_requests."""
        if fc["expected_case"]["dvm_link_status"] != "DVM_EXACT":
            pytest.skip("Not a DVM_EXACT case")

        dvm_id = fc["dvm_request_id"]
        assert dvm_id is not None
        dvm_df = release_tables["dvm_requests"]
        assert dvm_id in dvm_df["dvm_request_id"].values

    @pytest.mark.parametrize("fc", _case_ids.__func__())
    def test_condition_id(self, release_tables, fc):
        """Condition ID matches fixture (null or specific value)."""
        row = _get_case_row(release_tables["cases"], fc["oo_request_id"])
        if fc["condition_id"] is not None:
            assert str(row["condition_id"]) == fc["condition_id"]
        else:
            assert pd.isna(row["condition_id"]) or row["condition_id"] is None


def test_fixture_coverage(fixture_cases):
    """Verify the fixture file covers all required edge-case categories."""
    all_tags = set()
    for fc in fixture_cases:
        all_tags.update(fc["tags"])

    required_categories = [
        "permissionless_oov2",
        "managed_oov2",
        "p4_too_early",
        "p1_yes",
        "p2_no",
        "p3_unknown",
        "pre_voting_v2",
        "negrisk",
        "high_ballot_count",
    ]
    # At least one rolled case
    has_rolled = any(t.startswith("rolled_count_") for t in all_tags)
    assert has_rolled, "No rolled-round cases in fixtures"

    for cat in required_categories:
        assert cat in all_tags, f"Missing category {cat} in fixture tags"


def test_fixture_count(fixture_cases):
    """Verify we have the expected number of fixture cases."""
    assert len(fixture_cases) >= 25, f"Expected >= 25 fixtures, got {len(fixture_cases)}"
    assert len(fixture_cases) <= 35, f"Expected <= 35 fixtures, got {len(fixture_cases)}"
