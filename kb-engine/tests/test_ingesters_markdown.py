"""Tests for `kb_engine.ingesters.markdown`.

Covers:
  - "Split on every ATX heading" rule (the architectural decision
    documented in `kb_engine.ingesters.markdown`'s module docstring).
  - Heading depth (h1/h2/h3) is preserved as the chunk `kind`.
  - Fence-aware chunking: `#` inside a fenced code block is NOT a
    chunk boundary.
  - Line ranges monotonic, non-overlapping, span 1 .. EOF.
  - Pre-first-heading content becomes a `<preamble>` chunk.
  - `.md` and `.markdown` extensions both work.
  - Files inside vendored / build directories are skipped.
"""
from __future__ import annotations

from pathlib import Path

from kb_engine.ingesters import MarkdownIngester
from kb_engine.ingesters.markdown import chunk_markdown, markdown_source_ingester

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "text-ingest"


def test_markdown_ingester_returns_parsed_file():
    parsed = MarkdownIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    assert parsed.language == "markdown"
    # H1 + H2 + H3 + H2 = 4 symbols (no preamble — H1 is at line 1).
    assert len(parsed.symbols) == 4


def test_markdown_split_on_every_heading_depth():
    """Verifies the architectural decision: H1 + H2 + H3 + H2 → 4 chunks."""
    parsed = MarkdownIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    kinds = [s.kind for s in parsed.symbols]
    names = [s.name for s in parsed.symbols]
    assert kinds == ["h1", "h2", "h3", "h2"]
    assert names == [
        "Top-level title",
        "First section",
        "Subsection",
        "Second section",
    ]


def test_markdown_line_ranges_monotonic_and_non_overlapping():
    parsed = MarkdownIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    syms = parsed.symbols
    for a, b in zip(syms, syms[1:]):
        assert a.line_start < b.line_start
        assert a.line_end < b.line_start
    assert syms[0].line_start == 1
    file_lines = (FIXTURE_DIR / "sample.md").read_text().splitlines()
    assert syms[-1].line_end == len(file_lines)


def test_markdown_chunks_are_whole_line():
    parsed = MarkdownIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    file_lines = (FIXTURE_DIR / "sample.md").read_text().splitlines()
    for sym, chunk_text in zip(parsed.symbols, parsed.properties["chunks"]):
        expected = "\n".join(file_lines[sym.line_start - 1:sym.line_end])
        assert chunk_text == expected


def test_markdown_fenced_block_hash_is_not_a_heading():
    """Inside a fenced code block, `# something` must not split a chunk."""
    parsed = MarkdownIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    # The "Second section" chunk contains the fenced block with a
    # `# This hash is INSIDE a fence` comment line. That must NOT
    # produce its own heading chunk.
    second_idx = next(
        i for i, s in enumerate(parsed.symbols)
        if s.name == "Second section"
    )
    second_text = parsed.properties["chunks"][second_idx]
    assert "INSIDE a fence" in second_text
    assert "looks_like_heading" in second_text


def test_markdown_preamble_for_files_with_prologue(tmp_path: Path):
    src = (
        "Some intro paragraph.\n"
        "More intro lines.\n"
        "\n"
        "## A heading\n"
        "Body.\n"
    )
    f = tmp_path / "p.md"
    f.write_text(src)
    parsed = MarkdownIngester().ingest(str(f))
    assert parsed is not None
    assert parsed.symbols[0].kind == "preamble"
    assert parsed.symbols[0].name == "<preamble>"
    assert parsed.symbols[0].line_start == 1
    assert parsed.symbols[1].kind == "h2"


def test_markdown_no_headings_yields_one_document_chunk(tmp_path: Path):
    src = "Just prose.\nNo headings here.\n"
    f = tmp_path / "flat.md"
    f.write_text(src)
    parsed = MarkdownIngester().ingest(str(f))
    assert parsed is not None
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].kind == "document"


def test_markdown_handles_markdown_extension(tmp_path: Path):
    f = tmp_path / "readme.markdown"
    f.write_text("# Title\nBody.\n")
    parsed = MarkdownIngester().ingest(str(f))
    assert parsed is not None
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].kind == "h1"


def test_markdown_skips_vendor_dir(tmp_path: Path):
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    f = nm / "README.md"
    f.write_text("# x\n")
    assert MarkdownIngester().ingest(str(f)) is None


def test_markdown_function_alias_works():
    parsed = markdown_source_ingester(str(FIXTURE_DIR / "sample.md"))
    assert parsed is not None
    assert len(parsed.symbols) == 4


def test_markdown_oversize_chunk_falls_back_to_size_split():
    body_lines = "\n".join(f"line-{i}" for i in range(2000))
    src = f"# big heading\n{body_lines}\n"
    chunks = chunk_markdown(src, max_chars=500)
    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:]):
        assert a.line_end < b.line_start


def test_markdown_indented_hash_is_not_a_heading(tmp_path: Path):
    """CommonMark: `    # foo` is a code block, not a heading."""
    src = (
        "# Real heading\n"
        "Content.\n"
        "\n"
        "    # this is a code block, not a heading\n"
        "More content.\n"
    )
    f = tmp_path / "x.md"
    f.write_text(src)
    parsed = MarkdownIngester().ingest(str(f))
    assert parsed is not None
    assert len(parsed.symbols) == 1  # Only the real H1
    assert parsed.symbols[0].kind == "h1"
