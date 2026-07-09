"""Governed agent memory stored as signed vault episodes."""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from kb_engine.receipt import sign_response, sha256_json


@dataclass(frozen=True)
class MemoryWrite:
    path: Path
    memory_id: str
    receipt_hash: str


def repo_root_from_env() -> Path:
    env = os.environ.get("CHIO_DEV_REPO")
    if env:
        return Path(env).resolve()
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "PLAN.md").exists() and (candidate / "Makefile").exists():
            return candidate
    return here


def append_memory_entry(
    repo_root: Path,
    *,
    session_id: str,
    text: str,
    title: str = "Governed agent memory",
    source_description: str = "Governed agent memory",
    tags: Iterable[str] = (),
    parent_receipt_hash: str | None = None,
) -> MemoryWrite:
    session = _slug(session_id or "default")
    memory_id = f"memory.{session}.{uuid.uuid4().hex[:12]}"
    path = repo_root / "vault" / "episodes" / f"session-{session}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt_response = sign_response(
        {
            "status": "ok",
            "tool": "kb_memory_add",
            "query": text,
            "results": [{"id": memory_id, "text": text}],
            "index_snapshot": f"vault:{path.name}",
        },
        parent_receipt_hash=parent_receipt_hash,
    )
    receipt_hash = sha256_json(receipt_response["receipt"])
    if not path.exists():
        path.write_text(
            "---\n"
            f"id: episode.session-{session}\n"
            "type: episode-architecture-summary\n"
            "status: active\n"
            f"title: \"Session {session} governed memory\"\n"
            f"graphiti_episode_name: \"Session {session} governed memory\"\n"
            f"source_description: \"{source_description}\"\n"
            "---\n\n"
            f"# Session {session} Governed Memory\n\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as f:
        f.write(f"## {memory_id}\n\n")
        f.write(f"- recorded_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        f.write(f"- title: {title}\n")
        f.write(f"- receipt_hash: {receipt_hash}\n")
        if parent_receipt_hash:
            f.write(f"- parent_receipt_hash: {parent_receipt_hash}\n")
        if tags:
            f.write(f"- tags: {', '.join(tags)}\n")
        f.write("\n")
        f.write(text.strip() + "\n\n")
        f.write("```json\n")
        f.write(json.dumps(receipt_response["receipt"], indent=2, sort_keys=True))
        f.write("\n```\n\n")
    return MemoryWrite(path=path, memory_id=memory_id, receipt_hash=receipt_hash)


def query_memory(repo_root: Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    needle = query.lower()
    results: list[dict[str, str]] = []
    revoked = _revoked_memory_ids(repo_root)
    for path in sorted((repo_root / "vault" / "episodes").glob("session-*.md")):
        text = path.read_text(encoding="utf-8")
        for section in text.split("\n## "):
            if "memory." not in section:
                continue
            memory_id = section.splitlines()[0].strip()
            if not memory_id.startswith("memory."):
                memory_id = memory_id.split()[0] if memory_id else path.stem
            # Skip revocation tombstone sections and previously revoked ids.
            if memory_id in revoked:
                continue
            head = "\n".join(section.splitlines()[:12]).lower()
            if "tags: revocation" in head or "title: revocation for" in head:
                continue
            if "~~memory." in head:
                continue
            haystack = section.lower()
            if needle and needle not in haystack:
                continue
            results.append({
                "id": memory_id,
                "path": str(path),
                "excerpt": "\n".join(section.splitlines()[:8])[:500],
            })
            if len(results) >= limit:
                return results
    return results


def _revoked_memory_ids(repo_root: Path) -> set[str]:
    """Collect memory ids that have an append-only ~~id~~ tombstone somewhere."""
    revoked: set[str] = set()
    pattern = re.compile(r"~~(memory\.[a-zA-Z0-9_.-]+)~~")
    episodes = repo_root / "vault" / "episodes"
    if not episodes.exists():
        return revoked
    for path in episodes.glob("session-*.md"):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            revoked.add(match.group(1))
    return revoked


def revoke_memory(
    repo_root: Path,
    *,
    memory_id: str,
    reason: str,
    session_id: str = "revoke",
    parent_receipt_hash: str | None = None,
) -> MemoryWrite:
    return append_memory_entry(
        repo_root,
        session_id=session_id,
        title=f"Revocation for {memory_id}",
        text=f"~~{memory_id}~~\n\nRevoked memory.\n\nReason: {reason}",
        source_description="Governed agent memory revocation",
        tags=("revocation",),
        parent_receipt_hash=parent_receipt_hash,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-").lower()
    return slug or "default"
