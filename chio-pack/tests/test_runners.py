"""Smoke tests for the three fixture-validating runners.

Each runner is invoked against the actual committed fixture set and
expected to return status="blocked-input" (fixtures present + schema-
valid; real input pipeline is Phase 1.x).
"""
from __future__ import annotations

import pathlib

from chio_pack.eval.runners import time_to_fix, conformance_recall, cap_error_explanation


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "chio-pack" / "eval" / "fixtures"


def test_time_to_fix_validates_committed_fixtures():
    agg = time_to_fix.run(FIXTURES / "time-to-fix")
    assert agg.n_fixtures >= 8, f"expected ≥ 8 fixtures, got {agg.n_fixtures}"
    assert agg.n_invalid == 0, f"schema errors in: {[fr.id for fr in agg.fixtures if not fr.valid]}"
    assert agg.status == "blocked-input"


def test_conformance_recall_validates_committed_fixtures():
    agg = conformance_recall.run(FIXTURES / "conformance-recall")
    assert agg.n_fixtures >= 20, f"expected ≥ 20 fixtures, got {agg.n_fixtures}"
    assert agg.n_invalid == 0, f"schema errors in: {[fr.id for fr in agg.fixtures if not fr.valid]}"
    assert agg.n_uncurated == 0, f"uncurated (_review) fixtures: {[fr.id for fr in agg.fixtures if fr.has_review_marker]}"
    assert agg.status == "blocked-input"


def test_cap_error_explanation_validates_committed_fixtures():
    agg = cap_error_explanation.run(FIXTURES / "cap-error-explanation")
    assert agg.n_fixtures >= 10, f"expected ≥ 10 fixtures, got {agg.n_fixtures}"
    assert agg.n_invalid == 0, f"schema errors in: {[fr.id for fr in agg.fixtures if not fr.valid]}"
    assert agg.n_with_full_augmentation_set == agg.n_fixtures, (
        f"{agg.n_fixtures - agg.n_with_full_augmentation_set} fixtures "
        f"missing canonical augmentations"
    )
    assert agg.status == "blocked-input"


def test_time_to_fix_below_threshold_returns_blocked_fixtures(tmp_path):
    # Empty dir → blocked-fixtures
    agg = time_to_fix.run(tmp_path, fixture_count_min=8)
    assert agg.status == "blocked-fixtures"
    assert agg.n_fixtures == 0
