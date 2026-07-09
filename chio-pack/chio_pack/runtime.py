"""Shared runtime handle for chio-pack MCP tools.

Tools call ``get_runtime()`` to obtain Postgres / Neo4j / Embedder
handles. The MCP gateway sets the runtime at boot; unit tests can
inject a fake via ``set_runtime``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kb_engine.runtime import RuntimeHandles, build_runtime_from_env


@dataclass
class ToolRuntime:
    """Pack-facing runtime: engine handles + vault root for episodes."""

    handles: RuntimeHandles
    vault_root: Path

    @property
    def postgres(self) -> Any:
        return self.handles.postgres

    @property
    def neo4j(self) -> Any:
        return self.handles.neo4j

    @property
    def embedder(self) -> Any:
        return self.handles.embedder

    @property
    def registry(self) -> Any:
        return self.handles.registry

    @property
    def pack_schema(self) -> str:
        return self.handles.pack_schema

    def search_code(
        self,
        query: str,
        *,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from chio_pack.ranking import rerank_hits

        raw = self.handles.search_code(query, limit=max(limit * 4, 20))
        results = [
            {
                "file_path": hit.get("file_path"),
                "language": hit.get("language"),
                "line_start": hit.get("line_start"),
                "line_end": hit.get("line_end"),
                "chunk_text": hit.get("chunk_text"),
                "similarity": float(hit.get("similarity") or 0.0),
                "rank_components": {
                    "cosine": float(hit.get("similarity") or 0.0),
                },
            }
            for hit in raw
        ]
        if filters:
            if filters.get("language"):
                results = [r for r in results if r.get("language") == filters["language"]]
            if filters.get("path_prefix"):
                prefix = str(filters["path_prefix"])
                results = [
                    r for r in results if str(r.get("file_path") or "").startswith(prefix)
                ]
        results = rerank_hits(results, query, limit=limit)
        return {
            "status": "ok",
            "tool": "kb_search_code",
            "query": query,
            "limit": limit,
            "filters": filters or {},
            "results": results,
            "index_snapshot": self.handles.snapshot_id(),
        }

    def search_docs(
        self,
        query: str,
        *,
        limit: int = 8,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from chio_pack.ranking import rerank_hits

        raw = self.handles.search_docs(query, limit=max(limit * 4, 20))
        results = [
            {
                "file_path": hit.get("file_path"),
                "language": hit.get("language"),
                "line_start": hit.get("line_start"),
                "line_end": hit.get("line_end"),
                "chunk_text": hit.get("chunk_text"),
                "similarity": float(hit.get("similarity") or 0.0),
                "rank_components": {
                    "cosine": float(hit.get("similarity") or 0.0),
                },
            }
            for hit in raw
        ]
        if filters:
            if filters.get("language"):
                results = [r for r in results if r.get("language") == filters["language"]]
            if filters.get("path_prefix"):
                prefix = str(filters["path_prefix"])
                results = [
                    r for r in results if str(r.get("file_path") or "").startswith(prefix)
                ]
        results = rerank_hits(results, query, limit=limit)
        return {
            "status": "ok",
            "tool": "kb_search_docs",
            "query": query,
            "limit": limit,
            "filters": filters or {},
            "results": results,
            "index_snapshot": self.handles.snapshot_id(),
        }

    def neighbors(
        self,
        entity: str,
        *,
        depth: int = 2,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.handles.neighbors(entity, depth=depth, limit=limit)

    def add_episode(
        self,
        name: str,
        body: str,
        *,
        source_description: str = "Chio KB user episode",
    ) -> str:
        """Write ``vault/episodes/<slug>.md`` (AGENTS.md hard rule #1).

        Does not write Graphiti; vault-sync is the only Graphiti writer.
        Distinct from ``kb_memory_*`` session append files.
        """
        import re
        import time

        vault = self.vault_root
        if vault is None:
            raise RuntimeError("vault_root not configured")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled"
        # Keep ids unique if the same name is written twice.
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        path = vault / "episodes" / f"{slug}-{stamp}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        episode_id = f"episode.{slug}.{stamp}"
        path.write_text(
            "---\n"
            f"id: {episode_id}\n"
            "type: episode-architecture-summary\n"
            "status: active\n"
            f'title: "{name}"\n'
            f'graphiti_episode_name: "{name}"\n'
            f'source_description: "{source_description}"\n'
            "---\n\n"
            f"# {name}\n\n"
            f"{body.strip()}\n",
            encoding="utf-8",
        )
        return str(path)


_RUNTIME: ToolRuntime | None = None


def set_runtime(runtime: ToolRuntime | None) -> None:
    global _RUNTIME
    _RUNTIME = runtime


configure_runtime = set_runtime
ChioRuntime = ToolRuntime


def get_runtime() -> ToolRuntime | None:
    return _RUNTIME or ensure_runtime_from_env()


def ensure_runtime_from_env() -> ToolRuntime:
    """Build and cache a runtime from environment variables."""
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    handles = build_runtime_from_env()
    vault = Path(
        __import__("os").environ.get("CHIO_KB_VAULT_ROOT", "/vault")
    )
    _RUNTIME = ToolRuntime(handles=handles, vault_root=vault)
    return _RUNTIME
