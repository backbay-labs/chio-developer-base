from __future__ import annotations

from typing import cast

from kb_engine.store import PostgresStore, VectorRecord, VectorStore
from tests.test_store import _mock_pg_connection


def test_postgres_store_satisfies_vector_store_protocol_shape() -> None:
    conn, _ = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=4, schema="demo_kb")

    vector_store = cast(VectorStore, store)

    assert vector_store.dim == 4
    assert callable(vector_store.upsert)
    assert callable(vector_store.query)
    assert callable(vector_store.snapshot_id)


def test_postgres_vector_upsert_writes_vector_records() -> None:
    conn, cur = _mock_pg_connection()
    store = PostgresStore(conn, embedding_dim=4, schema="demo_kb")
    record: VectorRecord = {
        "id": "doc-1",
        "text": "hello vector",
        "embedding": [0.1, 0.2, 0.3, 0.4],
        "tenant": "demo",
        "properties": {"kind": "doc"},
    }

    store.upsert([record])

    insert_sql = [c[0][0] for c in cur.execute.call_args_list if "INSERT INTO" in c[0][0]]
    assert insert_sql
    assert all("demo_kb.code_chunks" in stmt for stmt in insert_sql)
    params = cur.execute.call_args_list[-1][0][1]
    assert params[0] == "doc-1"
    assert params[1] == "demo"
    assert params[5] == "hello vector"


def test_postgres_vector_query_maps_hits_and_filters() -> None:
    conn, cur = _mock_pg_connection()
    cur.description = [
        ("id",),
        ("file_path",),
        ("source_root",),
        ("language",),
        ("line_start",),
        ("line_end",),
        ("chunk_text",),
        ("properties",),
        ("similarity",),
    ]
    cur.fetchall.return_value = [
        (7, "doc-1", "demo", "text", 1, 1, "hello", {"kind": "doc"}, 0.91),
    ]
    store = PostgresStore(conn, embedding_dim=4, schema="demo_kb")

    hits = store.query(
        [0.0, 0.1, 0.2, 0.3],
        k=3,
        filters={"tenant": "demo", "properties": {"kind": "doc"}},
    )

    assert hits == [
        {
            "id": "doc-1",
            "text": "hello",
            "score": 0.91,
            "tenant": "demo",
            "properties": {"kind": "doc"},
        }
    ]
    sql, params = cur.execute.call_args[0]
    assert "source_root = %s" in sql
    assert "properties @> %s::jsonb" in sql
    assert params[-1] == 3
