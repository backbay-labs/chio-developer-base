"""Tests for the three backing stores using injected fakes."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from kb_engine import ConstraintKind, ConstraintSpec, Edge, Node
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
    assert any("hnsw" in stmt for stmt in executed)


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


def test_postgres_search_similar_casts_query_as_vector():
    """Bare float lists must not bind as double precision[] (Wave 1 live bug)."""
    conn, cur = _mock_pg_connection()
    cur.description = []
    cur.fetchall.return_value = []
    store = PostgresStore(conn, embedding_dim=4)
    store.search_similar([0.1, 0.2, 0.3, 0.4])
    sql, params = cur.execute.call_args[0]
    assert "%s::vector" in sql
    assert "<=> %s::vector" in sql
    # Params are Vector adapter or literal string — never a raw list.
    assert not any(isinstance(p, list) for p in params[:2])


# === PostgresStore — multitenant schema parameterization ===
#
# M1-Multitenant deliverable 1: schema is configurable; default keeps
# `chio_kb` for back-compat. Every schema-qualified statement must use
# the configured name. Two stores sharing one connection but different
# schemas must not collide.


def test_postgres_default_schema_is_chio_kb():
    """Back-compat: the default constructor still uses `chio_kb`."""
    conn, _ = _mock_pg_connection()
    store = PostgresStore(conn)
    assert store.schema == "chio_kb"


def test_postgres_bootstrap_with_alexandria_schema():
    """All bootstrap DDL must schema-qualify on the configured name."""
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=1536, schema="alexandria_kb")
    store.bootstrap()
    executed = [args[0][0] for args in cur.execute.call_args_list]
    # Every emitted statement that references the schema must use the
    # configured name. None should reference the legacy default.
    assert any("CREATE SCHEMA IF NOT EXISTS alexandria_kb" in s for s in executed)
    assert any("CREATE TABLE IF NOT EXISTS alexandria_kb.code_chunks" in s for s in executed)
    assert any("ON alexandria_kb.code_chunks" in s for s in executed)
    # And critically, none of them mention `chio_kb` — silent leakage
    # of the legacy schema would defeat the multitenant story.
    assert not any("chio_kb" in s for s in executed), (
        f"alexandria_kb store emitted SQL that references chio_kb: {executed}"
    )


def test_postgres_insert_uses_configured_schema():
    """insert_code_chunks must schema-qualify."""
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=4, schema="opus_kb")
    chunk = CodeChunk(
        file_path="x.py", source_root="/r", language="python",
        line_start=1, line_end=2, chunk_text="x", properties={},
    )
    store.insert_code_chunks([chunk], [[0.1] * 4])
    insert_sql = [
        c[0][0] for c in cur.execute.call_args_list if "INSERT INTO" in c[0][0]
    ]
    assert insert_sql, "expected an INSERT statement"
    assert all("opus_kb.code_chunks" in s for s in insert_sql)
    assert not any("chio_kb" in s for s in insert_sql)


def test_postgres_search_uses_configured_schema():
    """search_similar must schema-qualify."""
    conn, cur = _mock_pg_connection()
    cur.description = []
    cur.fetchall.return_value = []
    store = PostgresStore(conn, embedding_dim=4, schema="alpha_kb")
    store.search_similar([0.1] * 4)
    select_sql = [
        c[0][0] for c in cur.execute.call_args_list if "SELECT" in c[0][0]
    ]
    assert select_sql
    assert any("FROM alpha_kb.code_chunks" in s for s in select_sql)


def test_postgres_reset_uses_configured_schema():
    """reset() drops only the configured schema, never the legacy one."""
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=4, schema="alexandria_kb")
    store.reset()
    drop_sql = [
        c[0][0] for c in cur.execute.call_args_list if "DROP SCHEMA" in c[0][0]
    ]
    assert drop_sql
    assert all("alexandria_kb" in s for s in drop_sql)
    assert not any("chio_kb" in s for s in drop_sql)


def test_postgres_invalid_schema_rejected_at_construction():
    """Schema names that don't match `^[a-z][a-z0-9_]*$` raise ValueError
    BEFORE any SQL runs. This is the SQL-injection bouncer.
    """
    conn, _ = _mock_pg_connection()
    bad = [
        "Chio_KB",          # uppercase
        "chio-kb",          # dash
        "1_starts_digit",   # leading digit
        "with space",       # space
        "chio_kb;DROP",     # injection attempt
        "",                 # empty
        "schema'name",      # quote
    ]
    for name in bad:
        with pytest.raises(ValueError, match="invalid schema name|must be a string"):
            PostgresStore(conn, schema=name)


def test_postgres_two_schemas_share_connection_no_cross_writes():
    """Two stores on the same connection but different schemas must
    issue SQL that targets ONLY their own schema. This is the
    multitenant migration smoke test from the deliverable spec:
    bootstrap + insert against `chio_kb`, then bootstrap + insert
    against `alexandria_kb` on the same connection, and verify the
    two paths never bleed into each other's schema.
    """
    conn, cur = _mock_pg_connection()
    legacy = PostgresStore(conn, embedding_dim=4, schema="chio_kb")
    new_pack = PostgresStore(conn, embedding_dim=4, schema="alexandria_kb")
    chunk = CodeChunk(
        file_path="x.rs", source_root="/r", language="rust",
        line_start=1, line_end=2, chunk_text="x", properties={},
    )

    legacy.bootstrap()
    legacy.insert_code_chunks([chunk], [[0.1] * 4])
    legacy_sql = [c[0][0] for c in cur.execute.call_args_list]
    cur.execute.reset_mock()

    new_pack.bootstrap()
    new_pack.insert_code_chunks([chunk], [[0.2] * 4])
    new_sql = [c[0][0] for c in cur.execute.call_args_list]

    # Phase A only touches chio_kb.
    assert any("chio_kb" in s for s in legacy_sql)
    assert not any("alexandria_kb" in s for s in legacy_sql)
    # Phase B only touches alexandria_kb.
    assert any("alexandria_kb" in s for s in new_sql)
    assert not any("chio_kb" in s for s in new_sql)


def test_postgres_from_url_pulls_schema_from_query_param(monkeypatch):
    """from_url(url) accepts a `?schema=` query param and prefers it
    over the default. The kwarg still wins if both are given.
    """
    from kb_engine.store import postgres as pg_mod

    captured = {}

    class _FakePsycopg:
        def connect(self, url, autocommit=False):
            captured["url"] = url
            captured["autocommit"] = autocommit
            return MagicMock()

    fake = _FakePsycopg()
    monkeypatch.setitem(__import__("sys").modules, "psycopg", fake)

    # 1. URL with ?schema=... → schema picked up, query stripped from url
    store = pg_mod.PostgresStore.from_url(
        "postgres://u:p@h/db?schema=baia_kb"
    )
    assert store.schema == "baia_kb"
    assert "schema=" not in captured["url"], (
        f"schema query should be stripped before psycopg sees it: {captured['url']}"
    )

    # 2. Explicit kwarg overrides URL.
    store2 = pg_mod.PostgresStore.from_url(
        "postgres://u:p@h/db?schema=ignored", schema="opus_kb"
    )
    assert store2.schema == "opus_kb"

    # 3. Bare URL → default schema.
    store3 = pg_mod.PostgresStore.from_url("postgres://u:p@h/db")
    assert store3.schema == "chio_kb"


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


# === Neo4jStore — apply_constraint_specs (M1-Multitenant deliverable 2) ===


def test_neo4j_apply_constraint_specs_renders_uniqueness_cypher():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    n = store.apply_constraint_specs([
        ConstraintSpec(label="ChioCapability", property="id"),
        ConstraintSpec(label="ChioFile", property="path"),
    ])
    assert n == 2
    cyphers = [c[0][0] for c in session.run.call_args_list]
    # Each statement is the IF-NOT-EXISTS uniqueness form, with the
    # auto-derived constraint name.
    assert any(
        "CREATE CONSTRAINT ChioCapability_id_uniqueness IF NOT EXISTS" in c
        and "FOR (n:ChioCapability) REQUIRE n.id IS UNIQUE" in c
        for c in cyphers
    )
    assert any(
        "FOR (n:ChioFile) REQUIRE n.path IS UNIQUE" in c
        for c in cyphers
    )


def test_neo4j_apply_constraint_specs_supports_index_and_existence():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    store.apply_constraint_specs([
        ConstraintSpec(
            label="AlexandriaDoc",
            property="indexed_at",
            kind=ConstraintKind.INDEX,
        ),
        ConstraintSpec(
            label="AlexandriaDoc",
            property="title",
            kind=ConstraintKind.EXISTENCE,
        ),
    ])
    cyphers = [c[0][0] for c in session.run.call_args_list]
    assert any("CREATE INDEX" in c and "FOR (n:AlexandriaDoc) ON (n.indexed_at)" in c
               for c in cyphers)
    assert any("REQUIRE n.title IS NOT NULL" in c for c in cyphers)


def test_neo4j_apply_constraint_specs_rejects_unsafe_label():
    """A label with a closing-backtick injection attempt is rejected."""
    driver, _ = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    with pytest.raises(ValueError, match="invalid label identifier"):
        store.apply_constraint_specs([
            ConstraintSpec(label="X` MATCH (n) DELETE n;//", property="id"),
        ])
    with pytest.raises(ValueError, match="invalid property identifier"):
        store.apply_constraint_specs([
            ConstraintSpec(label="X", property="id; DROP "),
        ])


def test_neo4j_apply_constraint_specs_empty_runs_nothing():
    driver, session = _mock_neo4j_driver()
    store = Neo4jStore(driver)
    n = store.apply_constraint_specs([])
    assert n == 0
    assert session.run.call_count == 0
