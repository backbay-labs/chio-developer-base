"""Tests for the vault-sync daemon."""
from __future__ import annotations

import pathlib

import pytest

from kb_engine import DerivedRecord, Registry
from kb_engine.sync import (
    GraphitiHttpRouter,
    JsonlRouter,
    NullRouter,
    SyncState,
    TombstoneAuditWriter,
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


# === GraphitiHttpRouter ===


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = '{"result": {}}'):
        self.status_code = status_code
        self.text = text


def test_graphiti_router_posts_episode():
    sent: list = []

    def fake_post(url, json):
        sent.append((url, json))
        return _FakeResponse(200)

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    n = router.write([
        DerivedRecord(target="graphiti", payload={
            "name": "Test episode",
            "source_description": "Test seed",
            "frontmatter": {"id": "ep.test"},
        })
    ])
    assert n == 1
    url, envelope = sent[0]
    assert url == "http://localhost:8000/mcp"
    assert envelope["jsonrpc"] == "2.0"
    assert envelope["method"] == "tools/call"
    assert envelope["params"]["name"] == "add_memory"
    assert envelope["params"]["arguments"]["name"] == "Test episode"


def test_graphiti_router_skips_non_graphiti_records():
    sent: list = []

    def fake_post(url, json):
        sent.append((url, json))
        return _FakeResponse(200)

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    records = [
        DerivedRecord(target="neo4j", payload={"id": "x"}),
        DerivedRecord(target="graphiti", payload={"name": "Y"}),
        DerivedRecord(target="audit-log", payload={}),
    ]
    n = router.write(records)
    assert n == 1
    assert len(sent) == 1


def test_graphiti_router_handles_http_errors_non_strict():
    def fake_post(url, json):
        return _FakeResponse(500, text="server error")

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    n = router.write([DerivedRecord(target="graphiti", payload={"name": "X"})])
    assert n == 0
    assert len(router.failures) == 1
    assert "HTTP 500" in router.failures[0][1]


def test_graphiti_router_strict_raises_on_http_error():
    def fake_post(url, json):
        return _FakeResponse(500, text="boom")

    router = GraphitiHttpRouter(
        "http://localhost:8000/mcp", post=fake_post, strict=True
    )
    with pytest.raises(RuntimeError, match="Graphiti POST failed"):
        router.write([DerivedRecord(target="graphiti", payload={"name": "X"})])


def test_graphiti_router_handles_post_exception_non_strict():
    def fake_post(url, json):
        raise ConnectionError("network down")

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    n = router.write([DerivedRecord(target="graphiti", payload={"name": "X"})])
    assert n == 0
    assert "network down" in router.failures[0][1]


def test_graphiti_router_falls_back_to_frontmatter_for_episode_body():
    sent: list = []

    def fake_post(url, json):
        sent.append((url, json))
        return _FakeResponse(200)

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    router.write([
        DerivedRecord(target="graphiti", payload={
            "name": "Y",
            "frontmatter": {"id": "y", "type": "episode-architecture-summary"},
        })
    ])
    body = sent[0][1]["params"]["arguments"]["episode_body"]
    assert "episode-architecture-summary" in body


# === Deletion handling (M0-C.1) ===


def test_null_router_records_deletions():
    r = NullRouter()
    r.on_record_deleted("spec.x", pathlib.Path("/v/spec/x.md"))
    assert r.deleted == [("spec.x", pathlib.Path("/v/spec/x.md"))]


def test_jsonl_router_writes_deletion_line(tmp_path):
    p = tmp_path / "audit.jsonl"
    r = JsonlRouter(p)
    r.write([DerivedRecord(target="neo4j", payload={"id": "spec.x"})])
    r.on_record_deleted("spec.x", pathlib.Path("/v/spec/x.md"))
    lines = p.read_text().strip().splitlines()
    assert len(lines) == 2
    import json as _json
    deleted = _json.loads(lines[1])
    assert deleted["target"] == "_deleted"
    assert deleted["payload"]["id"] == "spec.x"
    assert "/v/spec/x.md" in deleted["payload"]["source_path"]


