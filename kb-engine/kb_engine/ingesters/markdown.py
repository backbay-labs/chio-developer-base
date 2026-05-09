"""Built-in Markdown source ingester (heading-delimited chunks).

Chunk strategy — split on every ATX heading
-------------------------------------------

ARCHITECTURAL DECISION (chunk granularity for `.md`):

We split on **every** ATX heading (`^#{1,6} `) — H1 through H6. Not just
H2, not just "the deepest heading level we see". One heading = one chunk.

Rationale:

  - Markdown depth is author-driven, not semantic. One author writes a
    flat file with 12 H1s; another writes one H1 followed by 12 H2s
    under it. Splitting only on H2 would chunk the first file as one
    blob and the second as 12 chunks, despite the underlying content
    structure being equivalent. Splitting on every heading makes chunk
    granularity track the author's actual structural intent regardless
    of which heading levels they reach for.

  - Citations land on the heading nearest the matched text. With a
    "split on every heading" rule, retrieval can quote `## Caching` as
    the cite anchor instead of "the H1 above which contains 200 lines".

  - It composes with the size fallback. A heading with a long body just
    splits into multiple sub-chunks via the size fallback; a heading
    with one line stays small. No magic threshold tuning required.

  - Adopters whose docs use a different convention (e.g. "every doc has
    one H1 and we want chunks at H2 level") can register a pack
    ingester for `.md` that overrides this default. Pack > builtin.

The alternative — split-on-H2-only — was rejected because it forces an
opinion on heading depth that authors of the consumed corpus did not
sign up for. Splitting on every heading is structurally faithful and
hands the cite-anchor problem its best possible answer.

Other rules
-----------

  - Front matter blocks (`---\\n...\\n---` at the top of the file) are
    treated as opaque preamble; they belong to the implicit `<frontmatter>`
    chunk that covers everything before the first heading. Vault
    front-matter is interpreted by `FrontmatterHandler` plugins, not
    here — this ingester is text-extraction only.

  - Fenced code blocks (triple-backtick or triple-tilde) are NOT split,
    even if they contain `#` characters that would otherwise look like
    headings. `#` inside a fenced block is treated as content.

  - Indented headings (`    # foo`) are not headings under CommonMark
    (they're code blocks), and we don't treat them as chunk boundaries.

  - The implicit pre-first-heading region becomes a `<preamble>` chunk
    if non-empty (covers H1-less files and front-matter prologues).

  - If a chunk exceeds the size cap (default 8 KiB), we line-split it
    via `_common.fallback_size_chunks`. The first sub-chunk keeps the
    heading; subsequent sub-chunks get a `#N` suffix on the heading
    name so chunk identity is stable.
"""
from __future__ import annotations

import re

from ..types import ParsedFile, Symbol
from ._common import (
    DEFAULT_MAX_CHUNK_CHARS,
    Chunk,
    boundaries_to_ranges,
    fallback_size_chunks,
    has_extension,
    is_skipped_path,
    read_text_safely,
    slice_lines,
)

# ATX heading: 1-6 hashes followed by at least one space, then content.
# We don't trim trailing `###` closers; chunk name is just the visible heading text.
_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")

# Fenced code-block opener / closer. Both ``` and ~~~ are CommonMark
# fences; we honour both.
_FENCE = re.compile(r"^(?P<fence>`{3,}|~{3,})")


def _build_fence_mask(lines: list[str]) -> list[bool]:
    """Return a per-line boolean: True if that line is INSIDE a fenced block.

    A line that opens a fence is itself "inside" — we do not want a
    heading on the fence line either way (degenerate). The fence-closer
    line is also treated as inside.
    """
    mask = [False] * len(lines)
    in_fence = False
    fence_marker: str | None = None
    for i, line in enumerate(lines):
        m = _FENCE.match(line)
        if m:
            f = m.group("fence")
            if not in_fence:
                in_fence = True
                fence_marker = f[0]  # ` or ~
            elif f[0] == fence_marker:
                in_fence = False
                fence_marker = None
            mask[i] = True
            continue
        mask[i] = in_fence
    return mask


