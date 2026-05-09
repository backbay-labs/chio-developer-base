"""kb_neighbors — return nearby Neo4j knowledge-graph entities.

Phase 1.3+ runs a depth-bounded BFS in Neo4j. Today: stub.
"""
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
    return {
        "status": "stub",
        "reason": "Phase 1.3+: Neo4j BFS not yet wired",
        "tool": NAME,
        "echo": {
            "entity": arguments["entity"],
            "depth": arguments.get("depth", 2),
            "limit": arguments.get("limit", 50),
        },
        "neighbors": [],
    }
