"""kb_find_docs — find docs related to a path, crate, symbol, or concept.

Phase 1.3+ traverses CANONICAL_DOC / DESCRIBES edges. Today: stub.
"""
from __future__ import annotations

from typing import Any

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
    return {
        "status": "stub",
        "reason": "Phase 1.3+: Neo4j CANONICAL_DOC traversal not yet wired",
        "tool": NAME,
        "echo": {
            "path_or_crate": arguments["path_or_crate"],
            "limit": arguments.get("limit", 12),
        },
        "results": [],
    }
