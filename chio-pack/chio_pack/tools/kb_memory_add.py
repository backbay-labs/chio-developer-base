"""kb_memory_add — append governed memory to a signed vault episode."""
from __future__ import annotations

import os
from typing import Any

from chio_pack.memory import append_memory_entry, repo_root_from_env

NAME = "kb_memory_add"
DESCRIPTION = "Append governed agent memory to a signed session episode."
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "session_id": {"type": "string"},
        "title": {"type": "string"},
        "parent_receipt_hash": {"type": "string"},
    },
    "required": ["text"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "text" not in arguments:
        return {"status": "error", "reason": "missing required argument: text", "tool": NAME}
    repo = repo_root_from_env()
    session_id = str(arguments.get("session_id") or os.environ.get("CHIO_DEV_SESSION_ID") or "default")
    write = append_memory_entry(
        repo,
        session_id=session_id,
        text=str(arguments["text"]),
        title=str(arguments.get("title") or "Governed agent memory"),
        parent_receipt_hash=arguments.get("parent_receipt_hash"),
    )
    return {
        "status": "ok",
        "tool": NAME,
        "memory_id": write.memory_id,
        "path": str(write.path),
        "receipt_hash": write.receipt_hash,
    }