def _find_heading_starts(lines: list[str]) -> list[tuple[int, int, str]]:
    """Locate ATX heading lines outside fenced code blocks.

    Returns (1-based line, depth, title). Indented `#` lines are ignored
    (they're code blocks under CommonMark).
    """
    fence_mask = _build_fence_mask(lines)
    out: list[tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        if fence_mask[i]:
            continue
        if not line or line[0].isspace():
            continue
        m = _HEADING.match(line)
        if not m:
            continue
        depth = len(m.group("hashes"))
        title = m.group("title").strip()
        out.append((i + 1, depth, title))
    return out


def _split_oversize(c: Chunk, max_chars: int) -> list[Chunk]:
    if len(c.text) <= max_chars:
        return [c]
    sub = fallback_size_chunks(
        c.text,
        name_prefix=c.name,
        kind=c.kind,
        max_chars=max_chars,
    )
    out: list[Chunk] = []
    for s in sub:
        out.append(Chunk(
            name=s.name,
            kind=s.kind,
            line_start=c.line_start + (s.line_start - 1),
            line_end=c.line_start + (s.line_end - 1),
            text=s.text,
        ))
    return out


def chunk_markdown(text: str, *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[Chunk]:
    """Split markdown source into one chunk per ATX heading.

    Pre-heading content becomes a `<preamble>` chunk. Public for direct
    testing; the ingester wraps this.
    """
    if not text:
        return []
    lines = text.splitlines()
    total = len(lines)
    headings = _find_heading_starts(lines)

    if not headings:
        single = Chunk(
            name="<preamble>",
            kind="document",
            line_start=1,
            line_end=total,
            text=text.rstrip("\n"),
        )
        return _split_oversize(single, max_chars)

    boundary_lines = [h[0] for h in headings]
    ranges = boundaries_to_ranges(boundary_lines, total)
    by_start: dict[int, tuple[int, str]] = {h[0]: (h[1], h[2]) for h in headings}

    chunks: list[Chunk] = []
    for start, end in ranges:
        meta = by_start.get(start)
        if meta is None:
            kind, name = "preamble", "<preamble>"
        else:
            depth, title = meta
            kind = f"h{depth}"
            name = title
        chunk_text = slice_lines(text, start, end)
        chunks.append(Chunk(
            name=name,
            kind=kind,
            line_start=start,
            line_end=end,
            text=chunk_text,
        ))

    out: list[Chunk] = []
    for c in chunks:
        out.extend(_split_oversize(c, max_chars))
    return out


class MarkdownIngester:
    """`SourceIngester` callable for `.md` and `.markdown` files."""

    EXTENSIONS = (".md", ".markdown", ".mdx")
    LANGUAGE = "markdown"

    def __init__(self, *, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> None:
        self.max_chunk_chars = max_chunk_chars

    def __call__(self, file_path: str) -> ParsedFile | None:
        return self.ingest(file_path)

    def ingest(self, file_path: str) -> ParsedFile | None:
        if not has_extension(file_path, *self.EXTENSIONS):
            return None
        if is_skipped_path(file_path):
            return None
        text = read_text_safely(file_path)
        if text is None:
            return None
        chunks = chunk_markdown(text, max_chars=self.max_chunk_chars)
        symbols: list[Symbol] = []
        chunk_texts: list[str] = []
        for c in chunks:
            symbols.append(Symbol(
                name=c.name,
                kind=c.kind,
                line_start=c.line_start,
                line_end=c.line_end,
            ))
            chunk_texts.append(c.text)
        return ParsedFile(
            path=file_path,
            language=self.LANGUAGE,
            text=text,
            symbols=symbols,
            properties={"chunks": chunk_texts, "ingester": "kb_engine.builtin.markdown"},
        )


def markdown_source_ingester(file_path: str) -> ParsedFile | None:
    """Stateless wrapper around `MarkdownIngester` for entry-point use."""
    return MarkdownIngester()(file_path)


__all__ = ["MarkdownIngester", "chunk_markdown", "markdown_source_ingester"]
