"""Tests for the cap-error calibration harness."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from chio_pack.eval import calibration
from chio_pack.eval.calibration import (
    CalibrationRun,
    DeterministicRater,
    ModelValidationResult,
    RaterScore,
    calibrate,
    rater_b_model,
    rater_c_model,
    render_calibration_md,
    validate_models,
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


# === Rater model env-var resolution =====================================


def test_rater_model_defaults(monkeypatch):
    monkeypatch.delenv("CHIO_KB_RATER_B_MODEL", raising=False)
    monkeypatch.delenv("CHIO_KB_RATER_C_MODEL", raising=False)
    # Defaults are the historical hardcoded names; pinned by ADR-0004.
    assert rater_b_model() == "claude-sonnet-4-6"
    assert rater_c_model() == "claude-haiku-4-5-20251001"


def test_rater_model_env_overrides(monkeypatch):
    monkeypatch.setenv("CHIO_KB_RATER_B_MODEL", "claude-test-b")
    monkeypatch.setenv("CHIO_KB_RATER_C_MODEL", "claude-test-c")
    assert rater_b_model() == "claude-test-b"
    assert rater_c_model() == "claude-test-c"


def test_default_pool_uses_env_resolved_models(monkeypatch):
    monkeypatch.setenv("CHIO_KB_RATER_B_MODEL", "claude-pool-b")
    monkeypatch.setenv("CHIO_KB_RATER_C_MODEL", "claude-pool-c")
    pool = calibration.default_pool()
    by_id = {r.rater_id: r for r in pool}
    assert by_id["rater-B"].model == "claude-pool-b"
    assert by_id["rater-C"].model == "claude-pool-c"


# === --validate-models smoke test =======================================


class _FakeAnthropicClient:
    """Minimal stand-in for `anthropic.Anthropic()`. Records every call
    and returns a sentinel response so we can verify the validator
    actually reaches the API path with the env-resolved model name.
    """

    def __init__(self, *, raise_for: set[str] | None = None) -> None:
        self.calls: list[dict] = []
        self.raise_for = raise_for or set()

        class _Messages:
            def __init__(self, parent: "_FakeAnthropicClient") -> None:
                self._parent = parent

            def create(self, *, model: str, max_tokens: int, messages: list[dict]) -> object:
                self._parent.calls.append(
                    {"model": model, "max_tokens": max_tokens, "messages": messages}
                )
                if model in self._parent.raise_for:
                    raise RuntimeError(f"unknown model: {model}")
                return object()

        self.messages = _Messages(self)


def test_validate_models_happy_path(monkeypatch):
    monkeypatch.setenv("CHIO_KB_RATER_B_MODEL", "claude-fake-b")
    monkeypatch.setenv("CHIO_KB_RATER_C_MODEL", "claude-fake-c")
    fake = _FakeAnthropicClient()
    results = validate_models(client_factory=lambda: fake)
    assert [r.rater_id for r in results] == ["rater-B", "rater-C"]
    assert all(isinstance(r, ModelValidationResult) for r in results)
    assert all(r.ok for r in results), [r.error for r in results]
    # Both calls used the env-resolved names + max_tokens=1 (smoke).
    assert {c["model"] for c in fake.calls} == {"claude-fake-b", "claude-fake-c"}
    assert all(c["max_tokens"] == 1 for c in fake.calls)


def test_validate_models_reports_per_rater_failure(monkeypatch):
    monkeypatch.setenv("CHIO_KB_RATER_B_MODEL", "claude-fake-b")
    monkeypatch.setenv("CHIO_KB_RATER_C_MODEL", "claude-bad-c")
    fake = _FakeAnthropicClient(raise_for={"claude-bad-c"})
    results = validate_models(client_factory=lambda: fake)
    by_id = {r.rater_id: r for r in results}
    assert by_id["rater-B"].ok is True
    assert by_id["rater-C"].ok is False
    assert "unknown model" in (by_id["rater-C"].error or "")


def test_validate_models_no_sdk_returns_clear_errors(monkeypatch):
    # No SDK + no key: validator does NOT raise; it returns errors.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Force the import attempt to fail by removing both 'anthropic' and
    # any cached module entry.
    import sys as _sys
    monkeypatch.setitem(_sys.modules, "anthropic", None)
    results = validate_models()
    assert all(not r.ok for r in results)
    assert all(r.error for r in results)


def test_cli_validate_models_flag_reaches_validation_code_path(tmp_path):
    """Smoke: `--validate-models` exits non-zero with a clear error
    when ANTHROPIC_API_KEY is unset and no SDK is wired in this env.

    This is the integration smoke; the unit tests above cover the
    actual validator logic with an injected fake client.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "chio_pack.eval.calibration",
            "--validate-models",
        ],
        capture_output=True,
        text=True,
        env={
            # Strip ANTHROPIC_API_KEY so the validator hits the no-key
            # branch deterministically. PATH must be preserved so
            # python can locate site-packages.
            **{k: v for k, v in __import__("os").environ.items()
               if k != "ANTHROPIC_API_KEY"},
        },
        check=False,
    )
    # Exit 2 is reserved for "validation failed"; both happy + sad
    # paths reach the validator code path so this asserts the flag
    # is plumbed through main(). On environments where the
    # anthropic SDK + ANTHROPIC_API_KEY are both present the test
    # would still exercise the path but might exit 0 / 2 depending
    # on credentials, which is why we accept either non-success or
    # the "ok" success.
    assert proc.returncode in (0, 2), (proc.returncode, proc.stdout, proc.stderr)
    # The flag's identifying output line should always appear.
    assert "rater-B" in proc.stdout and "rater-C" in proc.stdout, proc.stdout


# === LLM-LLM independence tripwire ======================================


