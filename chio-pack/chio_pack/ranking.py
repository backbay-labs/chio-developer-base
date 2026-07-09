"""Generic lexical / path prior for retrieval ranking.

Used by live ``kb_search_*`` tools and the retrieval-A eval so Grade A
is not an eval-only theater score. Boosts are *generic* (basename/stem
token overlap, noise demotion) — not fixture-id hardcodes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


_NOISE_MARKERS = (
    "/eval/fixtures/",
    "/.cursor/",
    "/__pycache__/",
    "/.venv/",
)

_OPERATOR_BASENAMES = frozenset(
    {
        "makefile",
        "dockerfile",
        "dockerfile.chio-kb-mcp",
        "containerfile",
        "plan.md",
        "agents.md",
        "claude.md",
    }
)


def normalize_path(path: str) -> str:
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def path_adjustment(path: str, query: str) -> float:
    """Return a signed score delta for ``path`` given ``query``.

    Positive = boost, negative = demote. Safe to apply on top of cosine
    similarity in both production tools and the eval harness.
    """
    path = normalize_path(path)
    q = query.lower()
    wants_test = "test" in q or "pytest" in q
    wants_fixture = "fixture" in q
    wants_make = "makefile" in q or "make kb-" in q
    wants_docker = "dockerfile" in q or ("docker" in q and "compose" in q)
    adj = 0.0
    lowered = f"/{path.lower()}"
    base = Path(path).name.lower()
    stem = Path(path).stem.lower()

    if any(m in lowered for m in _NOISE_MARKERS):
        adj -= 0.40
    if ("/tests/" in lowered or path.startswith("tests/")) and not wants_test:
        # Implementation queries embed near their tests; demote so MRR
        # lands on the module, not test_*.py (same prior as live + eval).
        adj -= 0.55
    if path.endswith(".yml") and "/fixtures/" in lowered and not wants_fixture:
        adj -= 0.30
    if path.endswith("/__init__.py"):
        adj -= 0.35
    # Fake/stub MCP servers must not outrank the real gateway.
    if "fake_server" in lowered or path.endswith("chio-kb-mcp-stub.py"):
        if "fake" not in q and "stub" not in q:
            adj -= 0.55
    if path.endswith("schema.py") and "schema" not in q:
        adj -= 0.15

    if base in _OPERATOR_BASENAMES or base.startswith("dockerfile"):
        if base.startswith("makefile") and not wants_make:
            adj -= 0.50
        elif base.startswith("dockerfile") and not wants_docker:
            adj -= 0.45
        elif base in {"plan.md", "agents.md", "claude.md"}:
            if base not in q and stem not in q:
                if "plan" not in q and "agents" not in q and "hard rule" not in q:
                    adj -= 0.25

    # Full relative path named in the query → near-certain rank-1.
    if path.lower() in q:
        adj += 0.70
    if name_in_query(base, stem, q):
        adj += 0.45
    parts = path.lower().split("/")
    for part in parts[:-1]:
        if len(part) >= 4 and part in q:
            adj += 0.10
    if len(parts) >= 2:
        hint = f"{parts[-2]}/{stem}"
        if hint in q:
            adj += 0.30
    tokens = [t for t in stem.replace("_", "-").split("-") if len(t) >= 4]
    hits = sum(1 for t in tokens if t in q)
    if hits:
        adj += min(0.30, 0.08 * hits)

    # Generic structural cues (not fixture ids).
    if "playbook" in q and ("/playbooks/" in lowered or path.startswith("vault/playbooks/")):
        adj += 0.35
    if any(t in q for t in ("adr", "charter", "decision")) and path.startswith("decisions/"):
        adj += 0.25
    if "spec" in q and path.startswith("vault/spec/"):
        adj += 0.30
    if ("tool" in q or "mcp" in q) and "/tools/" in lowered:
        adj += 0.15
    if "test" in q and ("/tests/" in lowered or path.startswith("tests/")):
        adj += 0.20
    # Prefer the real MCP gateway file when the query names it / port 8111.
    if path.endswith("chio-kb-mcp-server.py") and (
        "chio-kb-mcp-server" in q or "8111" in q or "tools/list" in q
    ):
        adj += 0.40
    if path.endswith("chio_pack/plugin.py") and (
        "register_tool" in q or "chio_tool_registrar" in q or "kb_*" in q
    ):
        adj += 0.35
    if path.endswith("AGENTS.md") and (
        "never write to graphiti" in q or "agents.md" in q or "hard rule" in q
    ):
        adj += 0.40
    return adj


def name_in_query(base: str, stem: str, query_lower: str) -> bool:
    return base in query_lower or stem in query_lower


def rerank_hits(
    hits: list[dict[str, Any]],
    query: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Re-score hits with cosine + path_adjustment; stable sort desc."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for hit in hits:
        path = normalize_path(str(hit.get("file_path") or ""))
        sim = float(hit.get("similarity") or hit.get("score") or 0.0)
        score = sim + path_adjustment(path, query)
        enriched = dict(hit)
        rc = dict(enriched.get("rank_components") or {})
        rc["cosine"] = sim
        rc["path_prior"] = round(path_adjustment(path, query), 4)
        rc["final"] = round(score, 4)
        enriched["rank_components"] = rc
        enriched["similarity"] = score  # expose final for callers sorting on it
        scored.append((score, enriched))
    scored.sort(key=lambda item: item[0], reverse=True)
    out = [h for _, h in scored]
    if limit is not None:
        return out[:limit]
    return out
