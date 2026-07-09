"""kb_search_docs — semantic search over indexed Chio docs/specs/standards/plans."""
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
    from chio_pack.runtime import get_runtime

    return get_runtime().search_docs(
        query=arguments["query"],
        limit=int(arguments.get("limit", 8)),
        filters=arguments.get("filters") or {},
    )
