"""Backing-store adapters for the engine.

Three storage interfaces, each with a constructor that takes an injected
connection / driver handle so tests can pass fakes:

  - postgres.PostgresStore    pgvector chunk persistence + similarity search
  - neo4j.Neo4jStore          property-graph node/edge upsert + query
  - embed.Embedder            embedding callable (OpenAIEmbedder + FakeEmbedder)
  - turbovec.FakeTurboVecStore optional TurboVec-compatible offline index

The engine itself doesn't import these eagerly — they're loaded by the
ingest pipeline when a real backing store is configured. CI runs without
docker, so the unit tests cover the wiring without ever opening a real
connection.
"""
from .embed import Embedder, FakeEmbedder, OpenAIEmbedder
from .neo4j import Neo4jStore
from .postgres import PostgresStore
from .turbovec import FakeTurboVecStore, TurboVecStore, create_turbovec_store
from .vector import Filters, Hit, IdMapVectorIndex, VectorRecord, VectorStore, vector_backend_from_env

__all__ = [
    "Embedder",
    "Filters",
    "FakeTurboVecStore",
    "FakeEmbedder",
    "Hit",
    "IdMapVectorIndex",
    "OpenAIEmbedder",
    "Neo4jStore",
    "PostgresStore",
    "TurboVecStore",
    "VectorRecord",
    "VectorStore",
    "create_turbovec_store",
    "vector_backend_from_env",
]
