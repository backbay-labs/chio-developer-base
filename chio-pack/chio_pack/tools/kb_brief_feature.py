"""kb_brief_feature — agent editing brief from live retrieval tools."""
from __future__ import annotations

from typing import Any

from . import kb_find_docs, kb_find_tests, kb_impact, kb_search_code

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
    query = str(arguments["feature_or_task"])
    limit = int(arguments.get("limit", 8))
    code = kb_search_code.call({"query": query, "limit": limit})
    docs = kb_find_docs.call({"path_or_crate": query, "limit": limit})
    tests = kb_find_tests.call({"path_or_symbol": query, "limit": limit})
    impact = kb_impact.call({"path_or_crate": query, "limit": limit})
    status = "ok"
    if any(r.get("status") == "error" for r in (code, docs, tests, impact)):
        status = "error"
    return {
        "status": status,
        "tool": NAME,
        "echo": {
            "feature_or_task": query,
            "focus_paths": arguments.get("focus_paths") or [],
            "limit": limit,
            "include_memory": arguments.get("include_memory", True),
            "intent": arguments.get("intent", "auto"),
        },
        "code": code.get("results", []),
        "docs": docs.get("results", []),
        "tests": tests.get("results", []),
        "impact": {
            "components": impact.get("components", []),
            "tests": impact.get("tests", []),
            "docs": impact.get("docs", []),
        },
        "memory": [],
        "validation_commands": [
            "make check-boundary",
            "make kb-eval-retrieval",
        ],
    }
