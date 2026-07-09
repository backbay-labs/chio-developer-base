"""kb_neighbors — return nearby Neo4j knowledge-graph entities."""
from __future__ import annotations

from typing import Any

NAME = "kb_neighbors"

DESCRIPTION = "Return nearby Neo4j knowledge graph entities."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entity": {"type": "string"},
        "depth": {"type": "integer", "minimum": 1, "maximum": 4},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
    },
    "required": ["entity"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "entity" not in arguments:
        return {"status": "error", "reason": "missing required argument: entity"}
    from chio_pack.runtime import get_runtime

    rt = get_runtime()
    depth = int(arguments.get("depth", 2))
    limit = int(arguments.get("limit", 50))
    neighbors = rt.neighbors(arguments["entity"], depth=depth, limit=limit)
    return {
        "status": "ok",
        "tool": NAME,
        "entity": arguments["entity"],
        "depth": depth,
        "limit": limit,
        "neighbors": neighbors,
    }
