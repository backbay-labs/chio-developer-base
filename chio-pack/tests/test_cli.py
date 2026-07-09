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


# === init-pack appears in --help ===


def test_init_pack_listed_in_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "init-pack" in result.output


# === ingest --sources dispatch ===


def _extract_json_payload(output: str) -> dict:
    """Pull the trailing JSON payload from CliRunner mixed stdout.

    `chio-dev ingest` writes status to stderr (which CliRunner mixes
    into stdout by default) and a single multi-line JSON object to
    stdout. We scan for the first opening `{` whose contents parse
    cleanly through end-of-output.
    """
    import json as _json

    for i, ch in enumerate(output):
        if ch != "{":
            continue
        try:
            return _json.loads(output[i:])
        except _json.JSONDecodeError:
            continue
    raise AssertionError(f"no JSON payload in CLI output: {output!r}")


def test_ingest_sources_visits_each_source_entry(tmp_path, monkeypatch):
    """`chio-dev ingest --sources sources.toml --no-postgres --no-neo4j`
    parses the file and walks each [[source]] entry. The output JSON
    reports per-source stats so we can assert dispatch happened.
    """
    src_a = tmp_path / "tree-a"
    src_b = tmp_path / "tree-b"
    (src_a / "sub").mkdir(parents=True)
    (src_b / "sub").mkdir(parents=True)
    (src_a / "sub" / "lib.rs").write_text("fn a() {}\n")
    (src_b / "sub" / "lib.rs").write_text("fn b() {}\n")
    cfg = tmp_path / "sources.toml"
    cfg.write_text(
        f'''
        [[source]]
        pack = "chio"
        root = "{src_a}"

        [[source]]
        pack = "chio"
        root = "{src_b}"
        ''',
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "ingest",
            "--sources", str(cfg),
            "--no-postgres",
            "--no-neo4j",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert len(payload["sources"]) == 2
    assert payload["sources"][0]["root"] == str(src_a.resolve())
    assert payload["sources"][1]["root"] == str(src_b.resolve())


def test_ingest_back_compat_positional_root_still_works(tmp_path, monkeypatch):
    """Without --sources and without a discoverable sources.toml, the
    positional [SOURCE_ROOT] arg still works (back-compat).
    """
    src = tmp_path / "tree"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "lib.rs").write_text("fn a() {}\n")
    # Run from a directory with NO sources.toml so default lookup fails.
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    # Force CHIO_DEV_REPO so the repo-root sources.toml lookup also
    # points at a path with no sources.toml (tmp_path again).
    monkeypatch.setenv("CHIO_DEV_REPO", str(tmp_path))
    result = runner.invoke(
        main,
        [
            "ingest",
            str(src),
            "--no-postgres",
            "--no-neo4j",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _extract_json_payload(result.output)
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["root"] == str(src)


def test_ingest_rejects_unregistered_pack_in_sources(tmp_path, monkeypatch):
    src = tmp_path / "tree"
    src.mkdir()
    cfg = tmp_path / "sources.toml"
    cfg.write_text(
        f'''
        [[source]]
        pack = "definitely-not-installed"
        root = "{src}"
        ''',
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["ingest", "--sources", str(cfg), "--no-postgres", "--no-neo4j"],
    )
    assert result.exit_code == 2
    assert "not registered" in (result.output + (result.stderr or ""))


# === M1-Multitenant deliverable 3: --pack-schema / CHIO_KB_PACK_SCHEMA ===


def test_resolve_pack_schema_priority_order(monkeypatch):
    """`--pack-schema` flag wins, then env, then default."""
    from chio_pack.cli import _resolve_pack_schema

    monkeypatch.delenv("CHIO_KB_PACK_SCHEMA", raising=False)
    assert _resolve_pack_schema(None) == "chio_kb"

    monkeypatch.setenv("CHIO_KB_PACK_SCHEMA", "opus_kb")
    assert _resolve_pack_schema(None) == "opus_kb"

    # Flag overrides env.
    assert _resolve_pack_schema("alexandria_kb") == "alexandria_kb"


def test_ingest_help_advertises_pack_schema_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "--pack-schema" in result.output


def test_query_help_advertises_pack_schema_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["query", "--help"])
    assert result.exit_code == 0
    assert "--pack-schema" in result.output


def test_sync_help_advertises_pack_schema_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "--help"])
    assert result.exit_code == 0
    assert "--pack-schema" in result.output


def test_verify_command_accepts_signed_response(tmp_path):
    from kb_engine.receipt import sign_response

    response = sign_response(
        {
            "status": "ok",
            "tool": "kb_search_code",
            "query": "verify me",
            "results": [{"file_path": "x.py"}],
            "index_snapshot": "test",
        }
    )
    path = tmp_path / "response.json"
    path.write_text(__import__("json").dumps(response), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["verify", str(path)])
    assert result.exit_code == 0, result.output
    assert "receipt verified" in result.output


def test_verify_command_rejects_tampered_response(tmp_path):
    from kb_engine.receipt import sign_response

    response = sign_response(
        {
            "status": "ok",
            "tool": "kb_search_code",
            "query": "verify me",
            "results": [{"file_path": "x.py", "similarity": 0.9}],
        }
    )
    response["results"][0]["similarity"] = 0.1
    path = tmp_path / "response.json"
    path.write_text(__import__("json").dumps(response), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["verify", str(path)])
    assert result.exit_code == 1
    assert "verification failed" in result.output
