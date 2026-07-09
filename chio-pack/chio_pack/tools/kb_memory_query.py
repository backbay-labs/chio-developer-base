"""kb_memory_query — search governed session-memory episodes."""
from __future__ import annotations

from typing import Any

from chio_pack.memory import query_memory, repo_root_from_env

NAME = "kb_memory_query"
DESCRIPTION = "Query governed agent memory stored in vault session episodes."
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["query"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "query" not in arguments:
        return {"status": "error", "reason": "missing required argument: query", "tool": NAME}
    limit = int(arguments.get("limit", 10))
    results = query_memory(repo_root_from_env(), str(arguments["query"]), limit=limit)
    return {
        "status": "ok",
        "tool": NAME,
        "query": str(arguments["query"]),
        "limit": limit,
        "results": results,
    }
