"""kb_add_episode — add a high-value temporal memory episode.

Per AGENTS.md hard rule #1, this MUST NOT write to Graphiti directly.
Writes ``vault/episodes/<id>.md``; vault-sync is the only Graphiti writer.
"""
from __future__ import annotations

from typing import Any

from chio_pack.runtime import get_runtime

NAME = "kb_add_episode"

DESCRIPTION = (
    "Add a high-value temporal memory episode "
    "(writes through vault-sync, not directly to Graphiti)."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "body": {"type": "string"},
        "source_description": {"type": "string"},
    },
    "required": ["name", "body"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "name" not in arguments or "body" not in arguments:
        return {
            "status": "error",
            "reason": "missing required arguments: name, body",
        }
    rt = get_runtime()
    if rt is None:
        return {
            "status": "error",
            "reason": "runtime not configured",
            "tool": NAME,
        }
    try:
        path = rt.add_episode(
            str(arguments["name"]),
            str(arguments["body"]),
            source_description=str(
                arguments.get("source_description", "Chio KB user episode")
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "reason": f"episode write failed: {exc}",
            "tool": NAME,
        }
    return {
        "status": "ok",
        "tool": NAME,
        "wrote": path,
        "note": "vault-sync daemon will derive Graphiti episode from this note",
    }


def _slugify(name: str) -> str:
    out: list[str] = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "untitled"
