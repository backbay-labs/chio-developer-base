"""Built-in Python source ingester (regex-based, no AST).

Why no `ast` module
-------------------

Even though Python ships an AST parser in the stdlib, this ingester is a
deliberate regex chunker. Reasons:

  - Adopters who want real symbol resolution write a pack ingester.
    Mixing baselines (regex chunker for builtin, AST chunker for opt-in
    pack) means the pack contract is *additive*, not *replacement-only*.
  - Regex survives syntactically invalid mid-edit files. AST does not —
    a single broken `def` would refuse to ingest the whole file. The
    base ingester must work on every file the IDE just saved, even mid-
    refactor.
  - The output contract (`ParsedFile.symbols` with line ranges) does not
    need full Python semantics. A def/class boundary regex is enough to
    cite spans accurately for retrieval.
  - Keeps `kb_engine` install-time cheap: zero new dependencies.

Chunk strategy
--------------

We split on top-level (column-0) `def`, `async def`, and `class`
statements. Decorators above a definition are absorbed into the chunk
that begins at the decorator's line — citation should point at the
decorator, not at the line below it.

Methods inside classes are NOT split out separately. The class is the
chunk; the class body (methods + nested defs) stays with it. This is the
*pragmatic* trade. A pack ingester that wants per-method chunks can
override the `.py` extension.

Anything before the first definition (module docstring, imports, top-level
constants) becomes a synthetic `module` chunk. If the file has zero
definitions, the entire file is one `module` chunk.

Each chunk that is too large (default 8 KiB) is recursively split by
line on the size fallback (`_common.fallback_size_chunks`).

The ingester returns:

  - language="python"
  - symbols=[Symbol(name=..., kind="module"|"class"|"function", ...)]
  - properties={"chunks": [<chunk text per symbol, by index>]}

Chunk text is stored on `properties["chunks"]` because the public
`Symbol` dataclass deliberately doesn't carry text — that's the
embedder's input, not symbol metadata. Indexed by symbol position so
`parsed.symbols[i]` and `parsed.properties["chunks"][i]` line up.
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

# Top-level def / async def / class. Column-0 only — methods are absorbed
# into the enclosing class chunk by design.
_TOP_LEVEL_DEF = re.compile(
    r"^(?P<keyword>async\s+def|def|class)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
)

# A decorator at column 0. We walk decorators backwards to attach them to
# the def/class they apply to so citations include `@cached`, `@staticmethod`
# etc.
_DECORATOR = re.compile(r"^@[A-Za-z_]")


def _find_definition_starts(lines: list[str]) -> list[tuple[int, str, str]]:
    """Walk a Python file's lines and locate top-level definition starts.

    Returns a list of (1-based line, kind, name). `kind` is one of
    "function" or "class". Decorators above a definition shift the
    reported line number up to the topmost decorator.
    """
    starts: list[tuple[int, str, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # Only column-0 matters; skip indented lines fast.
        if line and not line[0].isspace() and not line.startswith("#"):
            m = _TOP_LEVEL_DEF.match(line)
            if m:
                kind = "class" if m.group("keyword") == "class" else "function"
                name = m.group("name")
                # Walk back through any contiguous decorator lines.
                j = i - 1
                while j >= 0 and _DECORATOR.match(lines[j]):
                    j -= 1
                starts.append((j + 2, kind, name))  # +2: 1-based, line after last non-decorator
        i += 1
    return starts


def _split_oversize(c: Chunk, max_chars: int) -> list[Chunk]:
    """Apply size fallback to a single chunk if it's too long.

    A single function/class that exceeds `max_chars` is line-split with
    a stable name suffix so chunk identity remains stable across runs.
    """
    if len(c.text) <= max_chars:
        return [c]
    sub = fallback_size_chunks(
        c.text,
        name_prefix=c.name,
        kind=c.kind,
        max_chars=max_chars,
    )
    # Re-anchor the sub-chunk line numbers into the parent's line space.
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


def chunk_python(text: str, *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> list[Chunk]:
    """Split a Python source string into structural chunks.

    Public for direct testing; the ingester wraps this. Chunks always
    cover the whole file with no gaps and no overlaps.
    """
    if not text:
        return []
    lines = text.splitlines()
    total = len(lines)
    starts = _find_definition_starts(lines)

    if not starts:
        single = Chunk(
            name="<module>",
            kind="module",
            line_start=1,
            line_end=total,
            text=text.rstrip("\n"),
        )
        return _split_oversize(single, max_chars)

    boundary_lines = [s[0] for s in starts]
    ranges = boundaries_to_ranges(boundary_lines, total)

    # Build a quick lookup: starting line -> (kind, name)
    by_start: dict[int, tuple[str, str]] = {s[0]: (s[1], s[2]) for s in starts}

    chunks: list[Chunk] = []
    for start, end in ranges:
        meta = by_start.get(start)
        if meta is None:
            # Pre-first-definition region (imports, module docstring).
            kind, name = "module", "<module>"
        else:
            kind, name = meta
        chunk_text = slice_lines(text, start, end)
        chunks.append(Chunk(
            name=name,
            kind=kind,
            line_start=start,
            line_end=end,
            text=chunk_text,
        ))

    # Apply size fallback to any oversize chunk.
    out: list[Chunk] = []
    for c in chunks:
        out.extend(_split_oversize(c, max_chars))
    return out


class PythonIngester:
    """`SourceIngester` callable for `.py` files.

    Returns a `ParsedFile` with one `Symbol` per chunk. Skips files in
    vendor directories (`__pycache__/`, `.venv/`, ...) and binary content.
    """

    EXTENSIONS = (".py",)
    LANGUAGE = "python"

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
        chunks = chunk_python(text, max_chars=self.max_chunk_chars)
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
            properties={"chunks": chunk_texts, "ingester": "kb_engine.builtin.python"},
        )


# Function-style alias matches the chio-pack `rust_source_ingester` style
# so the registry can register either form.
def python_source_ingester(file_path: str) -> ParsedFile | None:
    """Stateless wrapper around `PythonIngester` for entry-point use."""
    return PythonIngester()(file_path)


__all__ = ["PythonIngester", "chunk_python", "python_source_ingester"]
