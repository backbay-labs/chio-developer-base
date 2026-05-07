"""Heuristic mistake classifier for repeated-mistake-rate (Eval 2).

Walks a session's events and emits `mistake` records for known patterns.

Per chio-pack/eval/rubrics.md "Mistake taxonomy":

  - reverted_edit:        an edit's content is undone within 30 min
  - failed_then_re_edited: test run exit ≠ 0 then file edited within 10 min
                           without a test re-run between
  - superseded_quickly:   ADR draft transitions proposed → superseded within 7 days
  - wrong_capability_scope: edit grants/requests a scope later narrowed in same session
  - bypassed_guard:       test/feat disables/mocks a required guard
  - other:                manually classified

Today, only `reverted_edit` and `failed_then_re_edited` are implemented as
fully heuristic. The capability-scope and bypassed-guard classes need
arc-aware static analysis (Phase 1+) — they're STUBBED here so the API
is stable and the runner can compute partial rates.

The classifier is pure: same input → same output. It does NOT call out
to the KB or LLM; that's the job of llm_judge.py (downstream).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any


REVERTED_WINDOW_SECS = 30 * 60      # 30 min
FAILED_RE_EDITED_WINDOW_SECS = 10 * 60  # 10 min


@dataclass
class Mistake:
    """A classified mistake. Pre-LLM-judge."""

    t: _dt.datetime
    kind: str
    file: str | None = None
    reason: str | None = None
    pre_event_idx: int | None = None  # index into the source events list
    extra: dict[str, Any] = field(default_factory=dict)


def _parse_t(ev: dict[str, Any]) -> _dt.datetime:
    return _dt.datetime.fromisoformat(ev["t"])


def _classify_reverted_edits(events: list[dict[str, Any]]) -> list[Mistake]:
    """Detect edits whose post-content matches a prior pre-content within 30 min.

    A "revert" is heuristically: edit A produced sha X→Y, then edit B
    produced sha Y→X (or sha Y→Z where Z matches some earlier-known sha
    on the same file). We approximate by tracking sha_after sequences
    per-file and flagging any edit whose sha_after equals an earlier
    sha_before for that file within the window.
    """
    mistakes: list[Mistake] = []
    # per-file: list of (event_idx, t, sha_before, sha_after)
    per_file: dict[str, list[tuple[int, _dt.datetime, str | None, str | None]]] = {}
    for i, ev in enumerate(events):
        if ev.get("event") != "edit":
            continue
        f = ev.get("file") or ""
        t = _parse_t(ev)
        sb = ev.get("sha_before")
        sa = ev.get("sha_after")
        history = per_file.setdefault(f, [])
        # Look back: did we previously have a sha_before == this sha_after?
        for prev_i, prev_t, prev_sb, prev_sa in history:
            if (
                sa is not None
                and prev_sb == sa
                and (t - prev_t).total_seconds() <= REVERTED_WINDOW_SECS
            ):
                mistakes.append(
                    Mistake(
                        t=t,
                        kind="reverted_edit",
                        file=f or None,
                        reason="restored content from a prior sha within 30 min",
                        pre_event_idx=i,
                        extra={"reverted_to_sha": prev_sb, "from_sha": sa},
                    )
                )
                break
        history.append((i, t, sb, sa))
    return mistakes


def _classify_failed_then_re_edited(events: list[dict[str, Any]]) -> list[Mistake]:
    """Detect: test_run exit ≠ 0 → edit on a failing-test-related file →
    NO intervening test_run, all within 10 min.

    The "related file" check is approximate: any file edited after a
    failure counts. Real-world this misses cases where the edit is in a
    different file than what failed, but it captures the simple pattern
    of editing-in-a-vacuum after a red test.
    """
    mistakes: list[Mistake] = []
    last_failed_test: tuple[int, _dt.datetime] | None = None
    for i, ev in enumerate(events):
        kind = ev.get("event")
        if kind == "test_run":
            if ev.get("exit", 0) != 0:
                last_failed_test = (i, _parse_t(ev))
            else:
                last_failed_test = None  # green run resets
        elif kind == "edit" and last_failed_test is not None:
            t = _parse_t(ev)
            failed_i, failed_t = last_failed_test
            if (t - failed_t).total_seconds() <= FAILED_RE_EDITED_WINDOW_SECS:
                mistakes.append(
                    Mistake(
                        t=t,
                        kind="failed_then_re_edited",
                        file=ev.get("file"),
                        reason="edited within 10 min after a failing test run, with no intervening test re-run",
                        pre_event_idx=i,
                        extra={"failed_test_event_idx": failed_i},
                    )
                )
                # Don't reset last_failed_test — keep it active until
                # a green test_run or the window expires
    return mistakes


def _classify_superseded_quickly(events: list[dict[str, Any]]) -> list[Mistake]:
    """ADR draft → superseded within 7 days. Cross-session in practice;
    this stub returns []. Implemented in Phase 1+ when ADR transitions
    are tracked across sessions via the vault-sync daemon.
    """
    return []


def _classify_wrong_capability_scope(events: list[dict[str, Any]]) -> list[Mistake]:
    """Edit grants/requests a capability scope later narrowed in the same
    session. Requires arc-aware static analysis of capability literals.
    Stubbed — Phase 1+.
    """
    return []


def _classify_bypassed_guard(events: list[dict[str, Any]]) -> list[Mistake]:
    """Edit disables/mocks a guard that the spec requires. Requires arc-
    aware static analysis. Stubbed — Phase 1+.
    """
    return []


def classify(events: list[dict[str, Any]]) -> list[Mistake]:
    """Run all classifiers and return mistakes in chronological order."""
    mistakes: list[Mistake] = []
    mistakes.extend(_classify_reverted_edits(events))
    mistakes.extend(_classify_failed_then_re_edited(events))
    mistakes.extend(_classify_superseded_quickly(events))
    mistakes.extend(_classify_wrong_capability_scope(events))
    mistakes.extend(_classify_bypassed_guard(events))
    mistakes.sort(key=lambda m: m.t)
    return mistakes
