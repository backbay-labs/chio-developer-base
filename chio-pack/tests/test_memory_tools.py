from __future__ import annotations

from pathlib import Path

from chio_pack.memory import append_memory_entry, query_memory, revoke_memory
from chio_pack.tools import kb_memory_add, kb_memory_query, kb_memory_revoke


def _repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "vault" / "episodes").mkdir(parents=True)
    (repo / "PLAN.md").write_text("plan", encoding="utf-8")
    (repo / "Makefile").write_text("help:\n", encoding="utf-8")
    return repo


def test_append_memory_entry_writes_signed_session_episode(tmp_path):
    repo = _repo(tmp_path)
    write = append_memory_entry(
        repo,
        session_id="abc",
        text="Remember the receipt checkpoint invariant.",
        parent_receipt_hash="parent",
    )
    text = write.path.read_text(encoding="utf-8")
    assert write.path.name == "session-abc.md"
    assert write.memory_id in text
    assert "receipt_hash:" in text
    assert "parent_receipt_hash: parent" in text
    assert '"parent_receipt_hash": "parent"' in text


def test_query_and_revoke_memory_are_append_only(tmp_path):
    repo = _repo(tmp_path)
    write = append_memory_entry(repo, session_id="abc", text="Keep this policy invariant.")
    hits = query_memory(repo, "policy", limit=5)
    assert hits and hits[0]["id"].startswith("memory.abc.")

    revocation = revoke_memory(repo, memory_id=write.memory_id, reason="obsolete", session_id="abc")
    text = revocation.path.read_text(encoding="utf-8")
    assert f"~~{write.memory_id}~~" in text
    assert "Reason: obsolete" in text
    # After revoke, query must not surface the tombstoned memory id.
    assert query_memory(repo, "policy", limit=5) == []
    assert query_memory(repo, write.memory_id, limit=5) == []


def test_memory_tools_use_repo_env(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setenv("CHIO_DEV_REPO", str(repo))

    added = kb_memory_add.call({"text": "Mirror scratchpad delta", "session_id": "session-1"})
    assert added["status"] == "ok"
    episode = repo / "vault" / "episodes" / "session-session-1.md"
    assert episode.exists()
    assert added["memory_id"] in episode.read_text(encoding="utf-8")
    assert added["path"].endswith("session-session-1.md")

    queried = kb_memory_query.call({"query": "scratchpad"})
    assert queried["status"] == "ok"
    assert queried["results"]
    assert any(added["memory_id"] in (hit.get("id") or "") for hit in queried["results"])

    revoked = kb_memory_revoke.call({"memory_id": added["memory_id"], "reason": "test"})
    assert revoked["status"] == "ok"
    revoke_path = Path(revoked["path"])
    assert revoke_path.exists()
    assert f"~~{added['memory_id']}~~" in revoke_path.read_text(encoding="utf-8")


def test_memory_add_query_revoke_end_to_end_behavior(tmp_path, monkeypatch):
    """Binary Wave 6 dogfood: add → file under vault/episodes → query hits → revoke tombs."""
    repo = _repo(tmp_path)
    monkeypatch.setenv("CHIO_DEV_REPO", str(repo))
    marker = "wave6-dogfood-unique-token-7f3a"

    added = kb_memory_add.call({"text": f"Remember {marker}", "session_id": "wave6"})
    assert added["status"] == "ok"
    path = Path(added["path"])
    assert path.is_relative_to(repo / "vault" / "episodes") or str(path).endswith(
        "session-wave6.md"
    )
    assert path.exists()
    assert marker in path.read_text(encoding="utf-8")

    queried = kb_memory_query.call({"query": marker, "limit": 5})
    assert queried["status"] == "ok"
    assert queried["results"], "query must find the just-added memory"
    assert queried["results"][0]["id"] == added["memory_id"]

    revoked = kb_memory_revoke.call(
        {"memory_id": added["memory_id"], "reason": "wave6-e2e", "session_id": "wave6"}
    )
    assert revoked["status"] == "ok"
    tomb = Path(revoked["path"]).read_text(encoding="utf-8")
    assert f"~~{added['memory_id']}~~" in tomb
    assert "wave6-e2e" in tomb
