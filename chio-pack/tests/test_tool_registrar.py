"""Tests for ``chio_tool_registrar`` and the 10 ``kb_*`` tools.

These prove the engine ↔ pack boundary holds end-to-end:

  - The :class:`Registry` (from kb-engine) accepts a duck-typed
    ``server`` and dispatches all registrars against it.
  - chio-pack's ``chio_tool_registrar`` populates ``server.tools`` with
    exactly the 10 names listed in AGENTS.md.
  - Every registered tool is callable and returns a structured response
    (the Phase 1.3 stubs return ``{"status": "stub", ...}`` — that's
    fine; the contract is what's tested).
  - kb-engine never imports any chio_pack.tools.* module (boundary
    rule, AGENTS.md hard rule #3).
"""
from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest
from kb_engine import Registry

from chio_pack import plugin
from chio_pack.tools import ALL_NAMES, ALL_TOOLS
from chio_pack.tools.fake_server import FakeServer

# Canonical list straight from AGENTS.md "The 10 MCP tools".
EXPECTED_NAMES = {
    "kb_search_code",
    "kb_search_docs",
    "kb_find_tests",
    "kb_find_docs",
    "kb_neighbors",
    "kb_context",
    "kb_impact",
    "kb_brief_feature",
    "kb_eval",
    "kb_add_episode",
}


def test_all_names_match_agents_md_canonical_list():
    assert set(ALL_NAMES) == EXPECTED_NAMES
    assert len(ALL_NAMES) == 10


def test_registry_register_tools_populates_all_ten_names():
    """End-to-end: Registry → chio_tool_registrar → server.tools."""
    server = FakeServer()
    r = Registry()
    plugin.register(r)
    r.register_tools(server)
    assert set(server.tools) == EXPECTED_NAMES
    assert len(server.tools) == 10


def test_chio_tool_registrar_direct_invocation():
    """Calling the registrar directly (without going through Registry)
    also populates the server. Useful for tests / debugging."""
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    assert set(server.tools) == EXPECTED_NAMES


def test_registrar_rejects_server_without_register_tool():
    """Fail fast: a server that doesn't expose ``register_tool`` is a
    programming error and must surface as a TypeError, not as silent
    no-op."""

    class Bogus:
        pass

    with pytest.raises(TypeError, match="register_tool"):
        plugin.chio_tool_registrar(Bogus())


def test_registrar_rejects_server_with_non_callable_register_tool():
    class Bogus:
        register_tool = "not a function"

    with pytest.raises(TypeError, match="register_tool"):
        plugin.chio_tool_registrar(Bogus())


def test_each_registered_tool_has_required_metadata():
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    for name, t in server.tools.items():
        assert t.name == name
        assert isinstance(t.description, str) and t.description
        assert isinstance(t.input_schema, dict)
        assert t.input_schema.get("type") == "object"
        assert callable(t.call)


def test_each_registered_tool_is_callable_and_returns_structured_response():
    """Every tool is invokable and returns a dict with at least
    ``status`` and ``tool``. Stubs return ``status: stub``; real
    implementations (Phase 1.3+) will return ``status: ok``."""
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    sample_args: dict[str, dict[str, Any]] = {
        "kb_search_code": {"query": "capability revocation"},
        "kb_search_docs": {"query": "receipt commitment"},
        "kb_find_tests": {"path_or_symbol": "crates/chio-receipts/src/lib.rs"},
        "kb_find_docs": {"path_or_crate": "chio-receipts"},
        "kb_neighbors": {"entity": "ChioCapability:revocation"},
        "kb_context": {"entity": "ChioCapability:revocation"},
        "kb_impact": {"path_or_crate": "crates/chio-receipts/"},
        "kb_brief_feature": {"feature_or_task": "wire receipt verification"},
        "kb_eval": {},
        "kb_add_episode": {"name": "Demo episode", "body": "hello"},
    }
    for name in EXPECTED_NAMES:
        result = server.call_tool(name, sample_args[name])
        assert isinstance(result, dict), f"{name} returned non-dict"
        assert "status" in result, f"{name} returned no status"
        assert result["status"] in {"stub", "ok", "error"}, (
            f"{name} returned unexpected status {result['status']!r}"
        )
        if result["status"] != "error":
            assert result.get("tool") == name


