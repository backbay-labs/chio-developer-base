"""Tests for kb_engine.plugin Registry and hook protocols."""
from __future__ import annotations

import pytest

from kb_engine import (
    DerivedRecord,
    Edge,
    Node,
    ParsedFile,
    Registry,
    Symbol,
)


def test_empty_registry_returns_no_results():
    r = Registry()
    assert r.ingest_file("anything") is None
    assert r.project_graph(ParsedFile(path="x", language="py", text="")) == []
    assert r.handle_frontmatter("any", {}) == []


def test_source_ingester_first_non_none_wins():
    r = Registry()

    def skipper(p):
        return None

    def matcher(p):
        if p.endswith(".py"):
            return ParsedFile(path=p, language="python", text="")
        return None

    r.register_source_ingester(skipper)
    r.register_source_ingester(matcher)

    assert r.ingest_file("foo.py") is not None
    assert r.ingest_file("foo.rs") is None


def test_graph_projector_unions_output():
    r = Registry()

    def proj_a(parsed):
        yield Node(id="a", label="A")

    def proj_b(parsed):
        yield Node(id="b", label="B")
        yield Edge(src_id="a", dst_id="b", relationship="REL")

    r.register_graph_projector(proj_a)
    r.register_graph_projector(proj_b)

    parsed = ParsedFile(path="x", language="py", text="")
    out = r.project_graph(parsed)
    assert len(out) == 3
    assert any(isinstance(o, Node) and o.id == "a" for o in out)
    assert any(isinstance(o, Edge) and o.relationship == "REL" for o in out)


def test_frontmatter_handler_dispatches_by_type_with_wildcard():
    r = Registry()

    def spec_handler(type_, fm):
        yield DerivedRecord(target="graphiti", payload={"id": fm.get("id"), "via": "spec"})

    def universal_handler(type_, fm):
        yield DerivedRecord(target="audit-log", payload={"type": type_})

    r.register_frontmatter_handler("spec", spec_handler)
    r.register_frontmatter_handler("*", universal_handler)

    out_spec = r.handle_frontmatter("spec", {"id": "spec.foo"})
    assert len(out_spec) == 2
    targets = {rec.target for rec in out_spec}
    assert targets == {"graphiti", "audit-log"}

    # Non-matching type only fires the wildcard
    out_other = r.handle_frontmatter("daily", {"id": "daily.x"})
    assert len(out_other) == 1
    assert out_other[0].target == "audit-log"


def test_tool_registrar_called_with_server():
    r = Registry()
    seen: list[object] = []

    def registrar(server):
        seen.append(server)

    r.register_tool_registrar(registrar)

    sentinel = object()
    r.register_tools(sentinel)
    assert seen == [sentinel]


def test_register_rejects_non_callable():
    r = Registry()
    with pytest.raises(TypeError):
        r.register_source_ingester(42)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        r.register_graph_projector("not a function")  # type: ignore[arg-type]


def test_parsed_file_carries_symbols_and_properties():
    f = ParsedFile(
        path="src/foo.rs",
        language="rust",
        text="fn bar() {}",
        symbols=[Symbol(name="bar", kind="function", line_start=1, line_end=1)],
        properties={"crate": "chio-foo"},
    )
    assert f.symbols[0].name == "bar"
    assert f.properties["crate"] == "chio-foo"


def test_node_and_edge_equal_by_value():
    """Nodes and edges compare by field equality (frozen dataclasses)."""
    assert Node(id="x", label="L") == Node(id="x", label="L")
    assert Edge(src_id="x", dst_id="y", relationship="R") == Edge(
        src_id="x", dst_id="y", relationship="R"
    )
    assert Node(id="x", label="L") != Node(id="y", label="L")
