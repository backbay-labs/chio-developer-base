"""Tests for the three backing stores using injected fakes."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from kb_engine import Edge, Node
from kb_engine.store import FakeEmbedder, Neo4jStore, OpenAIEmbedder, PostgresStore
from kb_engine.store.postgres import CodeChunk


# === FakeEmbedder ===


def test_fake_embedder_is_deterministic():
    e = FakeEmbedder(dim=8)
    a = e(["hello"])[0]
    b = e(["hello"])[0]
    assert a == b
    assert len(a) == 8


def test_fake_embedder_distinct_inputs_distinct_vectors():
    e = FakeEmbedder(dim=8)
    a = e(["hello"])[0]
    b = e(["world"])[0]
    assert a != b


def test_fake_embedder_empty_input_empty_output():
    assert FakeEmbedder()([]) == []


# === OpenAIEmbedder ===


def test_openai_embedder_lazy_import_error_message():
    """If the openai SDK is missing, the error is informative."""
    e = OpenAIEmbedder(model="text-embedding-3-small")
    # Default dim still set even before the SDK is touched
    assert e.dim == 1536


# === PostgresStore (with mock psycopg connection) ===


def _mock_pg_connection():
    """Build a mock that supports `with conn.cursor() as cur:` semantics."""
    conn = MagicMock()
    cur = MagicMock()
    # Support `with conn.cursor() as cur`
    conn.cursor.return_value.__enter__.return_value = cur
    conn.cursor.return_value.__exit__.return_value = False
    return conn, cur


def test_postgres_bootstrap_runs_expected_ddl():
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=1536)
    store.bootstrap()
    executed = [args[0][0] for args in cur.execute.call_args_list]
    assert any("CREATE SCHEMA IF NOT EXISTS chio_kb" in stmt for stmt in executed)
    assert any("CREATE TABLE IF NOT EXISTS chio_kb.code_chunks" in stmt for stmt in executed)
    assert any("vector(1536)" in stmt for stmt in executed)
    assert any("ivfflat" in stmt for stmt in executed)


def test_postgres_insert_code_chunks_validates_lengths():
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=8)
    chunk = CodeChunk(
        file_path="x.rs", source_root="/repo", language="rust",
        line_start=1, line_end=10, chunk_text="fn x() {}",
        properties={"crate": "foo"},
    )
    with pytest.raises(ValueError, match="must be the same length"):
        store.insert_code_chunks([chunk], [])
    with pytest.raises(ValueError, match="embedding dim 4"):
        store.insert_code_chunks([chunk], [[0.1] * 4])


def test_postgres_insert_code_chunks_executes_per_chunk():
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=4)
    chunk = CodeChunk(
        file_path="a.rs", source_root="/r", language="rust",
        line_start=1, line_end=2, chunk_text="x",
        properties={},
    )
    n = store.insert_code_chunks([chunk, chunk], [[0.1] * 4, [0.2] * 4])
    assert n == 2
    # Two INSERT statements via the same cursor
    insert_calls = [c for c in cur.execute.call_args_list if "INSERT INTO" in c[0][0]]
    assert len(insert_calls) == 2


def test_postgres_search_similar_validates_query_dim():
    conn, _ = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=8)
    with pytest.raises(ValueError, match="query_vec dim"):
        store.search_similar([0.1] * 4)


# === Neo4jStore (with mock driver) ===


def _mock_neo4j_driver():
    driver = MagicMock()
    session = MagicMock()
    # Support `with driver.session() as session`
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = False
    return driver, session


def test_neo4j_apply_constraints_swallows_per_statement_errors():
    driver, session = _mock_neo4j_driver()
    # First statement raises; second statement succeeds.
    session.run.side_effect = [Exception("already exists"), None]
    store = Neo4jStore(driver)
    store.apply_constraints([
        "CREATE CONSTRAINT a IF NOT EXISTS FOR (n:A) REQUIRE n.id IS UNIQUE;",
        "CREATE CONSTRAINT b IF NOT EXISTS FOR (n:B) REQUIRE n.id IS UNIQUE;",
    ])
    # Both statements were run despite the first raising
    assert session.run.call_count == 2


def test_neo4j_upsert_nodes_buckets_by_label():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    nodes = [
        Node(id="a1", label="Apple", properties={"color": "red"}),
        Node(id="a2", label="Apple", properties={"color": "green"}),
        Node(id="b1", label="Banana", properties={}),
    ]
    n = store.upsert_nodes(nodes)
    assert n == 3
    # One MERGE call per label (2 distinct labels → 2 calls)
    assert session.run.call_count == 2
    cyphers = [c[0][0] for c in session.run.call_args_list]
    assert any("Apple" in cy for cy in cyphers)
    assert any("Banana" in cy for cy in cyphers)


def test_neo4j_upsert_edges_buckets_by_relationship():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    edges = [
        Edge(src_id="a", dst_id="b", relationship="CALLS"),
        Edge(src_id="b", dst_id="c", relationship="CALLS"),
        Edge(src_id="a", dst_id="c", relationship="IMPLEMENTS"),
    ]
    n = store.upsert_edges(edges)
    assert n == 3
    # 2 distinct relationship types → 2 calls
    assert session.run.call_count == 2


def test_neo4j_upsert_empty_returns_zero():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    assert store.upsert_nodes([]) == 0
    assert store.upsert_edges([]) == 0
    assert session.run.call_count == 0


def test_neo4j_reset_with_label_prefix_filters():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    store.reset(label_prefix="Chio")
    cypher = session.run.call_args[0][0]
    assert "Chio" in cypher
    assert "STARTS WITH" in cypher


def test_neo4j_delete_node_uses_detach_delete_and_id_param():
    """delete_node must DETACH DELETE (no dangling edges) and bind the
    id as a parameter (no Cypher injection).
    """
    driver, session = _mock_neo4j_driver()
    result = MagicMock()
    record = {"deleted": 1}
    result.single.return_value = record
    session.run.return_value = result
    store = Neo4jStore(driver)
    n = store.delete_node("spec.x")
    assert n == 1
    cypher, kwargs = session.run.call_args[0][0], session.run.call_args[1]
    assert "DETACH DELETE" in cypher
    assert "MATCH (n {id: $id})" in cypher
    assert kwargs == {"id": "spec.x"}


def test_neo4j_delete_node_idempotent_when_missing():
    """Deleting a non-existent id returns 0 — re-running the prune is
    safe."""
    driver, session = _mock_neo4j_driver()
    result = MagicMock()
    result.single.return_value = {"deleted": 0}
    session.run.return_value = result
    store = Neo4jStore(driver)
    assert store.delete_node("does-not-exist") == 0


def test_neo4j_delete_node_handles_no_record():
    """If the driver returns no record (edge case in some adapters),
    delete_node returns 0 instead of crashing."""
    driver, session = _mock_neo4j_driver()
    result = MagicMock()
    result.single.return_value = None
    session.run.return_value = result
    store = Neo4jStore(driver)
    assert store.delete_node("anything") == 0
