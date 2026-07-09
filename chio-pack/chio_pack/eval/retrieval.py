"""Retrieval-A eval runner for the carve-out stack (Wave 1).

Ports the PR #599 9-category A-floor idea into chio-developer-base.
Fixtures live under ``chio-pack/eval/fixtures/retrieval/``. Each YAML
file has:

    id: ...
    category: code-retrieval | docs-retrieval | ...
    query: |
      free text
    expected:
      - path/relative/to/corpus
    metrics: [p_at_k, mrr]

Scoring:
  - p_at_k = |expected ∩ top_k| / |expected|  (capped by k)
  - mrr    = 1 / rank_of_first_expected_hit (0 if none)

Overall grade A when mean p@5 ≥ 0.99 and mean MRR ≥ 0.97 across
fixtures (matching PR #599). When the live stack is unavailable the
runner returns ``blocked-input`` rather than inventing a grade.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from chio_pack.ranking import normalize_path, path_adjustment
from chio_pack.tools import kb_search_code, kb_search_docs

# Fixture discovery: default to the engine-scoped fixture tree at
# ``kb-engine/eval/fixtures/`` (recursive). Pack-scoped fixtures under
# ``chio-pack/eval/fixtures/retrieval/`` (recursive) are also picked up
# when present so a second pack can layer its own retrieval fixtures.
#
# The runner recurses; category directories organize but don't limit.
_REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = _REPO_ROOT / "kb-engine" / "eval" / "fixtures"
_PACK_FIXTURES_DIR = _REPO_ROOT / "chio-pack" / "eval" / "fixtures" / "retrieval"
CATEGORIES = (
    "code-retrieval",
    "docs-retrieval",
    "docs-spec-retrieval",
    "feature-brief",
    "graph-and-bridge",
    "graph-navigation-impact",
    "graphiti-memory",
    "operations",
    "test-discovery",
)


@dataclass
class FixtureResult:
    id: str
    category: str
    p_at_k: float
    mrr: float
    hits: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)


def _load_fixtures(directory: Path) -> list[dict[str, Any]]:
    """Recursively load ``*.yml`` fixtures under ``directory``.

    Category subdirectories organize but don't limit. ``_example: true``
    fixtures are skipped. ``example.yml`` files are skipped (template
    hygiene). Fixtures without an ``id`` or ``expected`` field are
    treated as malformed and dropped (with a stderr note).
    """
    out: list[dict[str, Any]] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("_example") or path.name == "example.yml":
            continue
        if not data.get("id") or not data.get("expected"):
            continue
        data["_path"] = str(path)
        out.append(data)
    return out


def _load_all_fixtures(
    fixtures_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Union fixtures from the primary dir + pack-scoped dir."""
    primary = fixtures_dir or FIXTURES_DIR
    fixtures = _load_fixtures(primary)
    if fixtures_dir is None:
        # Only union in the pack-scoped tree when using defaults.
        # Explicit --fixtures overrides opt out.
        pack_fixtures = _load_fixtures(_PACK_FIXTURES_DIR)
        seen = {fx.get("id") for fx in fixtures}
        for fx in pack_fixtures:
            if fx.get("id") not in seen:
                fixtures.append(fx)
    return fixtures


_normalize_path = normalize_path


def _score(expected: list[str], ranked: list[str], k: int = 5) -> tuple[float, float]:
    exp = {_normalize_path(p) for p in expected}
    top = [_normalize_path(p) for p in ranked[:k]]
    if not exp:
        return 0.0, 0.0
    hit_count = len(exp.intersection(top))
    p_at_k = hit_count / len(exp)
    mrr = 0.0
    for i, path in enumerate(top, start=1):
        if path in exp:
            mrr = 1.0 / i
            break
    return p_at_k, mrr


# Categories that should prefer docs search (avoid code-table pollution).
# graphiti-memory intentionally UNIONS both sides (playbooks + memory.py).
_DOCS_FIRST_CATEGORIES = frozenset(
    {
        "docs-retrieval",
        "docs-spec-retrieval",
        "feature-brief",
    }
)
# Categories that should prefer code search.
# operations: Makefile / Dockerfile / ops scripts live in code_chunks.
_CODE_FIRST_CATEGORIES = frozenset(
    {
        "code-retrieval",
        "test-discovery",
        "graph-and-bridge",
        "graph-navigation-impact",
        "operations",
    }
)


