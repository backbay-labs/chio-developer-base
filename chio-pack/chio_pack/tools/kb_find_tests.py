"""kb_find_tests — find tests related to a path, crate, symbol, or concept."""
from __future__ import annotations

from typing import Any

from . import kb_search_code

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
    path = arguments["path_or_symbol"]
    limit = int(arguments.get("limit", 12))
    search = kb_search_code.call(
        {
            "query": f"tests for {path}",
            "limit": limit,
            "filters": {"path_contains": "test"},
        }
    )
    results = [
        r for r in search.get("results", [])
        if "test" in str(r.get("file_path", "")).lower()
        or path.split("/")[-1].split(".")[0] in str(r.get("file_path", ""))
    ]
    if not results:
        results = search.get("results", [])
    return {
        "status": "ok" if search.get("status") == "ok" else search.get("status", "error"),
        "tool": NAME,
        "results": results[:limit],
        "reason": search.get("reason"),
    }
