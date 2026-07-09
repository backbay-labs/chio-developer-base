"""Generic vector-store protocol.

This module is deliberately domain-free: records know about text,
embeddings, tenant isolation, and opaque properties, but nothing about
Chio schemas or vault note types.
"""
from __future__ import annotations

import os
from typing import Any, Protocol, Sequence, TypedDict, runtime_checkable


class VectorRecord(TypedDict):
    id: str
    text: str
    embedding: list[float]
    tenant: str
    properties: dict[str, Any]


class Hit(TypedDict):
    id: str
    text: str
    score: float
    tenant: str
    properties: dict[str, Any]


class Filters(TypedDict, total=False):
    tenant: str
    properties: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    dim: int

    def upsert(self, records: Sequence[VectorRecord]) -> None: ...

    def query(
        self,
        embedding: list[float],
        k: int,
        filters: Filters | None = None,
    ) -> list[Hit]: ...

    def snapshot_id(self) -> str: ...


class IdMapVectorIndex(Protocol):
    """IdMapIndex-style surface used by the TurboVec sidecar spike."""

    dim: int

    def add_with_ids(self, ids: Sequence[int], vectors: Sequence[Sequence[float]]) -> None: ...

    def search(
        self,
        query: Sequence[float],
        k: int = 10,
        *,
        allowlist: set[int] | None = None,
    ) -> list[tuple[int, float]]: ...


def vector_backend_from_env(env: dict[str, str] | None = None) -> str:
    value = (env or os.environ).get("KB_VECTOR", "pgvector").strip().lower()
    if value not in {"pgvector", "turbovec"}:
        raise ValueError("KB_VECTOR must be 'pgvector' or 'turbovec'")
    return value
