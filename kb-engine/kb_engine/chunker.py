"""Symbol-aligned / size-bounded text chunker for ingest.

Phase 1.3 replaces the naive one-chunk-per-file path in
``IngestPipeline.ingest_file``. Chunks stay small enough for embedding
quality while preserving line ranges for citation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A contiguous slice of a source file ready for embedding."""

    text: str
    line_start: int  # 1-indexed inclusive
    line_end: int  # 1-indexed inclusive


def chunk_text(
    text: str,
    *,
    max_chars: int = 2400,
    overlap_lines: int = 2,
) -> list[TextChunk]:
    """Split ``text`` into overlapping line-bounded chunks.

    Strategy:
      1. Prefer blank-line paragraph boundaries when under ``max_chars``.
      2. Fall back to hard line windows when a paragraph is oversized.
      3. Overlap the last ``overlap_lines`` of the previous chunk so
         symbol definitions that straddle a boundary stay findable.

    Empty / whitespace-only input yields no chunks.
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines()
    if not lines:
        return [TextChunk(text=text, line_start=1, line_end=1)]

    # Fast path: whole file fits.
    if len(text) <= max_chars:
        return [
            TextChunk(
                text=text if text.endswith("\n") else text + "\n" if "\n" in text else text,
                line_start=1,
                line_end=len(lines),
            )
        ]

    paragraphs = _paragraph_ranges(lines)
    chunks: list[TextChunk] = []
    buf_start = paragraphs[0][0] if paragraphs else 0
    buf_end = buf_start
    buf_chars = 0

    def _flush(start: int, end: int) -> None:
        if start > end:
            return
        slice_lines = lines[start : end + 1]
        body = "\n".join(slice_lines)
        if not body.strip():
            return
        chunks.append(
            TextChunk(
                text=body,
                line_start=start + 1,
                line_end=end + 1,
            )
        )

    for p_start, p_end in paragraphs:
        p_chars = sum(len(lines[i]) + 1 for i in range(p_start, p_end + 1))
        if p_chars > max_chars:
            if buf_chars:
                _flush(buf_start, buf_end)
                buf_chars = 0
            chunks.extend(_hard_line_windows(lines, p_start, p_end, max_chars, overlap_lines))
            buf_start = p_end + 1
            buf_end = p_end
            continue
        if buf_chars and buf_chars + p_chars > max_chars:
            _flush(buf_start, buf_end)
            # Overlap: restart a few lines before the new paragraph.
            overlap_start = max(p_start - overlap_lines, buf_start)
            # But never re-emit the entire previous buffer.
            buf_start = max(overlap_start, buf_end - overlap_lines + 1)
            if buf_start > p_start:
                buf_start = p_start
            buf_end = p_end
            buf_chars = sum(len(lines[i]) + 1 for i in range(buf_start, buf_end + 1))
            # Oversized single paragraph: hard-split by lines.
            if buf_chars > max_chars:
                for hard in _hard_line_windows(lines, p_start, p_end, max_chars, overlap_lines):
                    chunks.append(hard)
                buf_start = p_end + 1
                buf_end = p_end
                buf_chars = 0
            continue

        if buf_chars == 0:
            buf_start = p_start
        buf_end = p_end
        buf_chars = sum(len(lines[i]) + 1 for i in range(buf_start, buf_end + 1))

    if buf_chars:
        _flush(buf_start, buf_end)

    return chunks or [
        TextChunk(text=text, line_start=1, line_end=len(lines))
    ]


def _paragraph_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Return inclusive (start, end) line-index ranges for paragraphs."""
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip():
            if start is None:
                start = i
        else:
            if start is not None:
                ranges.append((start, i - 1))
                start = None
    if start is not None:
        ranges.append((start, len(lines) - 1))
    return ranges or [(0, len(lines) - 1)]


def _hard_line_windows(
    lines: list[str],
    start: int,
    end: int,
    max_chars: int,
    overlap_lines: int,
) -> list[TextChunk]:
    out: list[TextChunk] = []
    i = start
    while i <= end:
        chars = 0
        j = i
        while j <= end:
            add = len(lines[j]) + 1
            if chars and chars + add > max_chars:
                break
            chars += add
            j += 1
        if j == i:
            j = i + 1  # force progress on a single oversized line
        body = "\n".join(lines[i:j])
        out.append(TextChunk(text=body, line_start=i + 1, line_end=j))
        if j > end:
            break
        i = max(j - overlap_lines, i + 1)
    return out
