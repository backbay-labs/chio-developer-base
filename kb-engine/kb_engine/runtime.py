"""Shared runtime handles for MCP tools and the gateway.

Tools receive an injected :class:`Runtime` rather than opening their own
Postgres/Neo4j connections. The gateway constructs one Runtime at boot
and passes it into every tool call via a thread-local / contextvar.
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .plugin import Registry
from .store import Embedder, FakeEmbedder, Neo4jStore, OpenAIEmbedder, PostgresStore


_CURRENT: ContextVar["Runtime | None"] = ContextVar("kb_runtime", default=None)


@dataclass
class Runtime:
    """Process-wide KB handles used by MCP tools."""

    registry: Registry
    postgres: PostgresStore | None = None
    neo4j: Neo4jStore | None = None
    embedder: Embedder | None = None
    vault_root: Path | None = None
    pack_schema: str = "chio_kb"
    extras: dict[str, Any] = field(default_factory=dict)

    def search_code(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        if self.postgres is None or self.embedder is None:
            return []
        vec = self.embedder([query])[0]
        return self.postgres.search_similar(vec, limit=limit, table="code_chunks")

    def search_docs(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        if self.postgres is None or self.embedder is None:
            return []
        vec = self.embedder([query])[0]
        return self.postgres.search_docs(vec, limit=limit)

    def neighbors(
        self, entity: str, *, depth: int = 2, limit: int = 50,
    ) -> list[dict[str, Any]]:
        if self.neo4j is None:
            return []
        return self.neo4j.query_neighbors(entity, depth=depth, limit=limit)

    def snapshot_id(self) -> str:
        if self.postgres is None:
            return "no-postgres"
        return self.postgres.snapshot_id()


RuntimeHandles = Runtime


def get_runtime() -> Runtime | None:
    return _CURRENT.get()


def set_runtime(runtime: Runtime | None):
    return _CURRENT.set(runtime)


def reset_runtime(token) -> None:
    _CURRENT.reset(token)


def require_runtime() -> Runtime:
    rt = get_runtime()
    if rt is None:
        raise RuntimeError(
            "kb_engine.runtime: no Runtime bound. The MCP gateway must "
            "call set_runtime() before dispatching tools."
        )
    return rt


def build_runtime_from_env(
    *,
    vault_root: Path | str | None = None,
    pack_schema: str | None = None,
) -> Runtime:
    """Construct a Runtime from environment variables.

    Missing optional services degrade gracefully (postgres/neo4j left
    None) so the gateway can still boot for health checks.
    """
    registry = Registry()
    registry.load_entry_points()

    schema = pack_schema or os.environ.get("CHIO_KB_PACK_SCHEMA", "chio_kb")
    postgres: PostgresStore | None = None
    embedder: Embedder | None = None
    neo4j: Neo4jStore | None = None

    pg_url = os.environ.get("POSTGRES_URL")
    if pg_url:
        try:
            postgres = PostgresStore.from_url(pg_url, schema=schema)
            postgres.bootstrap()
        except Exception:
            postgres = None

    if postgres is not None:
        if os.environ.get("OPENAI_API_KEY"):
            embedder = OpenAIEmbedder(
                model=os.environ.get("CHIO_KB_EMBED_MODEL", "text-embedding-3-small"),
            )
        else:
            embedder = FakeEmbedder(dim=postgres.embedding_dim)

    neo_uri = os.environ.get("NEO4J_URI")
    if neo_uri:
        try:
            neo4j = Neo4jStore.from_url(
                neo_uri,
                os.environ.get("NEO4J_USER", "neo4j"),
                os.environ.get("NEO4J_PASSWORD", "demodemo"),
            )
        except Exception:
            neo4j = None

    vault: Path | None = None
    if vault_root is not None:
        vault = Path(vault_root)
    else:
        env_vault = os.environ.get("CHIO_KB_VAULT_ROOT", "/vault")
        candidate = Path(env_vault)
        vault = candidate if candidate.exists() else None

    return Runtime(
        registry=registry,
        postgres=postgres,
        neo4j=neo4j,
        embedder=embedder,
        vault_root=vault,
        pack_schema=schema,
    )
