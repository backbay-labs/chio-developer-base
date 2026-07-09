"""kb_eval — run fixed dogfood retrieval fixtures, return grade/metrics/misses."""
from __future__ import annotations

from typing import Any

NAME = "kb_eval"

DESCRIPTION = "Run fixed dogfood retrieval fixtures and return grade, metrics, and misses."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "format": {"type": "string", "enum": ["json", "markdown"]},
        "suite": {"type": "string", "enum": ["core", "deep", "all", "retrieval"]},
    },
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    from chio_pack.runtime import get_runtime

    rt = get_runtime()
    suite = arguments.get("suite", "all")
    category = arguments.get("category")
    fmt = arguments.get("format", "json")
    try:
        report = rt.run_retrieval_eval(suite=suite, category=category)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "reason": f"eval failed: {exc}",
            "tool": NAME,
        }
    return {
        "status": "ok",
        "tool": NAME,
        "format": fmt,
        "grade": report.get("grade"),
        "metrics": report.get("metrics", {}),
        "misses": report.get("misses", []),
        "report": report,
    }
