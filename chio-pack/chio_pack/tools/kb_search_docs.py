"""kb_search_docs — semantic search over indexed Chio docs/specs/standards/plans.

Phase 1.3+ wires this to the doc-corpus pgvector index. Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_search_docs"

DESCRIPTION = "Semantic search over indexed Chio docs, specs, standards, and plans."

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
        return {"status": "error", "reason": "missing required argument: query"}
    return {
        "status": "stub",
        "reason": "Phase 1.3+: doc-corpus index not yet wired",
        "tool": NAME,
        "echo": {
            "query": arguments["query"],
            "limit": arguments.get("limit", 8),
            "filters": arguments.get("filters") or {},
        },
        "results": [],
    }
