"""Vault-sync daemon. Watches vault/ for changes; runs frontmatter
through Registry; routes DerivedRecords to backing stores.

Per AGENTS.md hard rule #1, this is **the only writer to Graphiti**
(via a configured Router). Agents / Obsidian plugins / hand edits all
write vault files; the daemon materializes those edits into derived
stores idempotently.

Two operating modes:

  - run_once(vault_root)         scan all `*.md` files, derive, exit
  - run_forever(vault_root)      watchdog-based; long-running; calls
                                 process_file() on change events

Idempotency: each processed file's content hash is tracked in an
on-disk state file (`.chio-dev/vault-sync.state.json` by default).
Files whose hash matches the last seen state are skipped.

Routers
-------
A `Router` consumes DerivedRecord objects and writes them to the
appropriate backing store (Neo4j, Graphiti, etc.). Two impls ship:

  - NullRouter       drops everything; used in tests / dry-runs
  - JsonlRouter      append-only audit log; useful for ops + replay

Production routers (GraphitiHttpRouter, Neo4jStoreRouter) wrap the
relevant `kb_engine.store.*` adapters or HTTP clients.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .plugin import Registry
from .types import DerivedRecord


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# === Router protocol + impls ===


class Router(Protocol):
    """Routes derived records to backing stores. Plugins / wiring code
    decide which router(s) to use.
    """

    def write(self, records: Iterable[DerivedRecord]) -> int: ...


class NullRouter:
    """Drops everything. For tests + dry-run."""

    def __init__(self) -> None:
        self.received: list[DerivedRecord] = []

    def write(self, records: Iterable[DerivedRecord]) -> int:
        n = 0
        for r in records:
            self.received.append(r)
            n += 1
        return n


class JsonlRouter:
    """Append-only audit log. Production runs typically chain this with
    a real router so every derivation is replayable.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, records: Iterable[DerivedRecord]) -> int:
        n = 0
        with self.path.open("a") as f:
            for r in records:
                f.write(json.dumps({"target": r.target, "payload": r.payload}) + "\n")
                n += 1
        return n


class GraphitiHttpRouter:
    """POSTs Graphiti-target records to a graphiti-mcp HTTP endpoint.

    Per AGENTS.md hard rule #1, this is the designated Graphiti writer.
    Plugin code never writes Graphiti directly — it produces
    DerivedRecord(target="graphiti", ...) objects, which the daemon
    routes through this class.

    Records with target != "graphiti" are skipped. Each Graphiti record
    becomes one MCP JSON-RPC `tools/call` envelope, by default invoking
    the `add_memory` tool. Constructor takes the MCP URL plus optional
    overrides (tool_name, timeout, strict). For tests the underlying
    HTTP `post` callable is dependency-injected so no real httpx is
    needed.
    """

    DEFAULT_TOOL = "add_memory"

    def __init__(
        self,
        url: str,
        *,
        tool_name: str = DEFAULT_TOOL,
        timeout_seconds: float = 30.0,
        strict: bool = False,
        post: Any = None,
    ) -> None:
        self.url = url
        self.tool_name = tool_name
        self.timeout_seconds = timeout_seconds
        self.strict = strict
        self._post = post
        self._next_id = 1
        self.failures: list[tuple[DerivedRecord, str]] = []

    def _default_post(self, url: str, json: dict[str, Any]) -> Any:
        try:
            import httpx  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "httpx not installed. `pip install kb-engine[http]` "
                "or pass a custom `post` callable."
            ) from e
        return httpx.post(url, json=json, timeout=self.timeout_seconds)

    def _build_envelope(self, record: DerivedRecord) -> dict[str, Any]:
        rpc_id = self._next_id
        self._next_id += 1
        payload = record.payload
        arguments: dict[str, Any] = {
            "name": payload.get("name", ""),
            "episode_body": payload.get("episode_body")
                or json.dumps(payload.get("frontmatter", payload), sort_keys=True),
            "source_description": payload.get("source_description", ""),
            "source": payload.get("source", "json"),
        }
        if "group_id" in payload:
            arguments["group_id"] = payload["group_id"]
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": self.tool_name, "arguments": arguments},
        }

    def write(self, records: Iterable[DerivedRecord]) -> int:
        post = self._post or self._default_post
        n = 0
        for r in records:
            if r.target != "graphiti":
                continue
            envelope = self._build_envelope(r)
            try:
                response = post(self.url, json=envelope)
            except Exception as e:
                self.failures.append((r, str(e)))
                if self.strict:
                    raise
                continue
            status = getattr(response, "status_code", None)
            if status is not None and status >= 400:
                msg = f"HTTP {status}: {getattr(response, 'text', '')[:200]}"
                self.failures.append((r, msg))
                if self.strict:
                    raise RuntimeError(f"Graphiti POST failed: {msg}")
                continue
            n += 1
        return n


# === Frontmatter parsing ===


