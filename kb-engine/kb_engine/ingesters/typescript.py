"""Built-in TypeScript / JavaScript source ingester (regex-based, no AST).

Why no TypeScript AST library
-----------------------------

Python's stdlib does not ship a TypeScript parser. The viable AST options
(`tree-sitter-typescript`, calling out to the `typescript` npm package)
either add a native compile dependency or require a Node toolchain at
ingest time. Neither belongs in kb-engine builtins.

A pack that wants real TS symbol resolution writes its own ingester via
the plugin protocol (mirroring the chio-pack Rust tree-sitter ingester
pattern). The same precedence rule applies: pack > builtin.

Chunk strategy
--------------

We split on top-level structural declarations whose keyword starts at
column 0 (or with a leading `export ` / `export default ` / `declare `):

  - `function` (named functions, async or not)
  - `class`
  - `interface`
  - `type` aliases
  - `enum`
  - `const` / `let` / `var` arrow-function bindings
    (`const foo = (...) => ...` or `const foo = async (...) => ...`)

Methods inside classes / fields inside interfaces are NOT split out —
the enclosing declaration is the chunk. Adopters who want method-level
chunks write a pack ingester.

Handles `.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`. The same delimiter
set covers all of them; the language tag is set to "typescript" for
.ts/.tsx/.mts/.cts and "javascript" for .js/.jsx (downstream embedders
sometimes pick a model based on language).

Anything before the first declaration (imports, top-level prologue,
file-level comment) becomes a synthetic `module` chunk. If the file has
zero declarations, the entire file is one `module` chunk. Oversize
chunks fall back to size-based line splits.
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

# Optional `export ` / `export default ` / `declare ` prefix.
_EXPORT_PREFIX = r"(?:export\s+(?:default\s+)?|declare\s+)?"

# Top-level declaration patterns. All anchor at the start of the line —
# we rely on the caller to gate on column-0 status.
_TS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "function",
        re.compile(
            rf"^{_EXPORT_PREFIX}(?:async\s+)?function\*?\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
        ),
    ),
    (
        "class",
        re.compile(rf"^{_EXPORT_PREFIX}(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"),
    ),
    (
        "interface",
        re.compile(rf"^{_EXPORT_PREFIX}interface\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"),
    ),
    (
        "type",
        re.compile(rf"^{_EXPORT_PREFIX}type\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*[=<]"),
    ),
    (
        "enum",
        re.compile(rf"^{_EXPORT_PREFIX}(?:const\s+)?enum\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"),
    ),
    (
        "namespace",
        re.compile(
            rf"^{_EXPORT_PREFIX}(?:namespace|module)\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$.]*)"
        ),
    ),
    (
        # Arrow-function or function-expression bound to a top-level const.
        # Heuristic: looks for `<modifiers> const|let|var <name> = ...`
        # with no further commitment to what's on the right-hand side, so
        # we match both arrow functions and module-scope objects. Module-
        # scope objects assigned via `const` are still useful chunk anchors.
        "binding",
        re.compile(
            rf"^{_EXPORT_PREFIX}(?:const|let|var)\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*[:=]"
        ),
    ),
]


def _find_declaration_starts(lines: list[str]) -> list[tuple[int, str, str]]:
    """Walk a TS/JS file's lines and find top-level declaration starts.

    Returns (1-based line, kind, name). Decorators (`@Component(...)`) on
    classes are absorbed: the recorded line is the decorator's line.
    """
    starts: list[tuple[int, str, str]] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line and not line[0].isspace():
            for kind, pat in _TS_PATTERNS:
                m = pat.match(line)
                if m:
                    name = m.group("name")
                    # Walk back through decorator lines (`@Decorator(...)`).
                    j = i - 1
                    while j >= 0 and lines[j].lstrip().startswith("@"):
                        # Decorators must also be at column 0 to count.
                        if lines[j] and not lines[j][0].isspace():
                            j -= 1
                        else:
                            break
                    starts.append((j + 2, kind, name))
                    break
        i += 1
    return starts


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


def chunk_typescript(
    text: str, *, max_chars: int = DEFAULT_MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Split TS/JS source into structural chunks. Public for direct testing."""
    if not text:
        return []
    lines = text.splitlines()
    total = len(lines)
    starts = _find_declaration_starts(lines)
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
    by_start: dict[int, tuple[str, str]] = {s[0]: (s[1], s[2]) for s in starts}

    chunks: list[Chunk] = []
    for start, end in ranges:
        meta = by_start.get(start)
        if meta is None:
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

    out: list[Chunk] = []
    for c in chunks:
        out.extend(_split_oversize(c, max_chars))
    return out


class TypescriptIngester:
    """`SourceIngester` callable for `.ts`, `.tsx`, `.js`, `.jsx`, `.mts`, `.cts`."""

    EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mts", ".cts")

    def __init__(self, *, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> None:
        self.max_chunk_chars = max_chunk_chars

    def __call__(self, file_path: str) -> ParsedFile | None:
        return self.ingest(file_path)

    def _language_for(self, file_path: str) -> str:
        lower = file_path.lower()
        if lower.endswith(".js") or lower.endswith(".jsx"):
            return "javascript"
        return "typescript"

    def ingest(self, file_path: str) -> ParsedFile | None:
        if not has_extension(file_path, *self.EXTENSIONS):
            return None
        if is_skipped_path(file_path):
            return None
        # Skip declaration files — `.d.ts` is a TypeScript file but it's
        # type-only header content, not source. Pack ingesters that care
        # can register a dedicated handler.
        if file_path.lower().endswith(".d.ts"):
            return None
        text = read_text_safely(file_path)
        if text is None:
            return None
        chunks = chunk_typescript(text, max_chars=self.max_chunk_chars)
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
            language=self._language_for(file_path),
            text=text,
            symbols=symbols,
            properties={
                "chunks": chunk_texts,
                "ingester": "kb_engine.builtin.typescript",
            },
        )


def typescript_source_ingester(file_path: str) -> ParsedFile | None:
    """Stateless wrapper around `TypescriptIngester` for entry-point use."""
    return TypescriptIngester()(file_path)


__all__ = [
    "TypescriptIngester",
    "chunk_typescript",
    "typescript_source_ingester",
]
