"""Tests for the Wave 1 text chunker."""
from __future__ import annotations

from kb_engine.chunker import chunk_text


def test_chunk_text_splits_long_input():
    text = "\n".join(f"line {i}" for i in range(1, 401))
    chunks = chunk_text(text, max_chars=500, overlap_lines=2)
    assert len(chunks) > 1
    assert chunks[0].line_start == 1
    assert chunks[0].text
    # Overlap means later chunks start before prior end.
    assert chunks[1].line_start <= chunks[0].line_end


def test_chunk_text_empty():
    assert chunk_text("") == []