def test_required_argument_validation_returns_error_not_raises():
    """Tools that have required arguments return an error dict on
    missing input (so an MCP gateway can wrap it as a JSON-RPC error)
    rather than raising — the registrar contract is exception-free
    inside ``call``."""
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    # kb_search_code requires "query"
    out = server.call_tool("kb_search_code", {})
    assert out["status"] == "error"
    assert "query" in out["reason"]
    # kb_add_episode requires both name and body
    out = server.call_tool("kb_add_episode", {"name": "x"})
    assert out["status"] == "error"


def test_fake_server_rejects_duplicate_registration():
    """Same name registered twice = bug in a registrar. FakeServer
    surfaces it loudly so the test suite catches it."""
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    with pytest.raises(ValueError, match="already registered"):
        plugin.chio_tool_registrar(server)


def test_kb_add_episode_does_not_write_to_graphiti_in_stub():
    """AGENTS.md hard rule #1: never write to Graphiti directly. The
    stub MUST NOT touch any external store. We check by AST: the tool
    module imports nothing graphiti-related."""
    import chio_pack.tools.kb_add_episode as mod

    src = inspect.getsource(mod)
    tree = ast.parse(src)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
    bad = [m for m in imported if "graphiti" in m.lower() or "neo4j" in m.lower()]
    assert not bad, f"kb_add_episode stub imports forbidden module(s): {bad}"


def test_engine_does_not_import_chio_tools():
    """AGENTS.md hard rule #3: kb_engine cannot import chio_*. Repeats
    the check from test_plugin.py for the new tools modules
    specifically — registration mechanism flows pack -> engine, never
    the reverse."""
    import kb_engine
    import kb_engine.plugin
    import kb_engine.types

    for module in (kb_engine, kb_engine.plugin, kb_engine.types):
        src = inspect.getsource(module)
        tree = ast.parse(src)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.append(node.module)
        bad = [m for m in imported if m.startswith("chio_")]
        assert not bad, f"{module.__name__} imports chio_*: {bad}"


def test_all_tools_tuple_order_is_canonical_agents_md_order():
    """AGENTS.md lists tools in a specific order; ALL_TOOLS preserves
    it so generated docs / dashboards stay stable."""
    canonical_order = [
        "kb_search_code",
        "kb_search_docs",
        "kb_find_tests",
        "kb_find_docs",
        "kb_neighbors",
        "kb_context",
        "kb_impact",
        "kb_brief_feature",
        "kb_eval",
        "kb_add_episode",
    ]
    assert [t.NAME for t in ALL_TOOLS] == canonical_order


def test_input_schemas_declare_required_fields_correctly():
    """Spot-check that the JSON-Schema ``required`` arrays match the
    documented contract (mirrors arc PR #599's mcp_server.py)."""
    server = FakeServer()
    plugin.chio_tool_registrar(server)
    cases = {
        "kb_search_code": ["query"],
        "kb_search_docs": ["query"],
        "kb_find_tests": ["path_or_symbol"],
        "kb_find_docs": ["path_or_crate"],
        "kb_neighbors": ["entity"],
        "kb_context": ["entity"],
        "kb_impact": ["path_or_crate"],
        "kb_brief_feature": ["feature_or_task"],
        "kb_add_episode": ["name", "body"],
    }
    for name, required in cases.items():
        schema = server.tools[name].input_schema
        assert schema.get("required") == required, (
            f"{name} required={schema.get('required')} expected={required}"
        )
    # kb_eval has no required args
    assert "required" not in server.tools["kb_eval"].input_schema or (
        server.tools["kb_eval"].input_schema.get("required") == []
    )
