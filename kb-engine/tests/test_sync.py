"""Tests for the vault-sync daemon."""
from __future__ import annotations

import pathlib

import pytest

from kb_engine import DerivedRecord, Registry
from kb_engine.sync import (
    JsonlRouter,
    NullRouter,
    SyncState,
    VaultSyncDaemon,
    _content_hash,
    _parse_frontmatter,
)


# === Frontmatter parsing ===


def test_parse_frontmatter_basic():
    text = "---\ntype: spec\nid: x\n---\n\n# Body\n"
    fm, body = _parse_frontmatter(text)
    assert fm == {"type": "spec", "id": "x"}
    # Regex consumes trailing `\n` after `---`, so body starts with the
    # blank-line newline before "# Body".
    assert "# Body" in body


def test_parse_frontmatter_missing_returns_none():
    fm, body = _parse_frontmatter("# Just a heading\n")
    assert fm is None
    assert body == "# Just a heading\n"


def test_parse_frontmatter_empty_returns_none():
    fm, _ = _parse_frontmatter("---\n---\n")
    assert fm is None


# === SyncState ===


def test_sync_state_round_trip(tmp_path):
    p = tmp_path / "state.json"
    s = SyncState(path=p, hashes={"a.md": "sha256:abc"})
    s.save()
    loaded = SyncState.load(p)
    assert loaded.hashes == {"a.md": "sha256:abc"}


def test_sync_state_missing_file_returns_empty(tmp_path):
    s = SyncState.load(tmp_path / "nope.json")
    assert s.hashes == {}


def test_sync_state_corrupt_file_returns_empty(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{ not valid json")
    s = SyncState.load(p)
    assert s.hashes == {}


# === NullRouter / JsonlRouter ===


def test_null_router_records_writes():
    r = NullRouter()
    n = r.write([DerivedRecord(target="x", payload={"a": 1})])
    assert n == 1
    assert len(r.received) == 1


def test_jsonl_router_appends(tmp_path):
    p = tmp_path / "audit.jsonl"
    r = JsonlRouter(p)
    r.write([DerivedRecord(target="graphiti", payload={"id": "ep.x"})])
    r.write([DerivedRecord(target="neo4j", payload={"id": "spec.x"})])
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    import json

    parsed = [json.loads(line) for line in lines]
    assert parsed[0]["target"] == "graphiti"
    assert parsed[1]["target"] == "neo4j"


# === VaultSyncDaemon ===


def _build_registry_with_handler():
    r = Registry()

    def spec_handler(type, fm):
        yield DerivedRecord(target="neo4j", payload={"id": fm.get("id"), "type": type})

    def episode_handler(type, fm):
        yield DerivedRecord(target="graphiti", payload={"id": fm.get("id"), "type": type})

    r.register_frontmatter_handler("spec", spec_handler)
    r.register_frontmatter_handler("episode-architecture-summary", episode_handler)
    return r


def test_daemon_processes_spec_file(tmp_path):
    vault = tmp_path / "vault"
    (vault / "spec").mkdir(parents=True)
    spec = vault / "spec" / "cap.md"
    spec.write_text("---\ntype: spec\nid: spec.cap\n---\n\nBody.\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    stats = daemon.run_once(vault)
    assert stats.files_seen == 1
    assert stats.files_processed == 1
    assert stats.records_routed == 1
    assert router.received[0].target == "neo4j"
    assert router.received[0].payload["id"] == "spec.cap"


def test_daemon_idempotent_on_unchanged_files(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    stats1 = daemon.run_once(vault)
    assert stats1.files_processed == 1

    # Second run: nothing changed
    stats2 = daemon.run_once(vault)
    assert stats2.files_processed == 0
    assert stats2.files_skipped_unchanged == 1
    # Router only saw one write
    assert len(router.received) == 1


def test_daemon_re_processes_modified_files(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    daemon.run_once(vault)
    # Modify
    note.write_text("---\ntype: spec\nid: spec.x\n---\nDifferent body\n")
    daemon.run_once(vault)
    assert len(router.received) == 2


def test_daemon_skips_files_without_frontmatter(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "no-fm.md").write_text("# Just a heading\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    stats = daemon.run_once(vault)
    assert stats.files_seen == 1
    assert stats.files_skipped_no_frontmatter == 1
    assert stats.records_routed == 0


def test_daemon_skips_unrecognized_types(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "x.md").write_text("---\ntype: weird\nid: x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    stats = daemon.run_once(vault)
    assert stats.files_processed == 1  # we did invoke the handler
    assert stats.records_routed == 0  # but no handler was registered for "weird"


def test_daemon_handles_episode_file_routing_to_graphiti(tmp_path):
    vault = tmp_path / "vault"
    (vault / "episodes").mkdir(parents=True)
    ep = vault / "episodes" / "arch.md"
    ep.write_text(
        "---\ntype: episode-architecture-summary\nid: episode.arch\n---\nSummary.\n"
    )

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    assert len(router.received) == 1
    assert router.received[0].target == "graphiti"
    assert router.received[0].payload["id"] == "episode.arch"


def test_daemon_writes_to_multiple_routers(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "x.md").write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    audit_router = NullRouter()
    main_router = NullRouter()
    daemon = VaultSyncDaemon(registry, [audit_router, main_router],
                              state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    # Each router got the same record
    assert len(audit_router.received) == 1
    assert len(main_router.received) == 1


def test_content_hash_changes_with_content():
    a = _content_hash("hello")
    b = _content_hash("hello world")
    assert a != b
    assert a.startswith("sha256:")
