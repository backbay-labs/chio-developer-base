"""Smoke tests for the chio-dev CLI."""
from __future__ import annotations

from click.testing import CliRunner

from chio_pack.cli import main


def test_help_runs():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "chio-dev" in result.output


def test_session_show_does_not_error():
    runner = CliRunner()
    result = runner.invoke(main, ["session", "show"])
    # session show returns 0 even if no log exists yet
    assert result.exit_code == 0


def test_subcommands_are_listed_in_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    for cmd in ["status", "up", "down", "ingest", "query", "sync",
                "migrate-seeds", "eval", "dogfood", "session"]:
        assert cmd in result.output, f"missing subcommand in --help: {cmd}"


def test_session_subcommand_help():
    runner = CliRunner()
    result = runner.invoke(main, ["session", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output
    assert "tool-call" in result.output


def test_session_tool_call_writes_event(tmp_path, monkeypatch):
    monkeypatch.setenv("CHIO_DEV_HOME", str(tmp_path))
    monkeypatch.delenv("CHIO_DEV_SESSION_ID", raising=False)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["session", "tool-call", "--tool", "kb_search_code",
         "--args", '{"q": "x"}', "--result-ids", "a,b,c"],
    )
    assert result.exit_code == 0
    sessions = list((tmp_path / "sessions").glob("*.jsonl"))
    assert len(sessions) == 1
    content = sessions[0].read_text()
    assert "kb_search_code" in content
    assert '"q": "x"' in content
