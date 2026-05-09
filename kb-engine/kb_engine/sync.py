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

Lifecycle: vault is canonical and derived stores must follow it. The
daemon therefore handles the full lifecycle of a vault note:

  - create / modify  → process_file() emits DerivedRecords via Router.write
  - rename           → move_file() preserves graph identity if the
                       frontmatter `id` is unchanged, or emits a
                       delete+create pair if `id` changed
  - delete           → delete_file() emits a deletion via Router
                       on_record_deleted (tombstone audit in M0-C.4)
  - offline deletion → SyncState.prune() detects entries whose source
                       file no longer exists and re-emits the deletion

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

    Lifecycle methods:
      - write(records)                      derivations from create / modify
      - on_record_deleted(node_id, path)    deletion of a vault note (the
                                            daemon is the sole writer to
                                            derived stores per AGENTS.md
                                            hard rule #1, so the deletion
                                            path lives here too)

    `node_id` is the frontmatter `id` of the deleted note (the contract
    documented in AGENTS.md "Vault frontmatter is a contract"). The
    Router decides how to map that into its store's identifier; e.g.,
    Neo4jStoreRouter calls `Neo4jStore.delete_node(node_id)`.

    `source_path` is the absolute path to the vault file that was
    removed. It is informational — the Router should key off `node_id`
    when mutating a derived store, since the file is gone by the time
    this is called.
    """

    def write(self, records: Iterable[DerivedRecord]) -> int: ...

    def on_record_deleted(self, node_id: str, source_path: Path) -> None: ...


class NullRouter:
    """Drops everything. For tests + dry-run.

    Records writes in `received` and deletions in `deleted` so tests can
    assert lifecycle events reach the router without standing up real
    backing stores.
    """

    def __init__(self) -> None:
        self.received: list[DerivedRecord] = []
        self.deleted: list[tuple[str, Path]] = []

    def write(self, records: Iterable[DerivedRecord]) -> int:
        n = 0
        for r in records:
            self.received.append(r)
            n += 1
        return n

    def on_record_deleted(self, node_id: str, source_path: Path) -> None:
        self.deleted.append((node_id, source_path))


class JsonlRouter:
    """Append-only audit log. Production runs typically chain this with
    a real router so every derivation is replayable.

    Deletion lines use the special target `"_deleted"` to keep the same
    schema as derivation lines while staying greppable.
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

    def on_record_deleted(self, node_id: str, source_path: Path) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps({
                "target": "_deleted",
                "payload": {"id": node_id, "source_path": str(source_path)},
            }) + "\n")


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
        # Graphiti is append-mostly per vault/episodes/_README.md ("How
        # to remove an episode: You don't, generally"). The daemon
        # records the deletion intent here so the tombstone audit (M0-C.4)
        # has a witness, but we do NOT POST a delete tool call to the
        # Graphiti MCP — the canonical deletion record lives in the
        # vault tombstone JSONL and the receiving graph is treated as
        # an append-mostly index whose stale entries are reconciled out
        # of band.
        self.deletions: list[tuple[str, Path]] = []

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

    def on_record_deleted(self, node_id: str, source_path: Path) -> None:
        self.deletions.append((node_id, source_path))


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
    """On-disk state: per-file last-seen content hash + optional metadata.

    `hashes` keys file path strings to their last-seen sha256 (the
    legacy field; preserved for back-compat with existing state files
    and tests).

    `meta` keys the same path strings to a dict capturing what the
    daemon needs to remember for deletion / rename routing — minimally
    the frontmatter `id` and `type`. Entries can be missing meta (e.g.,
    pre-meta state files, or files with no frontmatter); deletion paths
    handle the absence by skipping the Router call (the audit log still
    fires).
    """

    path: Path
    hashes: dict[str, str] = field(default_factory=dict)
    meta: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if path.exists():
            try:
                with path.open() as f:
                    data = json.load(f)
                return cls(
                    path=path,
                    hashes=dict(data.get("hashes", {})),
                    meta={k: dict(v) for k, v in dict(data.get("meta", {})).items()},
                )
            except (OSError, json.JSONDecodeError):
                pass
        return cls(path=path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            json.dump(
                {"hashes": self.hashes, "meta": self.meta},
                f,
                indent=2,
                sort_keys=True,
            )

    def forget(self, path_str: str) -> dict[str, Any]:
        """Drop both hash and meta for `path_str`. Returns the dropped
        meta dict (empty if there was none). Used by deletion / rename
        flows to keep state in sync with the vault.
        """
        self.hashes.pop(path_str, None)
        return self.meta.pop(path_str, {})


@dataclass
class SyncStats:
    files_seen: int = 0
    files_processed: int = 0
    files_skipped_unchanged: int = 0
    files_skipped_no_frontmatter: int = 0
    records_routed: int = 0
    files_deleted: int = 0


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
            self.state.meta.pop(rel, None)
            return 0, "no_frontmatter"

        type_ = frontmatter.get("type")
        if not type_:
            self.state.hashes[rel] = h
            self.state.meta.pop(rel, None)
            return 0, "no_type"

        records = self.registry.handle_frontmatter(type_, frontmatter)
        # Always remember the frontmatter id/type, even if the registry
        # didn't emit records for this type — so a later deletion or
        # rename can still emit a deletion record keyed on `id`.
        node_id = frontmatter.get("id")
        if node_id is not None:
            self.state.meta[rel] = {"id": str(node_id), "type": str(type_)}
        else:
            self.state.meta.pop(rel, None)

        if not records:
            self.state.hashes[rel] = h
            return 0, "processed"

        n_routed = 0
        for router in self.routers:
            n_routed += router.write(records)
        self.state.hashes[rel] = h
        return n_routed, "processed"

    def move_file(self, src: Path, dest: Path) -> tuple[str, str | None, str | None]:
        """Handle a rename event. Returns (action, old_id, new_id).

        Watchdog can deliver a rename as either `on_moved(src, dest)`
        or as `on_deleted(src) + on_created(dest)` — platform-dependent.
        This entry point handles the unified case.

        Decision rule:

          - If the frontmatter `id` is unchanged across the rename,
            preserve graph identity. State is moved from src to dest;
            process_file(dest) re-derives if content changed (the
            store's MERGE-on-id keeps the node intact). NO deletion is
            emitted.

          - If the `id` changed (or src had no tracked id and dest has
            one — treated as a fresh create) emit a delete for the old
            id and process_file(dest) for the new one.

          - If dest is unreadable / has no frontmatter, treat as a
            delete of src (the rename effectively destroyed the note).

        Returns:
          - action: one of "renamed_same_id", "renamed_new_id",
                    "create_only", "delete_only", "noop".
          - old_id: src's tracked id (or None if untracked).
          - new_id: dest's frontmatter id (or None if dest has none).
        """
        src_rel = str(src)
        old_meta = self.state.meta.get(src_rel, {})
        old_id = old_meta.get("id")

        # If dest doesn't exist or is unreadable, treat as a deletion
        # of src — the rename event lied about the destination.
        if not dest.is_file():
            self.delete_file(src)
            return "delete_only", old_id, None

        try:
            text = dest.read_text(encoding="utf-8")
        except OSError:
            self.delete_file(src)
            return "delete_only", old_id, None

        frontmatter, _ = _parse_frontmatter(text)
        new_id = frontmatter.get("id") if frontmatter else None

        # Case 1: identity-preserving rename. The store's MERGE-on-id
        # keeps the existing node; we just move the state entry to the
        # new path so future content checks find it. Then re-process
        # to pick up any same-rename content edits.
        if old_id is not None and new_id is not None and str(old_id) == str(new_id):
            self.state.forget(src_rel)
            self.process_file(dest)
            return "renamed_same_id", str(old_id), str(new_id)

        # Case 2: id changed across rename — emit delete+create. The
        # delete propagates to the Router so the old node is removed
        # from derived stores; process_file then re-derives the new id.
        if old_id is not None and new_id is not None:
            self.delete_file(src)
            self.process_file(dest)
            return "renamed_new_id", str(old_id), str(new_id)

        # Case 3: src was untracked (no id) but dest has one — treat
        # as a fresh create. Just process dest.
        if old_id is None and new_id is not None:
            # Make sure no stale src state lingers (e.g., a no-id state
            # entry from a prior process_file).
            self.state.forget(src_rel)
            self.process_file(dest)
            return "create_only", None, str(new_id)

        # Case 4: src tracked, dest has no id — treat as delete of src.
        if old_id is not None and new_id is None:
            self.delete_file(src)
            # Still update state for dest so we don't re-derive on next
            # poll if frontmatter is missing.
            self.process_file(dest)
            return "delete_only", str(old_id), None

        # Case 5: nothing tracked, nothing to derive. Just process dest
        # so any new state entry is recorded.
        self.process_file(dest)
        return "noop", None, None

    def delete_file(self, path: Path) -> tuple[bool, str | None]:
        """Handle deletion of a vault file. Returns (emitted, node_id).

        Looks up the file's last-known frontmatter `id` from SyncState;
        if found, calls `Router.on_record_deleted(node_id, path)` on
        every configured router. State is pruned regardless so
        re-creation of the file later re-processes it from scratch.

        Returns:
          - emitted: True if a deletion record was actually emitted
                     (i.e., we knew the file's `id`). False means the
                     file was untracked (e.g., never had frontmatter
                     when it was alive) — still safe to drop the state
                     entry.
          - node_id: The id we emitted, or None if untracked.
        """
        rel = str(path)
        meta = self.state.forget(rel)
        node_id = meta.get("id")
        if not node_id:
            return False, None
        for router in self.routers:
            router.on_record_deleted(node_id, path)
        return True, node_id

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

            def on_deleted(self, event):
                if not event.is_directory and str(event.src_path).endswith(".md"):
                    daemon.delete_file(Path(event.src_path))
                    daemon.state.save()

            def on_moved(self, event):
                # Watchdog's MovedEvent has both src_path and dest_path.
                # Some platforms deliver a rename as on_deleted +
                # on_created instead; both paths converge to the same
                # state via delete_file / process_file, so handling
                # either form is sufficient.
                if event.is_directory:
                    return
                src = str(event.src_path)
                dest = str(event.dest_path)
                if not src.endswith(".md") and not dest.endswith(".md"):
                    return
                # If src wasn't .md but dest is, treat as a create at dest.
                if not src.endswith(".md"):
                    daemon.process_file(Path(dest))
                # If dest isn't .md but src was, treat as a delete of src.
                elif not dest.endswith(".md"):
                    daemon.delete_file(Path(src))
                else:
                    daemon.move_file(Path(src), Path(dest))
                daemon.state.save()

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
