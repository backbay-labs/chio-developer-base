"""Tests that surface the silent-zero stub in the repeated-mistake runner.

The candidate-notes lookup currently returns []; until the Phase 1 KB
stack is wired, every mistake is judged "not documented" and the rate
is biased toward 0%. These tests guarantee the runner emits a noisy
`stub_warning` field whenever the stub is still in use, so a downstream
consumer of the JSON cannot quietly accept a 0% rate as a real signal.

When the real implementation lands, these tests should be updated (or
flipped to assert the warning is _absent_) by the same change that
replaces `_candidate_notes_stub`.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from chio_pack.eval.runners import repeated_mistake


def test_candidate_notes_stub_returns_empty_list():
    # The stub is the silent-zero source. If this assertion ever flips,
    # whoever made the change must also clear the stub-warning surface.
    assert repeated_mistake._candidate_notes_stub("any context") == []


def test_candidate_notes_stub_self_advertises():
    # The runner relies on these attributes to pick up the warning.
    fn = repeated_mistake._candidate_notes_stub
    assert getattr(fn, "_is_stub", False) is True
    assert "Phase 1" in getattr(fn, "_stub_warning", "")


def test_aggregate_carries_stub_warning_when_blocked_on_inputs(tmp_path):
    agg = repeated_mistake.run(tmp_path)
    assert agg.status == "blocked-input"
    assert any("Phase 1" in w for w in agg.stub_warnings), (
        "expected Phase-1-wiring warning in aggregate.stub_warnings, "
        f"got: {agg.stub_warnings!r}"
    )


def test_aggregate_carries_stub_warning_when_below_baseline(tmp_path):
    # Drop a couple of empty session files to take the "below baseline"
    # path while still having at least one input present.
    for i in range(3):
        (tmp_path / f"s{i:03d}.jsonl").write_text("")
    agg = repeated_mistake.run(tmp_path, baseline_min_sessions=20)
    assert agg.status == "blocked-input"
    assert agg.n_sessions == 3
    assert any("Phase 1" in w for w in agg.stub_warnings)


def test_runner_main_emits_stub_warning_field(tmp_path):
    # Drive the CLI as a real subprocess so we know the stdout JSON is
    # what downstream consumers (make kb-eval, dashboard generators)
    # would actually see.
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "chio_pack.eval.runners.repeated_mistake",
            "--inputs",
            str(sessions_dir),
            "--baseline-min-sessions",
            "20",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Status is blocked-input → exit 1 by design.
    assert proc.returncode == 1, proc.stderr
    payload = json.loads(proc.stdout)
    assert "stub_warning" in payload, (
        f"expected stub_warning in CLI output, got keys: {list(payload)}"
    )
    warnings = payload["stub_warning"]
    assert isinstance(warnings, list) and warnings, warnings
    assert any("Phase 1" in w for w in warnings), warnings
    # The warning must reference the ADR so the consumer has a paper trail.
    assert any("ADR-0002" in w for w in warnings), warnings
