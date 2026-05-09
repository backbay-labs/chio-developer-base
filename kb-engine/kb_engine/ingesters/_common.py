"""Shared helpers for the built-in text ingesters.

Private — not part of the public kb_engine surface. Each language ingester
owns its own delimiter regex; this module just centralises the bits that
are genuinely language-agnostic: vendor-dir skipping, binary heuristics,
size-based fallback chunking, file-read with encoding fallback.

Why no AST libraries
--------------------

We deliberately do not depend on `ast`, `parso`, tree-sitter, etc. for the
built-ins. The contract for kb-engine builtins is: a pragmatic chunk per
top-level structural unit, with line ranges for citation. Adopters who
want real symbol resolution write a pack ingester (the chio-pack Rust
tree-sitter ingester is the canonical example). Keeping builtins regex-based
means the engine stays cheap to install (no native deps), survives
syntax-broken in-progress files, and works on `.ts` (where the stdlib has
no parser) the same way it works on `.py`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# Directories that we never descend into when ingesting a tree, regardless
# of language. These are vendored / build-output / virtualenv directories.
# This list is INTENTIONALLY conservative — packs that need finer control
# can register a pre-filter or override the relevant ingester.
SKIP_DIR_NAMES: frozenset[str] = frozenset({
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "target",          # Rust build output
    "dist",            # JS/TS bundler output
    "build",           # generic build output
    ".git",
    ".obsidian",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".next",           # Next.js
    ".nuxt",           # Nuxt
    ".cache",
    "coverage",
    ".coverage",
})

# Hard ceiling on chunk size in characters. If a single structural unit
# (giant function, giant prose section) exceeds this, we fall back to a
# size-based split. Aligns roughly with a token budget that fits in the
# embedding model's context (~8k tokens / 4 chars-per-token).
DEFAULT_MAX_CHUNK_CHARS = 8_000


def is_skipped_path(path: str | os.PathLike[str]) -> bool:
    """Return True if any path component is a vendored / build-output dir.

    Used both at tree-walk time (to prune) and at ingest time (so a single
    file path that happens to be inside `node_modules/` is rejected even
    when handed in directly).
    """
    parts = Path(path).parts
    return any(part in SKIP_DIR_NAMES for part in parts)


def looks_binary(text_sample: bytes) -> bool:
    """Heuristic: does this byte sample look like binary content?

    A NUL byte in the first 8 KiB is the canonical signal git uses too.
    Used to skip files that have a text extension but contain non-text
    payloads (e.g. a `.py` file with a pickled blob).
    """
    return b"\x00" in text_sample


def read_text_safely(file_path: str | os.PathLike[str]) -> str | None:
    """Read file as utf-8 with replacement; return None on binary/unreadable.

    Returns None instead of raising so callers can simply skip the file.
    """
    p = Path(file_path)
    try:
        head = p.read_bytes()[:8192]
    except OSError:
        return None
    if looks_binary(head):
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


@dataclass(frozen=True)
class Chunk:
    """A single text chunk with line-range metadata.

    Mirrors the shape that ingesters convert into `Symbol` entries on the
    `ParsedFile`. Line numbers are 1-based and inclusive. The chunk text
    contains the lines between `line_start` and `line_end`, joined by `\\n`,
    without trailing newline.
    """

    name: str
    kind: str
    line_start: int
    line_end: int
    text: str


def split_lines_keepends(text: str) -> list[str]:
    """Split text into lines without losing line endings.

    Used so we can reconstitute exact byte-for-byte ranges if needed.
    Standard `str.splitlines()` drops the newline character.
    """
    return text.splitlines(keepends=True)


def fallback_size_chunks(
    text: str,
    *,
    name_prefix: str,
    kind: str = "chunk",
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[Chunk]:
    """Last-resort splitter: cut a too-long region on line boundaries.

    Called when a structural unit (function body, prose section) exceeds
    `max_chars`. We split between lines so we never truncate mid-token.
    Used only as the fallback path — the primary chunk strategy is
    structural delimiters per ingester.
    """
    if not text:
        return []
    lines = text.splitlines()  # without trailing newlines for length math
    chunks: list[Chunk] = []
    cur: list[str] = []
    cur_chars = 0
    cur_start = 1
    counter = 0
    for i, line in enumerate(lines, start=1):
        line_len = len(line) + 1  # +1 for the newline that separates lines
        if cur and cur_chars + line_len > max_chars:
            counter += 1
            chunks.append(Chunk(
                name=f"{name_prefix}#{counter}",
                kind=kind,
                line_start=cur_start,
                line_end=cur_start + len(cur) - 1,
                text="\n".join(cur),
            ))
            cur_start = i
            cur = []
            cur_chars = 0
        cur.append(line)
        cur_chars += line_len
    if cur:
        counter += 1
        chunks.append(Chunk(
            name=f"{name_prefix}#{counter}",
            kind=kind,
            line_start=cur_start,
            line_end=cur_start + len(cur) - 1,
            text="\n".join(cur),
        ))
    return chunks


def slice_lines(text: str, line_start: int, line_end: int) -> str:
    """Return the (1-based, inclusive) line range from `text`.

    Defensive bounds: if line_end exceeds the file's line count we clamp.
    Returns an empty string if the range is empty or out of range.
    """
    if line_start < 1 or line_end < line_start:
        return ""
    lines = text.splitlines()
    n = len(lines)
    if line_start > n:
        return ""
    end = min(line_end, n)
    return "\n".join(lines[line_start - 1:end])


# Compile-once helper for ingesters that want to gate by extension.
def has_extension(file_path: str, *exts: str) -> bool:
    """Case-insensitive extension match. `exts` should include the dot."""
    lower = file_path.lower()
    return any(lower.endswith(e.lower()) for e in exts)


# Shared boundary-collapsing utility: given a sorted list of split-point
# line numbers (1-based), produce non-overlapping (start, end) ranges
# that cover [1, total_lines]. Each split point becomes the start of a
# new range; the previous range ends one line earlier.
def boundaries_to_ranges(
    boundaries: list[int],
    total_lines: int,
) -> list[tuple[int, int]]:
    """Convert sorted split-point line numbers into (start, end) ranges.

    `boundaries` are 1-based. The first range starts at 1 even if the
    first boundary is > 1 (preamble / module docstring). Ranges are
    non-overlapping and contiguous; their union is [1, total_lines].
    """
    if total_lines <= 0:
        return []
    starts = sorted({b for b in boundaries if 1 <= b <= total_lines})
    if not starts or starts[0] != 1:
        starts = [1, *starts]
    ranges: list[tuple[int, int]] = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else total_lines
        if end >= start:
            ranges.append((start, end))
    return ranges


__all__ = [
    "Chunk",
    "DEFAULT_MAX_CHUNK_CHARS",
    "SKIP_DIR_NAMES",
    "boundaries_to_ranges",
    "fallback_size_chunks",
    "has_extension",
    "is_skipped_path",
    "looks_binary",
    "read_text_safely",
    "slice_lines",
    "split_lines_keepends",
]


# Defensive re-export of `re` for ingesters that want our pre-compiled
# pattern utilities; kept simple and explicit.
_RE = re  # noqa: F841 — placeholder for future shared regex helpers
