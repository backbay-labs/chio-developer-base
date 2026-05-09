"""Tests for the kb-engine retrieval-eval fixture template.

The template lives at `kb-engine/eval/template/` and is the canonical
schema chio-pack and adopter packs copy when bootstrapping a new
retrieval-eval fixture set. These tests pin the template's shape so
drift is visible at PR time.

Constraints (from M1 handoff):
  - README.md is <= 20 lines (an unfamiliar reader can fill in
    example.yml fields without reading chio-pack source).
  - The README documents p_at_k, mrr, and the 9 PR-#599 categories.
  - example.yml carries `_example: true` so the runner skips it.
  - example.yml has the six fields the README promises.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent / "eval" / "template"
)


def test_template_directory_exists():
    assert TEMPLATE_DIR.is_dir()


def test_readme_is_at_most_20_lines():
    """Adopter checklist mandate — keep the README brief."""
    readme = TEMPLATE_DIR / "README.md"
    assert readme.is_file()
    n_lines = len(readme.read_text(encoding="utf-8").splitlines())
    assert n_lines <= 20, f"README.md has {n_lines} lines; cap is 20"


def test_readme_documents_metrics_and_categories():
    """README must name p_at_k, mrr, and all 9 PR-#599 categories."""
    text = (TEMPLATE_DIR / "README.md").read_text(encoding="utf-8")
    assert "p_at_k" in text
    assert "mrr" in text.lower() or "MRR" in text
    expected_categories = [
        "code-retrieval",
        "docs-retrieval",
        "docs-spec-retrieval",
        "feature-brief",
        "graph-and-bridge",
        "graph-navigation-impact",
        "graphiti-memory",
        "operations",
        "test-discovery",
    ]
    for cat in expected_categories:
        assert cat in text, f"README missing category: {cat}"


def test_example_yml_has_six_documented_fields():
    """example.yml has the 6 fields the README's checklist names."""
    text = (TEMPLATE_DIR / "example.yml").read_text(encoding="utf-8")
    for field in ("id:", "category:", "query:", "expected:", "metrics:", "notes:"):
        assert field in text, f"example.yml missing field marker: {field}"


def test_example_yml_marked_as_example():
    """`_example: true` gate — the runner must skip this file."""
    text = (TEMPLATE_DIR / "example.yml").read_text(encoding="utf-8")
    assert "_example: true" in text


def test_example_yml_uses_one_of_the_nine_categories():
    """The example uses a real category so adopters see a valid value."""
    text = (TEMPLATE_DIR / "example.yml").read_text(encoding="utf-8")
    expected_categories = [
        "code-retrieval",
        "docs-retrieval",
        "docs-spec-retrieval",
        "feature-brief",
        "graph-and-bridge",
        "graph-navigation-impact",
        "graphiti-memory",
        "operations",
        "test-discovery",
    ]
    found = [c for c in expected_categories if f"category: {c}" in text]
    assert len(found) == 1, f"expected exactly one category line, got {found}"


def test_example_yml_lists_both_metrics():
    """The example lists both p_at_k and mrr so adopters see the shape."""
    text = (TEMPLATE_DIR / "example.yml").read_text(encoding="utf-8")
    assert "p_at_k" in text
    assert "mrr" in text
