"""kb_memory_revoke — append an auditable memory revocation."""
from __future__ import annotations

import os
from typing import Any

from chio_pack.memory import repo_root_from_env, revoke_memory

NAME = "kb_memory_revoke"
DESCRIPTION = "Append an auditable revocation for governed agent memory."
INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memory_id": {"type": "string"},
        "reason": {"type": "string"},
        "session_id": {"type": "string"},
        "parent_receipt_hash": {"type": "string"},
    },
    "required": ["memory_id", "reason"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "memory_id" not in arguments or "reason" not in arguments:
        return {
            "status": "error",
            "reason": "missing required arguments: memory_id, reason",
            "tool": NAME,
        }
    write = revoke_memory(
        repo_root_from_env(),
        memory_id=str(arguments["memory_id"]),
        reason=str(arguments["reason"]),
        session_id=str(arguments.get("session_id") or os.environ.get("CHIO_DEV_SESSION_ID") or "default"),
        parent_receipt_hash=arguments.get("parent_receipt_hash"),
    )
    return {
        "status": "ok",
        "tool": NAME,
        "revoked": str(arguments["memory_id"]),
        "path": str(write.path),
        "receipt_hash": write.receipt_hash,
    }