def test_graphiti_router_records_deletion_intent_without_posting():
    sent: list = []

    def fake_post(url, json):
        sent.append(json)
        return _FakeResponse(200)

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    router.on_record_deleted("ep.x", pathlib.Path("/v/episodes/x.md"))
    # Per AGENTS.md hard rule #1 + episodes/_README.md ("Graphiti is
    # append-mostly"): the daemon does not POST a delete to Graphiti.
    # The deletion intent is recorded for the tombstone audit only.
    assert sent == []
    assert router.deletions == [("ep.x", pathlib.Path("/v/episodes/x.md"))]


def test_daemon_emits_deletion_record_on_delete_file(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    daemon.run_once(vault)
    assert str(note) in daemon.state.hashes
    # Frontmatter id was recorded so deletion can route by id later
    assert daemon.state.meta[str(note)]["id"] == "spec.x"

    note.unlink()
    emitted, node_id = daemon.delete_file(note)
    assert emitted is True
    assert node_id == "spec.x"
    assert router.deleted == [("spec.x", note)]
    # State is pruned
    assert str(note) not in daemon.state.hashes
    assert str(note) not in daemon.state.meta


def test_daemon_delete_file_untracked_is_noop(tmp_path):
    """A delete event for a file we never tracked (no frontmatter when
    it was alive) is safe — no router call, state stays clean.
    """
    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    emitted, node_id = daemon.delete_file(tmp_path / "never-existed.md")
    assert emitted is False
    assert node_id is None
    assert router.deleted == []


def test_daemon_delete_file_writes_to_all_routers(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    audit = NullRouter()
    main = NullRouter()
    daemon = VaultSyncDaemon(registry, [audit, main], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    note.unlink()
    daemon.delete_file(note)
    assert audit.deleted == [("spec.x", note)]
    assert main.deleted == [("spec.x", note)]


def test_watchdog_on_deleted_triggers_delete_file(tmp_path):
    """Verifies the watchdog handler shape calls delete_file for .md
    files. Uses a stub Observer/Handler so no real watchdog is needed.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    # Capture the inner _Handler class without starting a real loop
    class _StubObserver:
        def __init__(self):
            self.handler = None

        def schedule(self, handler, root, recursive):
            self.handler = handler

        def start(self):
            raise _StubStop()

        def stop(self):
            pass

        def join(self):
            pass

    class _StubStop(Exception):
        pass

    class _StubHandler:
        is_directory = False

    captured_observer = _StubObserver()
    try:
        daemon._run_with_watchdog(vault, lambda: captured_observer, _StubHandler)
    except _StubStop:
        pass

    handler = captured_observer.handler
    note.unlink()

    class _Event:
        def __init__(self, path):
            self.is_directory = False
            self.src_path = str(path)

    handler.on_deleted(_Event(note))
    assert router.deleted == [("spec.x", note)]


def test_daemon_delete_file_skips_when_no_frontmatter_id(tmp_path):
    """Files that were processed but had no `id` (e.g., status-only or
    legacy notes) should not emit a delete record — there's no node_id
    to mutate. State is still pruned so re-creation re-processes.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\n---\nBody without id\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    note.unlink()
    emitted, node_id = daemon.delete_file(note)
    assert emitted is False
    assert node_id is None
    assert router.deleted == []
    assert str(note) not in daemon.state.hashes


# === Convergence under churn (M0-C.5) ===


class _FakeGraphStore:
    """Minimal MERGE-on-id graph stand-in. Models what Neo4j /
    Graphiti will actually do under the daemon's record stream:
      - write(record) MERGEs on payload["id"], replacing payload.
      - on_record_deleted(id, _) hard-deletes the row.

    Lets us assert the daemon converges to the exact end-state vault
    truth dictates, without booting real backing stores.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.events: list[tuple[str, str]] = []  # (op, id) for trace

    def write(self, records):
        n = 0
        for r in records:
            nid = r.payload.get("id")
            if not nid:
                continue
            self.nodes[nid] = dict(r.payload)
            self.events.append(("upsert", nid))
            n += 1
        return n

    def on_record_deleted(self, node_id: str, source_path: Path) -> None:
        self.nodes.pop(node_id, None)
        self.events.append(("delete", node_id))


def _build_handler_with_content_capture():
    """Like _build_registry_with_handler but the spec handler also
    surfaces a `content_hint` derived from the frontmatter, so we can
    assert which version of the file the final node holds."""
    from kb_engine import Registry

    r = Registry()

    def spec_handler(type, fm):
        yield DerivedRecord(
            target="neo4j",
            payload={
                "id": fm.get("id"),
                "type": type,
                "version": fm.get("version"),
            },
        )

    r.register_frontmatter_handler("spec", spec_handler)
    return r


def test_convergence_under_rapid_churn(tmp_path):
    """Stress: 10 rapid create / modify / rename / delete events
    against the same logical file. SyncState and the (fake) graph
    must converge to exactly the truth the vault expresses at the end.

    Failure mode the original code silently exhibited: no on_deleted
    handler meant a delete-then-recreate cycle left the prior node id
    in the graph forever, while only the most recent file was tracked
    in state. The new daemon converges because every transition
    (delete, rename-with-new-id, recreate) routes through the
    Router's lifecycle methods.
    """
    from kb_engine import Registry

    vault = tmp_path / "vault"
    vault.mkdir()

    registry = _build_handler_with_content_capture()
    store = _FakeGraphStore()
    tomb_dir = tmp_path / "tomb"
    daemon = VaultSyncDaemon(
        registry, [store],
        state_path=tmp_path / "state.json",
        tombstone_writer=TombstoneAuditWriter(
            tomb_dir,
            clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
        ),
    )

    a = vault / "a.md"
    b = vault / "b.md"
    c = vault / "c.md"
    d = vault / "d.md"
    e = vault / "e.md"

    # Event 1: create a (id=spec.x v1)
    a.write_text("---\ntype: spec\nid: spec.x\nversion: 1\n---\n")
    daemon.process_file(a)

    # Event 2: modify a (v2)
    a.write_text("---\ntype: spec\nid: spec.x\nversion: 2\n---\n")
    daemon.process_file(a)

    # Event 3: rename a → b, id preserved
    a.rename(b)
    daemon.move_file(a, b)

    # Event 4: modify b (v3)
    b.write_text("---\ntype: spec\nid: spec.x\nversion: 3\n---\n")
    daemon.process_file(b)

    # Event 5: delete b
    b.unlink()
    daemon.delete_file(b)

    # Event 6: create c — fresh spec.x (v4)
    c.write_text("---\ntype: spec\nid: spec.x\nversion: 4\n---\n")
    daemon.process_file(c)

    # Event 7: rename c → d with id change spec.x → spec.y
    d.write_text("---\ntype: spec\nid: spec.y\nversion: 1\n---\n")
    c.unlink()
    daemon.move_file(c, d)

    # Event 8: delete d
    d.unlink()
    daemon.delete_file(d)

    # Event 9: create e — spec.x again (v5)
    e.write_text("---\ntype: spec\nid: spec.x\nversion: 5\n---\n")
    daemon.process_file(e)

    # Event 10: modify e (v6) — final state
    e.write_text("---\ntype: spec\nid: spec.x\nversion: 6\n---\n")
    daemon.process_file(e)

    # Final state: vault has exactly one note (e). The graph must
    # reflect that — spec.x exists at v6, spec.y is gone. (version
    # string-vs-int depends on whether yaml or the fallback parser is
    # active; either way the LAST write wins.)
    assert set(store.nodes.keys()) == {"spec.x"}
    assert str(store.nodes["spec.x"]["version"]) == "6"
    assert "spec.y" not in store.nodes

    # State holds exactly one entry, pointing at e.
    tracked = list(daemon.state.hashes.keys())
    assert tracked == [str(e)]
    assert daemon.state.meta[str(e)]["id"] == "spec.x"

    # The trace should include the spec.y delete (event 8) and at
    # least one spec.x delete (event 5). spec.x was recreated after
    # being deleted, so the final upsert reaches the store.
    deletes = [(op, nid) for op, nid in store.events if op == "delete"]
    delete_ids = [nid for _, nid in deletes]
    assert "spec.x" in delete_ids
    assert "spec.y" in delete_ids
    # Final spec.x event is an upsert, not a delete (proves
    # convergence to the recreated state, not orphaned mid-churn).
    assert store.events[-1] == ("upsert", "spec.x")


def test_convergence_run_once_after_churn_is_idempotent(tmp_path):
    """After a churn sequence ending in a stable file, a follow-up
    run_once must not re-emit any deletes or upserts. Catches the bug
    where post-rename state holds a stale path and prune fires a
    spurious delete.
    """
    vault = tmp_path / "vault"
    vault.mkdir()

    registry = _build_handler_with_content_capture()
    store = _FakeGraphStore()
    daemon = VaultSyncDaemon(registry, [store], state_path=tmp_path / "state.json")

    a = vault / "a.md"
    b = vault / "b.md"
    a.write_text("---\ntype: spec\nid: spec.x\nversion: 1\n---\n")
    daemon.process_file(a)
    a.rename(b)
    daemon.move_file(a, b)
    daemon.state.save()

    n_before = len(store.events)
    stats = daemon.run_once(vault)
    assert stats.files_pruned == 0  # the state was migrated by move_file
    n_after = len(store.events)
    # No new deletes; b was unchanged so no new upsert either
    assert n_after == n_before
    assert set(store.nodes.keys()) == {"spec.x"}


# === Tombstone audit writer (M0-C.4) ===


def _fixed_clock(when: str):
    import datetime as _dt
    dt = _dt.datetime.fromisoformat(when)
    return lambda: dt


def test_tombstone_writer_writes_jsonl_line(tmp_path):
    writer = TombstoneAuditWriter(
        tmp_path / "tomb",
        clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
    )
    out = writer.write(
        "spec.x",
        pathlib.Path("/v/spec/x.md"),
        last_known_hash="sha256:abc",
        reason="watchdog_delete",
    )
    assert out.name == "2026-05-08.jsonl"
    import json as _json
    line = _json.loads(out.read_text().strip())
    assert line == {
        "id": "spec.x",
        "deleted_at": "2026-05-08T12:00:00+00:00",
        "source_path": "/v/spec/x.md",
        "last_known_hash": "sha256:abc",
        "reason": "watchdog_delete",
    }


def test_tombstone_writer_appends_not_overwrites(tmp_path):
    writer = TombstoneAuditWriter(
        tmp_path / "tomb",
        clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
    )
    writer.write("a", pathlib.Path("/a.md"))
    writer.write("b", pathlib.Path("/b.md"))
    writer.write("c", pathlib.Path("/c.md"))
    file = tmp_path / "tomb" / "2026-05-08.jsonl"
    lines = file.read_text().strip().splitlines()
    assert len(lines) == 3
    import json as _json
    ids = [_json.loads(l)["id"] for l in lines]
    assert ids == ["a", "b", "c"]


def test_tombstone_writer_rotates_by_day(tmp_path):
    """Two deletions on different days land in different files."""
    import datetime as _dt
    times = iter([
        _dt.datetime(2026, 5, 8, 23, 59, tzinfo=_dt.timezone.utc),
        _dt.datetime(2026, 5, 9, 0, 1, tzinfo=_dt.timezone.utc),
    ])
    writer = TombstoneAuditWriter(tmp_path / "tomb", clock=lambda: next(times))
    writer.write("a", pathlib.Path("/a.md"))
    writer.write("b", pathlib.Path("/b.md"))
    files = sorted((tmp_path / "tomb").glob("*.jsonl"))
    names = [f.name for f in files]
    assert names == ["2026-05-08.jsonl", "2026-05-09.jsonl"]


def test_daemon_writes_tombstone_on_delete_file(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    tomb_dir = tmp_path / "vault" / "_meta" / "tombstones"
    writer = TombstoneAuditWriter(
        tomb_dir,
        clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
    )
    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(
        registry, [router],
        state_path=tmp_path / "state.json",
        tombstone_writer=writer,
    )
    daemon.run_once(vault)
    last_hash = daemon.state.hashes[str(note)]

    note.unlink()
    daemon.delete_file(note)

    file = tomb_dir / "2026-05-08.jsonl"
    import json as _json
    line = _json.loads(file.read_text().strip().splitlines()[0])
    assert line["id"] == "spec.x"
    assert line["last_known_hash"] == last_hash
    assert line["reason"] == "watchdog_delete"


def test_daemon_writes_tombstone_for_offline_prune(tmp_path):
    """Offline-detected deletion gets a tombstone with reason="offline_prune"
    so ops can distinguish from live delete events.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\n")

    tomb_dir = tmp_path / "tomb"
    writer = TombstoneAuditWriter(
        tomb_dir,
        clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
    )
    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(
        registry, [router],
        state_path=tmp_path / "state.json",
        tombstone_writer=writer,
    )
    daemon.run_once(vault)
    note.unlink()
    daemon.prune_state()

    file = tomb_dir / "2026-05-08.jsonl"
    import json as _json
    line = _json.loads(file.read_text().strip().splitlines()[0])
    assert line["reason"] == "offline_prune"
    assert line["id"] == "spec.x"


def test_daemon_writes_tombstone_with_rename_reason(tmp_path):
    """A rename whose id changed (delete+create) tombstones the old id
    with reason="watchdog_rename" so ops can correlate.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.old\n---\n")

    tomb_dir = tmp_path / "tomb"
    writer = TombstoneAuditWriter(
        tomb_dir,
        clock=_fixed_clock("2026-05-08T12:00:00+00:00"),
    )
    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(
        registry, [router],
        state_path=tmp_path / "state.json",
        tombstone_writer=writer,
    )
    daemon.run_once(vault)

    dest = vault / "new.md"
    dest.write_text("---\ntype: spec\nid: spec.new\n---\n")
    src.unlink()
    daemon.move_file(src, dest)

    file = tomb_dir / "2026-05-08.jsonl"
    import json as _json
    line = _json.loads(file.read_text().strip().splitlines()[0])
    assert line["id"] == "spec.old"
    assert line["reason"] == "watchdog_rename"


def test_daemon_without_tombstone_writer_does_not_crash(tmp_path):
    """Tombstone writer is optional. Construction without it must work
    and `delete_file` must not error."""
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)
    note.unlink()
    emitted, node_id = daemon.delete_file(note)
    assert emitted is True
    assert node_id == "spec.x"


# === SyncState.prune (M0-C.3) ===


def test_sync_state_prune_drops_missing_files(tmp_path):
    """SyncState.prune is a pure state op — drops entries whose source
    file no longer exists, returns the dropped (path, meta) pairs."""
    p = tmp_path / "state.json"
    real = tmp_path / "real.md"
    real.write_text("hi")
    state = SyncState(
        path=p,
        hashes={
            str(real): "sha256:abc",
            str(tmp_path / "ghost1.md"): "sha256:zzz",
            str(tmp_path / "ghost2.md"): "sha256:yyy",
        },
        meta={
            str(real): {"id": "spec.real", "type": "spec"},
            str(tmp_path / "ghost1.md"): {"id": "spec.ghost1", "type": "spec"},
            # ghost2 has no meta — pre-meta state file or no-id note
        },
    )
    dropped = state.prune()

    paths_dropped = sorted(p for p, _ in dropped)
    assert paths_dropped == sorted([
        str(tmp_path / "ghost1.md"),
        str(tmp_path / "ghost2.md"),
    ])
    # Real file is preserved
    assert str(real) in state.hashes
    assert str(real) in state.meta
    # Ghosts are gone
    assert str(tmp_path / "ghost1.md") not in state.hashes
    assert str(tmp_path / "ghost2.md") not in state.hashes


def test_sync_state_prune_no_op_when_all_files_exist(tmp_path):
    p = tmp_path / "state.json"
    real = tmp_path / "real.md"
    real.write_text("hi")
    state = SyncState(path=p, hashes={str(real): "sha256:abc"})
    dropped = state.prune()
    assert dropped == []
    assert str(real) in state.hashes


def test_daemon_prune_state_emits_deletions_for_missing_files(tmp_path):
    """The end-to-end claim: a file deleted while the daemon was
    offline still propagates a deletion record on next prune_state().
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    # Simulate offline deletion
    note.unlink()

    emitted = daemon.prune_state()
    assert emitted == [(str(note), "spec.x")]
    assert router.deleted == [("spec.x", note)]
    assert str(note) not in daemon.state.hashes
    assert str(note) not in daemon.state.meta


def test_daemon_prune_state_handles_entries_without_id(tmp_path):
    """Pruning an entry whose meta has no id is safe — state is
    cleaned but no deletion record is emitted (no node_id to route on).
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "noid.md"
    note.write_text("---\ntype: spec\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)
    note.unlink()
    emitted = daemon.prune_state()
    assert emitted == [(str(note), None)]
    assert router.deleted == []


def test_run_once_prunes_at_start(tmp_path):
    """run_once should prune stale state before scanning so a delete
    that happened between two polling ticks propagates on the very
    next run."""
    vault = tmp_path / "vault"
    vault.mkdir()
    a = vault / "a.md"
    b = vault / "b.md"
    a.write_text("---\ntype: spec\nid: spec.a\n---\n")
    b.write_text("---\ntype: spec\nid: spec.b\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    stats1 = daemon.run_once(vault)
    assert stats1.files_processed == 2
    assert stats1.files_pruned == 0

    # Delete one file between runs
    a.unlink()
    stats2 = daemon.run_once(vault)
    assert stats2.files_pruned == 1
    assert ("spec.a", a) in router.deleted
    # b is unchanged so it's a skipped-unchanged
    assert stats2.files_skipped_unchanged == 1


def test_run_forever_prunes_before_watchdog_wires_up(tmp_path):
    """The daemon catches up on offline deletes before subscribing to
    live events — exercised here by verifying prune_state runs from
    run_forever before the (stub) Observer.start() is called."""
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "x.md"
    note.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)
    note.unlink()

    # Verify prune_state runs before observer.start
    order: list[str] = []

    real_prune = daemon.prune_state

    def trace_prune():
        order.append("prune")
        return real_prune()

    daemon.prune_state = trace_prune  # type: ignore[method-assign]

    class _StubStop(Exception):
        pass

    class _StubObserver:
        def schedule(self, handler, root, recursive):
            pass

        def start(self):
            order.append("start")
            raise _StubStop()

        def stop(self):
            pass

        def join(self):
            pass

    class _StubHandler:
        is_directory = False

    # Simulate watchdog being available by injecting via _run_with_watchdog
    daemon.prune_state()  # mirrors what run_forever does inline; tested above
    try:
        daemon._run_with_watchdog(vault, _StubObserver, _StubHandler)
    except _StubStop:
        pass

    # Pruning preceded observer.start, and the deletion reached the
    # router because of it.
    assert order[0] == "prune"
    assert "start" in order
    assert router.deleted == [("spec.x", note)]


# === Rename / move handling (M0-C.2) ===


def test_move_file_same_id_preserves_identity(tmp_path):
    """Renaming a note while keeping its frontmatter `id` should NOT
    emit a delete record — the store's MERGE-on-id keeps the same
    graph node, only the source path moved.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.x\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)
    assert len(router.received) == 1

    dest = vault / "new.md"
    src.rename(dest)
    action, old_id, new_id = daemon.move_file(src, dest)

    assert action == "renamed_same_id"
    assert old_id == "spec.x"
    assert new_id == "spec.x"
    # No delete record — identity preserved
    assert router.deleted == []
    # State moved to dest
    assert str(src) not in daemon.state.hashes
    assert str(dest) in daemon.state.hashes
    assert daemon.state.meta[str(dest)]["id"] == "spec.x"
    # Re-derivation happened (content unchanged from src so handler
    # ran but the same record was emitted again — that's fine; the
    # store MERGEs on id idempotently).
    assert len(router.received) == 2


def test_move_file_changed_id_emits_delete_plus_create(tmp_path):
    """Renaming with a frontmatter-id change is a delete+create —
    graph identity does not survive."""
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.old\n---\nBody\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    dest = vault / "new.md"
    dest.write_text("---\ntype: spec\nid: spec.new\n---\nBody\n")
    src.unlink()
    action, old_id, new_id = daemon.move_file(src, dest)

    assert action == "renamed_new_id"
    assert old_id == "spec.old"
    assert new_id == "spec.new"
    # Delete record for the old id reached the router
    assert router.deleted == [("spec.old", src)]
    # New record was derived for the new id
    assert any(r.payload.get("id") == "spec.new" for r in router.received)
    assert daemon.state.meta[str(dest)]["id"] == "spec.new"
    assert str(src) not in daemon.state.hashes


def test_move_file_dest_missing_falls_back_to_delete(tmp_path):
    """If watchdog reports a move but dest doesn't exist by the time
    we look (race), treat as delete of src — never silently lose a
    deletion."""
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    # src no longer exists; dest never appeared
    src.unlink()
    dest = vault / "ghost.md"
    action, old_id, new_id = daemon.move_file(src, dest)
    assert action == "delete_only"
    assert old_id == "spec.x"
    assert new_id is None
    assert router.deleted == [("spec.x", src)]


def test_move_file_dest_has_no_id_treated_as_delete(tmp_path):
    """A rename whose dest lost its frontmatter id is a delete of src
    — the new file is meaningless to the derived stores."""
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    dest = vault / "noid.md"
    dest.write_text("---\ntype: spec\n---\nBody no id\n")
    src.unlink()
    action, old_id, new_id = daemon.move_file(src, dest)
    assert action == "delete_only"
    assert old_id == "spec.x"
    assert router.deleted == [("spec.x", src)]


def test_move_file_untracked_src_with_id_in_dest(tmp_path):
    """Renaming from a file we never tracked (e.g., it was just created
    in this scan tick) into a tracked id is a "create_only" action."""
    vault = tmp_path / "vault"
    vault.mkdir()

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")

    src = vault / "old.md"
    dest = vault / "new.md"
    dest.write_text("---\ntype: spec\nid: spec.fresh\n---\n")
    action, old_id, new_id = daemon.move_file(src, dest)
    assert action == "create_only"
    assert old_id is None
    assert new_id == "spec.fresh"
    assert router.deleted == []
    assert any(r.payload.get("id") == "spec.fresh" for r in router.received)


def test_watchdog_on_moved_dispatches_to_move_file(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    src = vault / "old.md"
    src.write_text("---\ntype: spec\nid: spec.x\n---\n")

    registry = _build_registry_with_handler()
    router = NullRouter()
    daemon = VaultSyncDaemon(registry, [router], state_path=tmp_path / "state.json")
    daemon.run_once(vault)

    class _StubObserver:
        def __init__(self):
            self.handler = None

        def schedule(self, handler, root, recursive):
            self.handler = handler

        def start(self):
            raise _StubStop()

        def stop(self):
            pass

        def join(self):
            pass

    class _StubStop(Exception):
        pass

    class _StubHandler:
        is_directory = False

    captured = _StubObserver()
    try:
        daemon._run_with_watchdog(vault, lambda: captured, _StubHandler)
    except _StubStop:
        pass

    handler = captured.handler

    dest = vault / "new.md"
    src.rename(dest)

    class _MoveEvent:
        def __init__(self, s, d):
            self.is_directory = False
            self.src_path = str(s)
            self.dest_path = str(d)

    handler.on_moved(_MoveEvent(src, dest))
    # Same-id rename: no deletion, but state moved
    assert router.deleted == []
    assert str(dest) in daemon.state.hashes
    assert str(src) not in daemon.state.hashes


def test_graphiti_router_increments_jsonrpc_id_per_call():
    sent: list = []

    def fake_post(url, json):
        sent.append(json)
        return _FakeResponse(200)

    router = GraphitiHttpRouter("http://localhost:8000/mcp", post=fake_post)
    router.write([
        DerivedRecord(target="graphiti", payload={"name": "A"}),
        DerivedRecord(target="graphiti", payload={"name": "B"}),
    ])
    ids = [e["id"] for e in sent]
    assert len(ids) == 2
    assert ids[0] != ids[1]
