"""kb_brief_feature — agent editing brief: code, docs, tests, graph impact, memory, validation cmds.

Phase 1.3+ blends ``kb_search_code``, ``kb_find_docs``, ``kb_impact``,
and the temporal-memory query into a single agent-readable brief.
Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_brief_feature"

DESCRIPTION = (
    "Build an agent editing brief with code, docs, tests, graph impact, memory, "
    "and validation commands."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "feature_or_task": {"type": "string"},
        "focus_paths": {"type": "array", "items": {"type": "string"}},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "include_memory": {"type": "boolean"},
        "intent": {
            "type": "string",
            "enum": [
                "auto",
                "capability",
                "revocation",
                "receipt",
                "guard-policy",
                "mcp-adapter",
                "sdk-conformance",
                "release-qualification",
                "compliance-certificate",
                "mercury-product",
                "planning-history",
                "generic",
            ],
        },
    },
    "required": ["feature_or_task"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "feature_or_task" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: feature_or_task",
        }
    return {
        "status": "stub",
        "reason": "Phase 1.3+: brief composer not yet wired",
        "tool": NAME,
        "echo": {
            "feature_or_task": arguments["feature_or_task"],
            "focus_paths": arguments.get("focus_paths") or [],
            "limit": arguments.get("limit", 8),
            "include_memory": arguments.get("include_memory", True),
            "intent": arguments.get("intent", "auto"),
        },
        "code": [],
        "docs": [],
        "tests": [],
        "memory": [],
        "validation_commands": [],
    }