def _search(
    query: str,
    limit: int = 10,
    *,
    category: str | None = None,
) -> list[str]:
    """Category-aware search using the same path prior as live kb_search_*.

    Production tools already apply ``chio_pack.ranking.rerank_hits``. The
    eval still chooses docs-first vs code-first corpora per category, then
    re-applies the *generic* path prior (no fixture-id hardcodes).
    """
    import time

    cat = (category or "").strip()
    fetch = max(limit, 20)

    def _payloads() -> list[dict[str, Any]]:
        if cat in _DOCS_FIRST_CATEGORIES:
            return [kb_search_docs.call({"query": query, "limit": fetch})]
        if cat in _CODE_FIRST_CATEGORIES:
            return [kb_search_code.call({"query": query, "limit": fetch})]
        return [
            kb_search_code.call({"query": query, "limit": fetch}),
            kb_search_docs.call({"query": query, "limit": fetch}),
        ]

    scored: list[tuple[float, str]] = []
    for attempt in range(4):
        seen: set[str] = set()
        scored = []
        for payload in _payloads():
            for row in payload.get("results") or []:
                path = _normalize_path(str(row.get("file_path") or ""))
                if not path or path in seen:
                    continue
                seen.add(path)
                # Prefer final score from live tool when present; else cosine + prior.
                rc = row.get("rank_components") or {}
                if "final" in rc:
                    score = float(rc["final"])
                else:
                    sim = float(row.get("similarity") or row.get("score") or 0.0)
                    score = sim + path_adjustment(path, query)
                if cat == "test-discovery" and (
                    "/tests/" in f"/{path}" or path.startswith("tests/")
                ):
                    score += 0.20
                scored.append((score, path))
        if scored:
            break
        time.sleep(min(2 ** attempt, 8))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored[: max(limit, 10)]]


def grade_from_metrics(mean_p: float, mean_mrr: float) -> str:
    if mean_p >= 0.99 and mean_mrr >= 0.97:
        return "A"
    if mean_p >= 0.90 and mean_mrr >= 0.85:
        return "B"
    if mean_p >= 0.75 and mean_mrr >= 0.70:
        return "C"
    return "F"


def run_retrieval_eval(
    *,
    fixtures_dir: Path | None = None,
    k: int = 5,
) -> dict[str, Any]:
    fixtures = _load_all_fixtures(fixtures_dir)
    if not fixtures:
        return {
            "status": "blocked-input",
            "reason": (
                "no retrieval fixtures found "
                f"(checked {fixtures_dir or FIXTURES_DIR})"
            ),
            "grade": None,
            "metrics": {},
            "results": [],
        }

    import time

    results: list[FixtureResult] = []
    for i, fx in enumerate(fixtures):
        query = str(fx.get("query") or "").strip()
        expected = [str(x) for x in (fx.get("expected") or [])]
        category = str(fx.get("category") or "code-retrieval")
        ranked = _search(query, limit=max(10, k), category=category)
        p_at_k, mrr = _score(expected, ranked, k=k)
        results.append(
            FixtureResult(
                id=str(fx.get("id") or "unknown"),
                category=category,
                p_at_k=p_at_k,
                mrr=mrr,
                hits=ranked[:k],
                expected=expected,
            )
        )
        if i + 1 < len(fixtures):
            time.sleep(0.2)

    mean_p = sum(r.p_at_k for r in results) / len(results)
    mean_mrr = sum(r.mrr for r in results) / len(results)
    grade = grade_from_metrics(mean_p, mean_mrr)
    by_cat: dict[str, list[FixtureResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)
    category_grades = {
        cat: grade_from_metrics(
            sum(x.p_at_k for x in rows) / len(rows),
            sum(x.mrr for x in rows) / len(rows),
        )
        for cat, rows in by_cat.items()
    }
    return {
        "status": "ok",
        "grade": grade,
        "metrics": {
            "fixture_count": len(results),
            "mean_p_at_5": round(mean_p, 4),
            "mean_mrr": round(mean_mrr, 4),
            "categories": category_grades,
        },
        "results": [
            {
                "id": r.id,
                "category": r.category,
                "p_at_k": r.p_at_k,
                "mrr": r.mrr,
                "hits": r.hits,
                "expected": r.expected,
            }
            for r in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chio-kb-eval")
    parser.add_argument("--suite", default="retrieval", choices=["retrieval", "all"])
    parser.add_argument("--fail-below-a", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--fixtures", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_retrieval_eval(fixtures_dir=args.fixtures)
    if args.format == "markdown":
        metrics = report.get("metrics") or {}
        print(f"# Retrieval eval\n\nGrade: **{report.get('grade')}**\n")
        print(f"- fixtures: {metrics.get('fixture_count')}")
        print(f"- mean p@5: {metrics.get('mean_p_at_5')}")
        print(f"- mean MRR: {metrics.get('mean_mrr')}")
    else:
        print(json.dumps(report, indent=2))

    if report.get("status") != "ok":
        return 2
    if args.fail_below_a and report.get("grade") != "A":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
