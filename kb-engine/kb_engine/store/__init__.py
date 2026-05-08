"""Backing-store adapters for the engine.

Three storage interfaces, each with a constructor that takes an injected
connection / driver handle so tests can pass fakes:

  - postgres.PostgresStore    pgvector chunk persistence + similarity search
  - neo4j.Neo4jStore          property-graph node/edge upsert + query
  - embed.Embedder            embedding callable (OpenAIEmbedder + FakeEmbedder)

The engine itself doesn't import these eagerly — they're loaded by the
ingest pipeline when a real backing store is configured. CI runs without
docker, so the unit tests cover the wiring without ever opening a real
connection.
"""
from .embed import Embedder, FakeEmbedder, OpenAIEmbedder
from .neo4j import Neo4jStore
from .postgres import PostgresStore

__all__ = [
    "Embedder",
    "FakeEmbedder",
    "OpenAIEmbedder",
    "Neo4jStore",
    "PostgresStore",
]
