"""kb_find_docs — find docs related to a path, crate, symbol, or concept."""
from __future__ import annotations

from typing import Any

from . import kb_search_docs

NAME = "kb_find_docs"

DESCRIPTION = "Find docs related to a path, crate, symbol, or concept."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path_or_crate": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["path_or_crate"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "path_or_crate" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: path_or_crate",
        }
    path = arguments["path_or_crate"]
    result = kb_search_docs.call(
        {
            "query": path,
            "limit": arguments.get("limit", 12),
        }
    )
    result["tool"] = NAME
    result["echo"] = {
        "path_or_crate": path,
        "limit": arguments.get("limit", 12),
    }
    return result
