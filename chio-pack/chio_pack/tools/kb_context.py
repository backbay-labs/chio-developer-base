"""kb_context — 360-degree incoming/outgoing graph view for one entity."""
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
    from chio_pack.runtime import get_runtime

    rt = get_runtime()
    limit = int(arguments.get("limit", 50))
    neighbors = rt.neighbors(str(arguments["entity"]), depth=1, limit=limit)
    return {
        "status": "ok",
        "tool": NAME,
        "entity": arguments["entity"],
        "incoming": neighbors,
        "outgoing": neighbors,
        "rank_components": {"graph_bfs": 1.0},
    }
