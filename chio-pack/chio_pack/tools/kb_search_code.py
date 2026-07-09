"""kb_search_code — semantic search over indexed Chio code chunks."""
from __future__ import annotations

from typing import Any

from chio_pack.runtime import get_runtime

NAME = "kb_search_code"

DESCRIPTION = "Semantic search over indexed Chio code chunks."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "filters": {"type": "object"},
    },
    "required": ["query"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "query" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: query",
        }
    query = arguments["query"]
    limit = int(arguments.get("limit", 8))
    filters = arguments.get("filters") or {}
    rt = get_runtime()
    if rt is None or rt.postgres is None or rt.embedder is None:
        return {
            "status": "error",
            "reason": "runtime not configured (postgres/embedder unavailable)",
            "tool": NAME,
            "results": [],
        }
    try:
        from chio_pack.ranking import rerank_hits

        vec = rt.embedder([query])[0]
        # Over-fetch then apply shared path prior (same as retrieval-A eval).
        hits = rt.postgres.search_similar(vec, limit=max(limit * 4, 20))
    except Exception as exc:  # noqa: BLE001 — surface as tool error
        return {
            "status": "error",
            "reason": f"search failed: {exc}",
            "tool": NAME,
            "results": [],
        }
    results = []
    for hit in hits:
        if filters.get("language") and hit.get("language") != filters["language"]:
            continue
        if filters.get("path_prefix") and not str(hit.get("file_path", "")).startswith(
            str(filters["path_prefix"])
        ):
            continue
        results.append(
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
        )
    results = rerank_hits(results, query, limit=limit)
    return {
        "status": "ok",
        "tool": NAME,
        "query": query,
        "limit": limit,
        "filters": filters,
        "results": results,
        "index_snapshot": rt.postgres.snapshot_id(),
    }
