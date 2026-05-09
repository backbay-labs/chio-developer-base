"""kb_find_tests — find tests related to a path, crate, symbol, or concept.

Phase 1.3+ traverses the GUARDS / IMPLEMENTS / TESTS edges in Neo4j.
Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_find_tests"

DESCRIPTION = "Find tests related to a path, crate, symbol, or concept."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path_or_symbol": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
    "required": ["path_or_symbol"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "path_or_symbol" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: path_or_symbol",
        }
    return {
        "status": "stub",
        "reason": "Phase 1.3+: Neo4j TESTS edge traversal not yet wired",
        "tool": NAME,
        "echo": {
            "path_or_symbol": arguments["path_or_symbol"],
            "limit": arguments.get("limit", 12),
        },
        "results": [],
    }
