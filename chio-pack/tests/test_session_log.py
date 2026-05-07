"""Tests for chio_pack.eval.session_log."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile

from chio_pack.eval import session_log


def _setup_tmp_home() -> pathlib.Path:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="chio-dev-test-"))
    os.environ["CHIO_DEV_HOME"] = str(tmp)
    os.environ.pop("CHIO_DEV_SESSION_ID", None)
    return tmp


def _read_lines(path: pathlib.Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def test_session_path_creates_dir():
    tmp = _setup_tmp_home()
    try:
        p = session_log.session_path()
        assert p.parent.exists()
        assert p.parent.name == "sessions"
        assert p.name.endswith(".jsonl")
    finally:
        shutil.rmtree(tmp)
        os.environ.pop("CHIO_DEV_HOME", None)
        os.environ.pop("CHIO_DEV_SESSION_ID", None)


def test_tool_call_emits_record():
    tmp = _setup_tmp_home()
    try:
        session_log.tool_call(tool="kb_search_code", args={"query": "x"}, result_ids=["a", "b"])
        records = _read_lines(session_log.session_path())
        assert len(records) == 1
        r = records[0]
        assert r["event"] == "tool_call"
        assert r["tool"] == "kb_search_code"
        assert r["args"] == {"query": "x"}
        assert r["result_ids"] == ["a", "b"]
        assert "t" in r
    finally:
        shutil.rmtree(tmp)
        os.environ.pop("CHIO_DEV_HOME", None)
        os.environ.pop("CHIO_DEV_SESSION_ID", None)


def test_full_event_sequence_loads_back():
    tmp = _setup_tmp_home()
    try:
        session_log.tool_call(tool="kb_search_code", args={}, result_ids=[])
        session_log.edit(file="src/foo.rs", sha_before="aaa", sha_after="bbb")
        session_log.test_run(cmd="cargo test", exit=1, failures=["t1"])
        session_log.mistake(kind="reverted_edit", file="src/foo.rs", reason="r")

        path = session_log.session_path()
        events = session_log.load_session(path)
        assert [e["event"] for e in events] == ["tool_call", "edit", "test_run", "mistake"]
        assert events[1]["sha_before"] == "aaa"
        assert events[2]["exit"] == 1
        assert events[3]["kind"] == "reverted_edit"
    finally:
        shutil.rmtree(tmp)
        os.environ.pop("CHIO_DEV_HOME", None)
        os.environ.pop("CHIO_DEV_SESSION_ID", None)
