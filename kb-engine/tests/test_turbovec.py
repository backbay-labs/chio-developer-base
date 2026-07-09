from __future__ import annotations

import pytest

from kb_engine.store import FakeTurboVecStore, TurboVecStore, create_turbovec_store, vector_backend_from_env


def test_fake_turbovec_search_supports_allowlist():
    store = FakeTurboVecStore(dim=2)
    store.add_with_ids([1, 2, 3], [[1, 0], [0, 1], [0.9, 0.1]])

    hits = store.search([1, 0], k=3)
    assert [id_ for id_, _ in hits] == [1, 3, 2]

    filtered = store.search([1, 0], k=3, allowlist={2, 3})
    assert [id_ for id_, _ in filtered] == [3, 2]


def test_fake_turbovec_record_query_supports_filters():
    store = FakeTurboVecStore(dim=2)
    store.upsert(
        [
            {
                "id": "a",
                "text": "alpha",
                "embedding": [1, 0],
                "tenant": "chio",
                "properties": {"kind": "code"},
            },
            {
                "id": "b",
                "text": "beta",
                "embedding": [0.9, 0.1],
                "tenant": "alexandria",
                "properties": {"kind": "doc"},
            },
        ]
    )

    hits = store.query([1, 0], k=2, filters={"tenant": "alexandria"})
    assert [hit["id"] for hit in hits] == ["b"]
    assert store.snapshot_id() == "fake-turbovec:n=2:dim=2"


def test_create_turbovec_store_falls_back_to_fake_offline(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "turbovec":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    store = create_turbovec_store(dim=4)
    assert isinstance(store, FakeTurboVecStore)


def test_create_turbovec_store_uses_real_when_installable():
    pytest.importorskip("turbovec")
    pytest.importorskip("numpy")
    store = create_turbovec_store(dim=8)
    assert isinstance(store, TurboVecStore)
    store.upsert(
        [
            {
                "id": "a",
                "text": "alpha",
                "embedding": [1, 0, 0, 0, 0, 0, 0, 0],
                "tenant": "chio",
                "properties": {"kind": "code"},
            },
            {
                "id": "b",
                "text": "beta",
                "embedding": [0, 1, 0, 0, 0, 0, 0, 0],
                "tenant": "chio",
                "properties": {"kind": "doc"},
            },
        ]
    )
    hits = store.query([1, 0, 0, 0, 0, 0, 0, 0], k=1)
    assert hits and hits[0]["id"] == "a"
    assert store.snapshot_id().startswith("turbovec:")


def test_create_turbovec_store_falls_back_when_dim_not_multiple_of_eight():
    """Real IdMapIndex requires dim % 8 == 0; odd dims stay on Fake."""
    pytest.importorskip("turbovec")
    store = create_turbovec_store(dim=3)
    assert isinstance(store, FakeTurboVecStore)


def test_vector_backend_env_defaults_to_pgvector():
    assert vector_backend_from_env({}) == "pgvector"
    assert vector_backend_from_env({"KB_VECTOR": "turbovec"}) == "turbovec"
    with pytest.raises(ValueError, match="KB_VECTOR"):
        vector_backend_from_env({"KB_VECTOR": "faiss"})
