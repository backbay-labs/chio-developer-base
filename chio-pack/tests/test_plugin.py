"""End-to-end tests proving chio-pack registers cleanly with kb_engine.

These tests exercise the engine ↔ pack boundary: chio-pack imports
kb_engine (allowed), kb_engine never imports chio_pack (enforced by
ops/ci/check-imports.py).
"""
from __future__ import annotations

import inspect

import pytest
from kb_engine import Edge, Node, Registry

from chio_pack import plugin, schema


def test_register_populates_all_four_hook_types():
    r = Registry()
    plugin.register(r)
    assert len(r.source_ingesters) == 1
    assert len(r.graph_projectors) == 1
    assert len(r.tool_registrars) == 1
    expected_types = schema.GRAPHITI_TYPES | schema.NEO4J_TYPES
    assert set(r.frontmatter_handlers.keys()) == expected_types


def test_rust_ingester_recognizes_rs_files():
    r = Registry()
    plugin.register(r)
    parsed = r.ingest_file("crates/chio-foo/src/lib.rs")
    assert parsed is not None
    assert parsed.language == "rust"
    assert parsed.properties["crate"] == "chio-foo"


def test_rust_ingester_skips_other_languages():
    r = Registry()
    plugin.register(r)
    assert r.ingest_file("foo.py") is None
    assert r.ingest_file("foo.ts") is None
    assert r.ingest_file("foo.md") is None


def test_graph_projector_emits_file_and_crate_nodes():
    r = Registry()
    plugin.register(r)
    parsed = r.ingest_file("crates/chio-foo/src/lib.rs")
    out = r.project_graph(parsed)
    nodes = [x for x in out if isinstance(x, Node)]
    edges = [x for x in out if isinstance(x, Edge)]
    file_nodes = [n for n in nodes if n.label == schema.FILE]
    crate_nodes = [n for n in nodes if n.label == schema.CRATE]
    contains_edges = [e for e in edges if e.relationship == schema.CONTAINS]
    assert len(file_nodes) == 1
    assert len(crate_nodes) == 1
    assert len(contains_edges) == 1
    assert contains_edges[0].src_id == "crate:chio-foo"
    assert contains_edges[0].dst_id == "file:crates/chio-foo/src/lib.rs"


def test_graph_projector_skips_non_rust():
    r = Registry()
    plugin.register(r)
    parsed = r.ingest_file("foo.py")
    if parsed is None:
        # Compose a non-Rust ParsedFile manually
        from kb_engine import ParsedFile

        parsed = ParsedFile(path="foo.py", language="python", text="")
    out = r.project_graph(parsed)
    assert out == []


def test_frontmatter_handler_routes_episode_to_graphiti():
    r = Registry()
    plugin.register(r)
    fm = {
        "id": "episode.foo",
        "title": "Foo",
        "graphiti_episode_name": "Foo",
        "scope": "chio-repo",
    }
    out = r.handle_frontmatter("episode-architecture-summary", fm)
    assert len(out) == 1
    rec = out[0]
    assert rec.target == "graphiti"
    assert rec.payload["name"] == "Foo"


def test_frontmatter_handler_routes_spec_with_chio_node_to_neo4j():
    r = Registry()
    plugin.register(r)
    fm = {"id": "spec.cap.x", "chio-node": "Capability"}
    out = r.handle_frontmatter("spec", fm)
    neo4j_records = [d for d in out if d.target == "neo4j"]
    assert len(neo4j_records) == 1
    assert neo4j_records[0].payload["label"] == schema.CAPABILITY


def test_frontmatter_handler_skips_unknown_chio_node():
    """Spec without a recognized chio-node value emits no Neo4j record."""
    r = Registry()
    plugin.register(r)
    fm = {"id": "spec.x", "chio-node": "NotAThing"}
    out = r.handle_frontmatter("spec", fm)
    assert all(d.target != "neo4j" for d in out)


def test_unknown_type_produces_no_records():
    r = Registry()
    plugin.register(r)
    out = r.handle_frontmatter("daily", {"id": "daily.x"})
    assert out == []


def test_engine_does_not_import_chio_modules():
    """Sanity check on AGENTS.md hard rule #3 — parse imports via AST.

    Docstrings legitimately mention `chio_*` (the very thing they're
    documenting), so a text-search check would false-positive. The AST
    walk only matches actual import statements.
    """
    import ast

    import kb_engine
    import kb_engine.plugin
    import kb_engine.types

    for module in (kb_engine, kb_engine.plugin, kb_engine.types):
        src = inspect.getsource(module)
        tree = ast.parse(src)
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)
        bad = [m for m in imported_modules if m.startswith("chio_")]
        assert not bad, f"{module.__name__} imports chio_*: {bad}"


def test_entry_point_loadable_via_registry():
    """If chio-pack is installed (which the test runner ensures via uv),
    Registry.load_entry_points() finds and runs `register`.
    """
    r = Registry()
    n = r.load_entry_points()
    assert n >= 1, "expected at least chio-pack's entry point to load"
    # After load, the same hooks should be present as direct register()
    assert len(r.source_ingesters) >= 1
    assert len(r.graph_projectors) >= 1
