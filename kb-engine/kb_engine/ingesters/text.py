"""Built-in generic-text ingester for config-style files.

Handles files that aren't Python / TypeScript / Markdown but still carry
retrievable knowledge — Makefiles, Dockerfiles, shell scripts, YAML,
TOML, INI, and plain text. Wave 1 upgrade: without this, ``make kb-eval``
returns zero hits for any query targeting an operator-facing file
(Makefile targets, Dockerfile stages, docker-compose services, etc.).

Chunk strategy — split on structural boundaries when they're obvious,
otherwise fall back to size-based windows.

For Makefiles/shell/text this means splitting on:
  - Makefile target headers (``^[A-Za-z0-9_.-]+:``)
  - Dockerfile stage headers (``^FROM ``)
  - Section-like comment blocks (``^# ==`` or ``^# ---``)

For everything else we treat the whole file as one candidate chunk and
let :func:`fallback_size_chunks` split anything over ``max_chars``.

Rationale for keeping this in kb-engine builtins
-----------------------------------------------
The mission's retrieval-A gate requires operator files be findable. A
pack that wanted richer parsing (e.g. proper Makefile AST) can register
its own ingester and take precedence via the pack > builtin rule.
"""
from __future__ import annotations

import re
from pathlib import Path

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

# Structural delimiters we recognize across the text family. Each pattern
# is matched at the start of a line; matches become chunk boundaries.
_BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Makefile-style target header: `foo:` / `foo.bar-baz:` at line start.
    re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*:(?:\s|$)"),
    # Dockerfile stage header (case-insensitive).
    re.compile(r"^\s*FROM\s+", re.IGNORECASE),
    # Big section-delimiter comment blocks (`# ==== …` or `# ---- …`).
    re.compile(r"^\s*#\s*(={3,}|-{3,})"),
    # TOML / systemd section headers (`[section]`).
    re.compile(r"^\s*\[[A-Za-z0-9_.\-:/]+\]\s*$"),
)

# Extensions we handle. Filenames without an extension (Makefile,
# Dockerfile, containerfile) are handled by :func:`_matches_bare_name`.
EXTENSIONS: tuple[str, ...] = (
    ".yml", ".yaml", ".toml", ".ini", ".cfg", ".env",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".txt", ".rst", ".adoc", ".asciidoc",
    ".mk",
)

# Bare filenames (case-insensitive, exact basename) we treat as text.
_BARE_NAMES: frozenset[str] = frozenset({
    "makefile",
    "gnumakefile",
    "dockerfile",
    "containerfile",
    "justfile",
    "procfile",
    "caddyfile",
})

# Bare filename prefixes (e.g. "Dockerfile.chio-kb-mcp").
_BARE_PREFIXES: tuple[str, ...] = ("dockerfile.",)


def _matches_bare_name(file_path: str) -> bool:
    name = Path(file_path).name.lower()
    if name in _BARE_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in _BARE_PREFIXES)


def _find_boundaries(lines: list[str]) -> list[int]:
    """Return 1-based line numbers that should start a new chunk."""
    boundaries: list[int] = [1]
    for i, line in enumerate(lines, start=1):
        if any(pat.search(line) for pat in _BOUNDARY_PATTERNS):
            if i != boundaries[-1]:
                boundaries.append(i)
    return boundaries


def chunk_text_file(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[Chunk]:
    """Chunk a text/config file into structural + size-bounded pieces."""
    if not text.strip():
        return []
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return []
    boundaries = _find_boundaries(lines)
    ranges = boundaries_to_ranges(boundaries, total)
    out: list[Chunk] = []
    for idx, (start, end) in enumerate(ranges, start=1):
        body = slice_lines(text, start, end)
        if not body.strip():
            continue
        name = f"chunk#{idx}"
        first_line = lines[start - 1] if start - 1 < total else ""
        stripped = first_line.strip()
        if stripped.endswith(":"):
            name = stripped[:-1].strip() or name
        elif stripped.upper().startswith("FROM "):
            name = stripped.split()[1] if len(stripped.split()) > 1 else name
        chunk = Chunk(
            name=name,
            kind="section",
            line_start=start,
            line_end=end,
            text=body,
        )
        if len(body) > max_chars:
            out.extend(fallback_size_chunks(body, name_prefix=name, max_chars=max_chars))
        else:
            out.append(chunk)
    if not out:
        out = fallback_size_chunks(text, name_prefix="section", max_chars=max_chars)
    return out


class TextIngester:
    """`SourceIngester` for Makefiles, Dockerfiles, YAML, TOML, shell, etc."""

    EXTENSIONS = EXTENSIONS
    LANGUAGE = "text"

    def __init__(self, *, max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS) -> None:
        self.max_chunk_chars = max_chunk_chars

    def __call__(self, file_path: str) -> ParsedFile | None:
        return self.ingest(file_path)

    def ingest(self, file_path: str) -> ParsedFile | None:
        if is_skipped_path(file_path):
            return None
        if not (
            has_extension(file_path, *self.EXTENSIONS)
            or _matches_bare_name(file_path)
        ):
            return None
        text = read_text_safely(file_path)
        if text is None:
            return None
        chunks = chunk_text_file(text, max_chars=self.max_chunk_chars)
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
            properties={"chunks": chunk_texts, "ingester": "kb_engine.builtin.text"},
        )


def text_source_ingester(file_path: str) -> ParsedFile | None:
    """Stateless wrapper around :class:`TextIngester` for entry-point use."""
    return TextIngester()(file_path)


__all__ = ["TextIngester", "chunk_text_file", "text_source_ingester"]