def _parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (frontmatter_dict | None, body) for a markdown file.

    Uses PyYAML if available; falls back to a minimal key:value parser
    so the daemon works on machines that haven't installed yaml yet.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    raw = m.group(1)
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None, text
    except ImportError:
        # Minimal fallback: parse top-level `key: value` lines.
        data = {}
        for line in raw.splitlines():
            if ":" not in line or line.startswith("  "):
                continue
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip().strip('"').strip("'")
    body = text[m.end():]
    return data, body


def _content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# === Daemon state ===


@dataclass
class SyncState:
    """On-disk state: file path → last-seen content hash."""

    path: Path
    hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if path.exists():
            try:
                with path.open() as f:
                    data = json.load(f)
                return cls(path=path, hashes=dict(data.get("hashes", {})))
            except (OSError, json.JSONDecodeError):
                pass
        return cls(path=path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            json.dump({"hashes": self.hashes}, f, indent=2, sort_keys=True)


@dataclass
class SyncStats:
    files_seen: int = 0
    files_processed: int = 0
    files_skipped_unchanged: int = 0
    files_skipped_no_frontmatter: int = 0
    records_routed: int = 0


# === Daemon ===


class VaultSyncDaemon:
    """Watches a vault and routes frontmatter through Registry hooks.

    Construct with a Registry (with frontmatter handlers registered) +
    one or more Routers. Call run_once() for a one-shot scan.
    """

    def __init__(
        self,
        registry: Registry,
        routers: list[Router],
        state_path: Path | None = None,
    ) -> None:
        self.registry = registry
        self.routers = routers
        if state_path is None:
            state_path = Path.home() / ".chio-dev" / "vault-sync.state.json"
        self.state = SyncState.load(state_path)

    def process_file(self, path: Path) -> tuple[int, str]:
        """Process a single vault file. Returns (records_routed, status).

        Status is one of:
          - "processed"        records derived and routed
          - "unchanged"        content hash matched state, skipped
          - "no_frontmatter"   file has no YAML frontmatter
          - "no_type"          frontmatter has no `type` field
          - "io_error"         file unreadable (logged; counted as skipped)
        """
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return 0, "io_error"

        h = _content_hash(text)
        rel = str(path)
        if self.state.hashes.get(rel) == h:
            return 0, "unchanged"

        frontmatter, _body = _parse_frontmatter(text)
        if frontmatter is None:
            self.state.hashes[rel] = h
            return 0, "no_frontmatter"

        type_ = frontmatter.get("type")
        if not type_:
            self.state.hashes[rel] = h
            return 0, "no_type"

        records = self.registry.handle_frontmatter(type_, frontmatter)
        if not records:
            self.state.hashes[rel] = h
            return 0, "processed"

        n_routed = 0
        for router in self.routers:
            n_routed += router.write(records)
        self.state.hashes[rel] = h
        return n_routed, "processed"

    def run_once(self, vault_root: Path, *, glob: str = "**/*.md") -> SyncStats:
        """One-shot scan of vault_root. Returns aggregate stats and persists state."""
        stats = SyncStats()
        for path in sorted(vault_root.glob(glob)):
            if not path.is_file():
                continue
            stats.files_seen += 1
            n_routed, status = self.process_file(path)
            if status == "unchanged":
                stats.files_skipped_unchanged += 1
            elif status == "no_frontmatter":
                stats.files_skipped_no_frontmatter += 1
            elif status == "processed":
                stats.files_processed += 1
                stats.records_routed += n_routed
        self.state.save()
        return stats

    def run_forever(
        self,
        vault_root: Path,
        *,
        poll_interval: float = 1.0,
        watchdog_handler: Callable[[Path], None] | None = None,
    ) -> None:
        """Long-running watcher. Uses watchdog if available, falls back
        to polling.

        watchdog_handler lets tests inject a custom callback (e.g., to
        capture events without a real filesystem watcher).
        """
        try:
            from watchdog.observers import Observer  # type: ignore
            from watchdog.events import FileSystemEventHandler  # type: ignore
            return self._run_with_watchdog(vault_root, Observer, FileSystemEventHandler)
        except ImportError:
            self._run_polling(vault_root, poll_interval)

    def _run_with_watchdog(self, vault_root: Path, Observer: Any, Handler: Any) -> None:
        daemon = self

        class _Handler(Handler):
            def on_modified(self, event):
                if not event.is_directory and str(event.src_path).endswith(".md"):
                    daemon.process_file(Path(event.src_path))
                    daemon.state.save()

            def on_created(self, event):
                self.on_modified(event)

        observer = Observer()
        observer.schedule(_Handler(), str(vault_root), recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        finally:
            observer.stop()
            observer.join()

    def _run_polling(self, vault_root: Path, poll_interval: float) -> None:
        """Polling fallback. Re-scans the vault on each tick."""
        while True:
            self.run_once(vault_root)
            time.sleep(poll_interval)
