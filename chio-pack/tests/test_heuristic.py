"""Tests for chio_pack.eval.classifiers.heuristic."""
from __future__ import annotations

import datetime as _dt

from chio_pack.eval.classifiers import heuristic


def _ev(t: str, event: str, **kw) -> dict:
    return {"t": t, "event": event, **kw}


def test_empty_session_no_mistakes():
    assert heuristic.classify([]) == []


def test_reverted_edit_within_window_classified():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "edit", file="src/a.rs", sha_before="X", sha_after="Y"),
        _ev("2026-05-07T10:15:00+00:00", "edit", file="src/a.rs", sha_before="Y", sha_after="X"),
    ]
    mistakes = heuristic.classify(events)
    assert len(mistakes) == 1
    assert mistakes[0].kind == "reverted_edit"
    assert mistakes[0].file == "src/a.rs"


def test_reverted_edit_outside_window_not_classified():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "edit", file="src/a.rs", sha_before="X", sha_after="Y"),
        # 35 min later — outside the 30 min window
        _ev("2026-05-07T10:35:00+00:00", "edit", file="src/a.rs", sha_before="Y", sha_after="X"),
    ]
    mistakes = heuristic.classify(events)
    assert mistakes == []


def test_reverted_edit_different_file_not_classified():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "edit", file="src/a.rs", sha_before="X", sha_after="Y"),
        _ev("2026-05-07T10:10:00+00:00", "edit", file="src/b.rs", sha_before="Y", sha_after="X"),
    ]
    mistakes = heuristic.classify(events)
    assert mistakes == []


def test_failed_then_re_edited_within_window():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "test_run", cmd="cargo test", exit=1, failures=["t1"]),
        _ev("2026-05-07T10:05:00+00:00", "edit", file="src/foo.rs", sha_before="A", sha_after="B"),
    ]
    mistakes = heuristic.classify(events)
    assert len(mistakes) == 1
    assert mistakes[0].kind == "failed_then_re_edited"
    assert mistakes[0].file == "src/foo.rs"


def test_failed_then_re_edited_with_intervening_test_not_classified():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "test_run", cmd="cargo test", exit=1, failures=["t1"]),
        _ev("2026-05-07T10:02:00+00:00", "test_run", cmd="cargo test --lib", exit=0),
        _ev("2026-05-07T10:05:00+00:00", "edit", file="src/foo.rs", sha_before="A", sha_after="B"),
    ]
    mistakes = heuristic.classify(events)
    # Green test resets the failed_test state
    assert all(m.kind != "failed_then_re_edited" for m in mistakes)


def test_failed_then_re_edited_outside_window_not_classified():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "test_run", cmd="cargo test", exit=1, failures=["t1"]),
        # 12 min later — outside the 10 min window
        _ev("2026-05-07T10:12:00+00:00", "edit", file="src/foo.rs", sha_before="A", sha_after="B"),
    ]
    mistakes = heuristic.classify(events)
    assert mistakes == []


def test_mistakes_returned_in_chronological_order():
    events = [
        _ev("2026-05-07T10:00:00+00:00", "edit", file="src/a.rs", sha_before="X", sha_after="Y"),
        _ev("2026-05-07T10:05:00+00:00", "test_run", cmd="cargo test", exit=1, failures=["t"]),
        _ev("2026-05-07T10:08:00+00:00", "edit", file="src/b.rs", sha_before="A", sha_after="B"),  # failed→re-edit
        _ev("2026-05-07T10:15:00+00:00", "edit", file="src/a.rs", sha_before="Y", sha_after="X"),  # revert
    ]
    mistakes = heuristic.classify(events)
    times = [m.t for m in mistakes]
    assert times == sorted(times)
