"""kb_impact — estimate related components, tests, and docs for a path or crate.

Phase 1.3+ resolves the path to graph nodes and unions GUARDS / TESTS /
CANONICAL_DOC neighbours, scored by the rank-component blend documented
in arc PR #599. Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_impact"

DESCRIPTION = "Estimate related components, tests, and docs for a path or crate."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path_or_crate": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
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
        "reason": "Phase 1.3+: impact ranker not yet wired (gates Phase 2A)",
        "tool": NAME,
        "echo": {
            "path_or_crate": arguments["path_or_crate"],
            "limit": arguments.get("limit", 50),
        },
        "components": [],
        "tests": [],
        "docs": [],
    }
