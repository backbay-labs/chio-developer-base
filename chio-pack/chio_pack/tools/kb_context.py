"""kb_context — 360-degree incoming/outgoing graph view for one entity.

Phase 1.3+ unions BFS in both directions and joins doc/test refs.
Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_context"

DESCRIPTION = "Return a 360-degree incoming and outgoing graph view for one entity or symbol."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entity": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
    },
    "required": ["entity"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "entity" not in arguments:
        return {"status": "error", "reason": "missing required argument: entity"}
    return {
        "status": "stub",
        "reason": "Phase 1.3+: bidirectional Neo4j traversal not yet wired",
        "tool": NAME,
        "echo": {
            "entity": arguments["entity"],
            "limit": arguments.get("limit", 50),
        },
        "incoming": [],
        "outgoing": [],
    }
