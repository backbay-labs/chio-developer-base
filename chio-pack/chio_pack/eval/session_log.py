"""Session-log writer for the repeated-mistake-rate eval (Eval 2).

A session is one bounded period of agent activity (a Claude Code session,
a Codex run, a manual `chio-dev` REPL). Sessions emit events to a JSONL
file at ~/.chio-dev/sessions/<session-id>.jsonl.

This module is the writer library. The future `chio-dev` CLI (Phase 1.5)
will call into these functions to record activity. Agents can also call
them directly from Python.

Usage:

    from chio_pack.eval import session_log as slog

    slog.tool_call(tool="kb_search_code",
                   args={"query": "capability revocation"},
                   result_ids=["spec.capability.revocation"])
    slog.edit(file="crates/chio-kernel/src/kernel/mod.rs",
              sha_before="abc123", sha_after="def456")
    slog.test_run(cmd="cargo test", exit=1, failures=["test_revoke"])
    slog.mistake(kind="reverted_edit",
                 file="crates/chio-kernel/src/kernel/mod.rs",
                 reason="reintroduced cap unwrap")

Session-id selection:
    - If env var CHIO_DEV_SESSION_ID is set, use it (lets multiple
      processes coordinate to the same session log).
    - Otherwise, generate one and export to env so subsequent calls in
      the same process land in the same file.

The schema matches the format documented in
chio-pack/eval/PHASE-0.md "Session log format".
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pathlib
import uuid
from typing import Any


def _home() -> pathlib.Path:
    base = os.environ.get("CHIO_DEV_HOME")
    return pathlib.Path(base) if base else pathlib.Path.home() / ".chio-dev"


def session_path() -> pathlib.Path:
    """Return the JSONL path for the current session, creating dirs as needed."""
    sessions = _home() / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    sid = os.environ.get("CHIO_DEV_SESSION_ID")
    if not sid:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S")
        sid = f"{ts}-{uuid.uuid4().hex[:8]}"
        os.environ["CHIO_DEV_SESSION_ID"] = sid
    return sessions / f"{sid}.jsonl"


def _emit(event: str, payload: dict[str, Any]) -> None:
    record = {
        "t": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        **payload,
    }
    with session_path().open("a") as f:
        f.write(json.dumps(record) + "\n")


def tool_call(tool: str, args: dict[str, Any], result_ids: list[str] | None = None) -> None:
    """Record a tool invocation (kb_search_code, kb_brief_feature, etc)."""
    _emit("tool_call", {"tool": tool, "args": args, "result_ids": result_ids or []})


def edit(file: str, sha_before: str | None = None, sha_after: str | None = None) -> None:
    """Record a file edit. SHAs identify the content before/after."""
    _emit("edit", {"file": file, "sha_before": sha_before, "sha_after": sha_after})


def test_run(cmd: str, exit: int, failures: list[str] | None = None) -> None:
    """Record a test invocation. Exit ≠ 0 indicates failures."""
    _emit("test_run", {"cmd": cmd, "exit": exit, "failures": failures or []})


def mistake(
    kind: str,
    file: str | None = None,
    reason: str | None = None,
    reverted_at: str | None = None,
    **extra: Any,
) -> None:
    """Record a classified mistake.

    Usually emitted by chio_pack.eval.classifiers.heuristic against a
    full session log; rarely called directly by agents.
    """
    payload = {"kind": kind}
    if file is not None:
        payload["file"] = file
    if reason is not None:
        payload["reason"] = reason
    if reverted_at is not None:
        payload["reverted_at"] = reverted_at
    payload.update(extra)
    _emit("mistake", payload)


def load_session(path: pathlib.Path) -> list[dict[str, Any]]:
    """Read a session JSONL file. Skips malformed lines with a warning print."""
    events: list[dict[str, Any]] = []
    with path.open() as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"warning: {path}:{n} malformed JSON, skipping", flush=True)
    return events
