"""TurboVec adapter spike.

TurboVec is an optional acceleration path behind ``KB_VECTOR=turbovec``.

- If the real ``turbovec`` PyPI package is installed, ``TurboVecStore`` wraps
  ``turbovec.IdMapIndex`` (quantized ANN; dim must be a multiple of 8).
- Otherwise ``FakeTurboVecStore`` provides a deterministic offline IdMapIndex
  mimic so dual-index benches and unit tests stay dependency-free.

Postgres remains the primary CI gate (``KB_VECTOR=pgvector``). This module
never promotes TurboVec to primary.
"""
from __future__ import annotations

import math
from typing import Sequence

from .vector import Filters, Hit, VectorRecord, VectorStore


class FakeTurboVecStore:
    """Dependency-free IdMapIndex mimic with allowlist-aware cosine search."""

    def __init__(self, dim: int) -> None:
        self.dim = dim
        self._vectors: dict[int, tuple[float, ...]] = {}
        self._records: dict[int, VectorRecord] = {}
        self._string_to_int_ids: dict[str, int] = {}

    def add_with_ids(self, ids: Sequence[int], vectors: Sequence[Sequence[float]]) -> None:
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must have the same length")
        for id_, vector in zip(ids, vectors):
            vec = tuple(float(x) for x in vector)
            if len(vec) != self.dim:
                raise ValueError(f"vector dim {len(vec)} != configured {self.dim}")
            self._vectors[int(id_)] = vec

    def search(
        self,
        query: Sequence[float],
        k: int = 10,
        *,
        allowlist: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        q = tuple(float(x) for x in query)
        if len(q) != self.dim:
            raise ValueError(f"query dim {len(q)} != configured {self.dim}")
        scored: list[tuple[int, float]] = []
        for id_, vector in self._vectors.items():
            if allowlist is not None and id_ not in allowlist:
                continue
            scored.append((id_, _cosine(q, vector)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        ids: list[int] = []
        vectors: list[list[float]] = []
        for record in records:
            int_id = self._id_for(str(record["id"]))
            ids.append(int_id)
            vectors.append(record["embedding"])
            self._records[int_id] = record
        self.add_with_ids(ids, vectors)

    def query(
        self,
        embedding: list[float],
        k: int,
        filters: Filters | None = None,
    ) -> list[Hit]:
        allowlist = None
        if filters:
            allowlist = {
                id_
                for id_, record in self._records.items()
                if _matches_filters(record, filters)
            }
        hits: list[Hit] = []
        for id_, score in self.search(embedding, k=k, allowlist=allowlist):
            record = self._records.get(id_)
            if record is None:
                hits.append({
                    "id": str(id_),
                    "text": "",
                    "score": score,
                    "tenant": "",
                    "properties": {},
                })
                continue
            hits.append({
                "id": record["id"],
                "text": record["text"],
                "score": score,
                "tenant": record["tenant"],
                "properties": record["properties"],
            })
        return hits

    def snapshot_id(self) -> str:
        return f"fake-turbovec:n={len(self._vectors)}:dim={self.dim}"

    def __len__(self) -> int:
        return len(self._vectors)

    def _id_for(self, id_: str) -> int:
        if id_ not in self._string_to_int_ids:
            self._string_to_int_ids[id_] = len(self._string_to_int_ids) + 1
        return self._string_to_int_ids[id_]


class TurboVecStore:
    """Real ``turbovec.IdMapIndex`` adapter (optional dependency).

    Construction requires ``turbovec`` to be importable. Dim must be a positive
    multiple of 8 (TurboVec package constraint). Chunk metadata stays in the
    Python side-car; the index holds quantized vectors keyed by integer ids.
    """

    def __init__(self, dim: int, *, bit_width: int = 4) -> None:
        if dim <= 0 or dim % 8 != 0:
            raise ValueError(f"TurboVecStore dim must be a positive multiple of 8, got {dim}")
        import numpy as np
        import turbovec

        self.dim = dim
        self.bit_width = bit_width
        self._np = np
        self._index = turbovec.IdMapIndex(dim=dim, bit_width=bit_width)
        self._records: dict[int, VectorRecord] = {}
        self._string_to_int_ids: dict[str, int] = {}
        self._n = 0

    def add_with_ids(self, ids: Sequence[int], vectors: Sequence[Sequence[float]]) -> None:
        if len(ids) != len(vectors):
            raise ValueError("ids and vectors must have the same length")
        if not ids:
            return
        vecs = self._np.asarray(vectors, dtype=self._np.float32)
        id_arr = self._np.asarray([int(i) for i in ids], dtype=self._np.uint64)
        if vecs.ndim != 2 or vecs.shape[1] != self.dim:
            raise ValueError(f"vectors shape {vecs.shape} incompatible with dim={self.dim}")
        self._index.add_with_ids(vecs, id_arr)
        self._n = len(self._index) if hasattr(self._index, "__len__") else self._n + len(ids)

    def search(
        self,
        query: Sequence[float],
        k: int = 10,
        *,
        allowlist: set[int] | None = None,
    ) -> list[tuple[int, float]]:
        q = self._np.asarray([list(query)], dtype=self._np.float32)
        if q.shape[1] != self.dim:
            raise ValueError(f"query dim {q.shape[1]} != configured {self.dim}")
        kwargs: dict = {}
        if allowlist is not None:
            kwargs["allowlist"] = self._np.asarray(sorted(allowlist), dtype=self._np.uint64)
        scores, hit_ids = self._index.search(q, k, **kwargs)
        out: list[tuple[int, float]] = []
        # Package returns (scores[n_queries, k], ids[n_queries, k])
        for score, id_ in zip(scores[0].tolist(), hit_ids[0].tolist()):
            if int(id_) == 0 and float(score) == 0.0 and not out and k > 0:
                # Empty result rows can appear as zeros; skip trailing empties.
                continue
            out.append((int(id_), float(score)))
        return out[:k]

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        ids: list[int] = []
        vectors: list[list[float]] = []
        for record in records:
            int_id = self._id_for(str(record["id"]))
            # Re-add after remove if the package supports it; otherwise overwrite
            # side-car and re-index the id (IdMapIndex remove is O(1)).
            if hasattr(self._index, "contains") and self._index.contains(int_id):
                self._index.remove(int_id)
            ids.append(int_id)
            vectors.append(record["embedding"])
            self._records[int_id] = record
        self.add_with_ids(ids, vectors)

    def query(
        self,
        embedding: list[float],
        k: int,
        filters: Filters | None = None,
    ) -> list[Hit]:
        allowlist = None
        if filters:
            allowlist = {
                id_
                for id_, record in self._records.items()
                if _matches_filters(record, filters)
            }
        hits: list[Hit] = []
        for id_, score in self.search(embedding, k=k, allowlist=allowlist):
            record = self._records.get(id_)
            if record is None:
                hits.append({
                    "id": str(id_),
                    "text": "",
                    "score": score,
                    "tenant": "",
                    "properties": {},
                })
                continue
            hits.append({
                "id": record["id"],
                "text": record["text"],
                "score": score,
                "tenant": record["tenant"],
                "properties": record["properties"],
            })
        return hits

    def snapshot_id(self) -> str:
        n = len(self._index) if hasattr(self._index, "__len__") else len(self._records)
        return f"turbovec:n={n}:dim={self.dim}:bw={self.bit_width}"

    def __len__(self) -> int:
        if hasattr(self._index, "__len__"):
            return len(self._index)
        return len(self._records)

    def _id_for(self, id_: str) -> int:
        if id_ not in self._string_to_int_ids:
            self._string_to_int_ids[id_] = len(self._string_to_int_ids) + 1
        return self._string_to_int_ids[id_]


def create_turbovec_store(dim: int, *, bit_width: int = 4) -> VectorStore:
    """Return a real TurboVecStore when importable; else FakeTurboVecStore."""
    try:
        __import__("turbovec")
        __import__("numpy")
    except ImportError:
        return FakeTurboVecStore(dim=dim)
    try:
        return TurboVecStore(dim=dim, bit_width=bit_width)
    except ValueError:
        # Dim not multiple of 8 — fall back so callers with odd dims still work.
        return FakeTurboVecStore(dim=dim)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _matches_filters(record: VectorRecord, filters: Filters) -> bool:
    tenant = filters.get("tenant")
    if tenant is not None and record["tenant"] != tenant:
        return False
    for key, value in (filters.get("properties") or {}).items():
        if record["properties"].get(key) != value:
            return False
    return True
