"""kb_eval — run fixed dogfood retrieval fixtures, return grade/metrics/misses.

Phase 1.3+ wires this to ``chio_pack.eval.runner``. Today: stub.
"""
from __future__ import annotations

from typing import Any

NAME = "kb_eval"

DESCRIPTION = "Run fixed dogfood retrieval fixtures and return grade, metrics, and misses."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "format": {"type": "string", "enum": ["json", "markdown"]},
        "suite": {"type": "string", "enum": ["core", "deep", "all"]},
    },
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "stub",
        "reason": "Phase 1.3+: eval runner not yet wired through MCP",
        "tool": NAME,
        "echo": {
            "category": arguments.get("category"),
            "format": arguments.get("format", "json"),
            "suite": arguments.get("suite", "all"),
        },
        "grade": None,
        "metrics": {},
        "misses": [],
    }