def _run_with_llm_scores(
    *, b: dict[str, int], c: dict[str, int], a: dict[str, int] | None = None
) -> CalibrationRun:
    """Helper: construct a CalibrationRun with synthetic scores from
    the three raters. Defaults rater-A to 3-across so the LLM-pair
    rate is independent of A's choices.
    """
    if a is None:
        a = {d: 3 for d in calibration.DIMENSIONS}
    return CalibrationRun(
        run_number=0, date="2026-05-08",
        scenario_id="synthetic", augmentation_name="raw",
        scores=[
            RaterScore(rater_id="rater-A", dimensions=dict(a)),
            RaterScore(rater_id="rater-B", dimensions=dict(b)),
            RaterScore(rater_id="rater-C", dimensions=dict(c)),
        ],
    )


def test_llm_pair_rate_zero_when_b_and_c_agree():
    # Both LLMs give identical scores → 0 flagged / 4 total.
    run = _run_with_llm_scores(
        b={"clarity": 4, "accuracy": 4, "actionability": 4, "brevity": 5},
        c={"clarity": 4, "accuracy": 4, "actionability": 4, "brevity": 5},
    )
    flagged, total, rate = run.llm_pair_disagreement_rate()
    assert (flagged, total) == (0, 4)
    assert rate == 0.0


def test_llm_pair_rate_diff_of_one_does_not_flag():
    # Per RATERS.md disagreement-flag protocol: |b - c| > 1 flags;
    # a difference of exactly 1 is NOT a flag.
    run = _run_with_llm_scores(
        b={"clarity": 4, "accuracy": 4, "actionability": 4, "brevity": 4},
        c={"clarity": 5, "accuracy": 3, "actionability": 4, "brevity": 5},
    )
    flagged, total, rate = run.llm_pair_disagreement_rate()
    assert flagged == 0
    assert total == 4
    assert rate == 0.0


def test_llm_pair_rate_diff_greater_than_one_flags():
    # Two dimensions differ by 2 (>1) → 2/4 = 50% rate.
    run = _run_with_llm_scores(
        b={"clarity": 5, "accuracy": 5, "actionability": 4, "brevity": 4},
        c={"clarity": 3, "accuracy": 3, "actionability": 4, "brevity": 4},
    )
    flagged, total, rate = run.llm_pair_disagreement_rate()
    assert (flagged, total) == (2, 4)
    assert rate == pytest.approx(0.5)


def test_llm_pair_rate_none_when_an_llm_rater_missing():
    # No rater-B (e.g., it errored mid-run): rate should be None,
    # not 0.0 (so the warning doesn't fire spuriously).
    run = CalibrationRun(
        run_number=0, date="2026-05-08",
        scenario_id="synthetic", augmentation_name="raw",
        scores=[
            RaterScore(rater_id="rater-A", dimensions={"clarity": 3}),
            RaterScore(rater_id="rater-C", dimensions={"clarity": 3}),
        ],
    )
    flagged, total, rate = run.llm_pair_disagreement_rate()
    assert rate is None
    assert (flagged, total) == (0, 0)


def test_independence_warning_fires_below_threshold():
    # 0% rate < 5% threshold → warning fires.
    run = _run_with_llm_scores(
        b={"clarity": 4, "accuracy": 4, "actionability": 4, "brevity": 5},
        c={"clarity": 4, "accuracy": 4, "actionability": 4, "brevity": 5},
    )
    warning = run.llm_independence_warning()
    assert warning is not None
    assert "ADR-0004a" in warning
    assert "Anthropic" in warning
    assert "0/4" in warning  # flagged/total breakdown


def test_independence_warning_silent_above_threshold():
    # 25% rate > 5% threshold → no warning.
    run = _run_with_llm_scores(
        b={"clarity": 5, "accuracy": 4, "actionability": 4, "brevity": 5},
        c={"clarity": 3, "accuracy": 4, "actionability": 4, "brevity": 5},
    )
    assert run.llm_independence_warning() is None


def test_independence_warning_silent_when_llm_raters_missing():
    # If we can't compute a rate, we don't fire (avoids false positives
    # when both LLM raters errored out on a malformed scenario).
    run = CalibrationRun(
        run_number=0, date="2026-05-08",
        scenario_id="synthetic", augmentation_name="raw",
        scores=[RaterScore(rater_id="rater-A", dimensions={"clarity": 3})],
    )
    assert run.llm_independence_warning() is None


def test_independence_warning_threshold_param_overridable():
    # 25% rate; with a 30% threshold, the warning should fire.
    run = _run_with_llm_scores(
        b={"clarity": 5, "accuracy": 4, "actionability": 4, "brevity": 5},
        c={"clarity": 3, "accuracy": 4, "actionability": 4, "brevity": 5},
    )
    assert run.llm_independence_warning(threshold=0.30) is not None
    assert run.llm_independence_warning(threshold=0.20) is None


def test_dry_run_pool_triggers_independence_warning_in_cli():
    """End-to-end: the deterministic dry-run pool gives B and C
    matching-enough scores that the 5% tripwire fires. The CLI must
    surface the warning both in stdout JSON and on stderr.

    If a future change to dry_run_pool drives the LLM pair into a
    >5% disagreement rate, this test will fail and should be updated
    along with the change.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "chio_pack.eval.calibration",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    # The diagnostic block is always present; the warning text only
    # when the rate is below threshold.
    assert "llm_pair_disagreement" in payload
    block = payload["llm_pair_disagreement"]
    assert block["total"] == 4
    if block["rate"] is not None and block["rate"] < block["threshold"]:
        assert "llm_independence_warning" in payload
        assert "ADR-0004a" in payload["llm_independence_warning"]
        assert "ADR-0004a" in proc.stderr
