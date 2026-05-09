"""Tests for the cap-error calibration harness."""
from __future__ import annotations

import pathlib

import pytest

from chio_pack.eval import calibration
from chio_pack.eval.calibration import (
    CalibrationRun,
    DeterministicRater,
    RaterScore,
    calibrate,
    render_calibration_md,
)


SCENARIO = (
    pathlib.Path(__file__).resolve().parents[1]
    / "eval" / "fixtures" / "cap-error-explanation"
    / "revoked-cap-still-presented.yml"
)


def test_dry_run_pool_produces_three_raters():
    pool = calibration.dry_run_pool()
    assert len(pool) == 3
    assert {r.rater_id for r in pool} == {"rater-A", "rater-B", "rater-C"}


def test_calibrate_against_real_scenario():
    pool = calibration.dry_run_pool()
    run = calibrate(SCENARIO, pool, augmentation_name="raw", run_number=0)
    assert run.scenario_id == "revoked-cap-still-presented"
    assert run.augmentation_name == "raw"
    assert len(run.scores) == 3
    for s in run.scores:
        assert set(s.dimensions.keys()) == {
            "clarity", "accuracy", "actionability", "brevity",
        }


def test_calibrate_unknown_augmentation_raises():
    pool = calibration.dry_run_pool()
    with pytest.raises(ValueError, match="no augmentation named"):
        calibrate(SCENARIO, pool, augmentation_name="not-a-real-aug")


def test_disagreement_flags_detected():
    run = CalibrationRun(
        run_number=0, date="2026-05-08",
        scenario_id="x", augmentation_name="raw",
        scores=[
            RaterScore(rater_id="A", dimensions={"clarity": 5, "accuracy": 3}),
            RaterScore(rater_id="B", dimensions={"clarity": 3, "accuracy": 3}),
            RaterScore(rater_id="C", dimensions={"clarity": 4, "accuracy": 3}),
        ],
    )
    flags = run.disagreement_flags()
    assert "clarity" in flags  # max 5, min 3, diff > 1
    assert flags["clarity"] == (5, 3)
    assert "accuracy" not in flags  # all 3, no disagreement


def test_disagreement_flag_threshold_is_strict_greater_than_one():
    run = CalibrationRun(
        run_number=0, date="2026-05-08",
        scenario_id="x", augmentation_name="raw",
        scores=[
            RaterScore(rater_id="A", dimensions={"clarity": 3}),
            RaterScore(rater_id="B", dimensions={"clarity": 4}),
        ],
    )
    # Diff of 1 should NOT flag
    assert run.disagreement_flags() == {}


def test_render_calibration_md_produces_rows():
    pool = calibration.dry_run_pool()
    run = calibrate(SCENARIO, pool, augmentation_name="raw")
    md = render_calibration_md(run)
    # 3 raters × 4 dimensions = 12 rows
    assert md.count("\n") == 11  # 12 rows = 11 newlines
    for d in ("clarity", "accuracy", "actionability", "brevity"):
        assert d in md


def test_rater_score_mean():
    s = RaterScore(rater_id="x", dimensions={
        "clarity": 5, "accuracy": 4, "actionability": 3, "brevity": 4,
    })
    assert s.mean() == 4.0


def test_deterministic_rater_returns_configured_scores():
    r = DeterministicRater(rater_id="test", base_scores={
        "clarity": 5, "accuracy": 5, "actionability": 1, "brevity": 1,
    })
    score = r.score({"id": "x", "scenario": "..."}, "irrelevant body")
    assert score.dimensions == {
        "clarity": 5, "accuracy": 5, "actionability": 1, "brevity": 1,
    }
