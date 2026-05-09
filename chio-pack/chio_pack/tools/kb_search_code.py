"""kb_search_code — semantic search over indexed Chio code chunks.

Phase 1.3+ wires this to ``kb_engine.store.PostgresStore`` for embedding
search and the chio-pack chunker. Today returns a stub so the plugin
contract round-trips.
"""
from __future__ import annotations

from typing import Any

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
    """Stub. Returns the call shape Phase 1.3+ will populate."""
    if "query" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: query",
        }
    return {
        "status": "stub",
        "reason": "Phase 1.3+: pgvector + chunker not yet wired",
        "tool": NAME,
        "echo": {
            "query": arguments["query"],
            "limit": arguments.get("limit", 8),
            "filters": arguments.get("filters") or {},
        },
        "results": [],
    }
