"""kb_add_episode — add a high-value temporal memory episode.

Per AGENTS.md hard rule #1, this MUST NOT write to Graphiti directly.
Phase 1.4+ this writes a vault note (``vault/episodes/<id>.md``) and the
vault-sync daemon picks it up; the daemon is the only writer to
Graphiti. Today: stub that returns the call shape, no side effects.

The ``write_authorized`` argument is a hook for the gateway — when the
real MCP server framework calls this tool it will pass ``True`` only if
the request came from loopback or carried the bearer token (the
authorization rule in arc PR #599's ``mcp_server.py``).
"""
from __future__ import annotations

from typing import Any

NAME = "kb_add_episode"

DESCRIPTION = "Add a high-value temporal memory episode (writes through vault-sync, not directly to Graphiti)."

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
    return {
        "status": "stub",
        "reason": "Phase 1.4+: vault-sync daemon not yet wired; episode not persisted",
        "tool": NAME,
        "echo": {
            "name": arguments["name"],
            "body_length": len(arguments["body"]),
            "source_description": arguments.get(
                "source_description", "Chio KB user episode"
            ),
        },
        # Phase 1.4+: this is the path the daemon would create.
        "would_write": f"vault/episodes/{_slugify(arguments['name'])}.md",
    }


def _slugify(name: str) -> str:
    out: list[str] = []
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "untitled"
