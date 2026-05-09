"""Tests for `kb_engine.ingesters.python`.

Covers:
  - Chunk count matches the expected definition count + module preamble.
  - Chunk text is whole-line (no mid-token truncation).
  - Line ranges are 1-based, monotonic, and cover the whole file.
  - Vendor / build directories (`__pycache__/`, `.venv/`, `node_modules/`)
    are skipped even when handed in directly.
  - The class chunk includes its methods (no per-method splits — pack
    ingesters can override that).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_engine.ingesters import PythonIngester
from kb_engine.ingesters.python import chunk_python, python_source_ingester

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "text-ingest"


def test_python_ingester_returns_parsed_file():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    assert parsed.language == "python"
    assert parsed.path == str(FIXTURE_DIR / "sample.py")
    # Module preamble + add + multiply + Calculator = 4 symbols.
    assert len(parsed.symbols) == 4


def test_python_ingester_emits_one_chunk_per_top_level_def():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    kinds = [s.kind for s in parsed.symbols]
    names = [s.name for s in parsed.symbols]
    assert kinds == ["module", "function", "function", "class"]
    assert names == ["<module>", "add", "multiply", "Calculator"]


def test_python_ingester_line_ranges_are_monotonic_and_non_overlapping():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    syms = parsed.symbols
    # start_line strictly increasing
    for a, b in zip(syms, syms[1:]):
        assert a.line_start < b.line_start
    # No overlaps: each symbol's end_line must be < the next's start_line.
    for a, b in zip(syms, syms[1:]):
        assert a.line_end < b.line_start
    # First symbol covers from line 1; last symbol covers through the end.
    assert syms[0].line_start == 1
    file_lines = (FIXTURE_DIR / "sample.py").read_text().splitlines()
    assert syms[-1].line_end == len(file_lines)


def test_python_ingester_class_chunk_contains_its_methods():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    chunks = parsed.properties["chunks"]
    class_idx = next(i for i, s in enumerate(parsed.symbols) if s.kind == "class")
    class_text = chunks[class_idx]
    # Class chunk MUST contain the methods — class is one chunk, not many.
    assert "class Calculator" in class_text
    assert "def __init__" in class_text
    assert "def add" in class_text
    assert "def reset" in class_text


def test_python_ingester_chunks_are_whole_line():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    file_lines = (FIXTURE_DIR / "sample.py").read_text().splitlines()
    for sym, chunk_text in zip(parsed.symbols, parsed.properties["chunks"]):
        # Reconstruct the slice from the file and verify byte equality.
        expected = "\n".join(file_lines[sym.line_start - 1:sym.line_end])
        assert chunk_text == expected, (
            f"chunk for {sym.name!r} does not match exact line slice"
        )


def test_python_ingester_skips_non_python_files():
    parsed = PythonIngester().ingest(str(FIXTURE_DIR / "sample.md"))
    assert parsed is None
    parsed = PythonIngester().ingest("/nope/foo.txt")
    assert parsed is None


def test_python_ingester_skips_vendor_dirs(tmp_path: Path):
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    target = venv_dir / "x.py"
    target.write_text("def x(): return 1\n")
    assert PythonIngester().ingest(str(target)) is None

    pycache = tmp_path / "pkg" / "__pycache__"
    pycache.mkdir(parents=True)
    cached = pycache / "y.py"
    cached.write_text("def y(): return 2\n")
    assert PythonIngester().ingest(str(cached)) is None


def test_python_ingester_handles_empty_file(tmp_path: Path):
    empty = tmp_path / "empty.py"
    empty.write_text("")
    parsed = PythonIngester().ingest(str(empty))
    assert parsed is not None
    assert parsed.symbols == []
    assert parsed.properties["chunks"] == []


def test_python_ingester_handles_no_definitions(tmp_path: Path):
    no_defs = tmp_path / "constants.py"
    no_defs.write_text("MAX = 10\nMIN = 0\n")
    parsed = PythonIngester().ingest(str(no_defs))
    assert parsed is not None
    assert len(parsed.symbols) == 1
    assert parsed.symbols[0].kind == "module"
    assert parsed.symbols[0].name == "<module>"


def test_python_chunk_function_absorbs_decorators(tmp_path: Path):
    src = (
        "import functools\n"
        "\n"
        "@functools.cache\n"
        "@staticmethod\n"
        "def cached_fn():\n"
        "    return 1\n"
    )
    f = tmp_path / "deco.py"
    f.write_text(src)
    parsed = PythonIngester().ingest(str(f))
    assert parsed is not None
    fn_sym = next(s for s in parsed.symbols if s.kind == "function")
    # Decorator at line 3 should be part of the function chunk.
    chunks = parsed.properties["chunks"]
    fn_idx = parsed.symbols.index(fn_sym)
    fn_text = chunks[fn_idx]
    assert "@functools.cache" in fn_text
    assert "@staticmethod" in fn_text
    assert fn_sym.line_start == 3


def test_python_chunk_pure_function_form_returns_parsed_file():
    """The function-style alias must work the same as the class form."""
    parsed = python_source_ingester(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    assert parsed.language == "python"
    assert len(parsed.symbols) == 4


def test_chunk_python_oversize_falls_back_to_size_split():
    # One huge function whose body exceeds the size cap.
    long_body = "\n".join(f"    x = {i}" for i in range(1000))
    src = f"def big():\n{long_body}\n"
    chunks = chunk_python(src, max_chars=200)
    # Must produce multiple chunks via fallback splitter.
    assert len(chunks) > 1
    # Line ranges must still be non-overlapping.
    for a, b in zip(chunks, chunks[1:]):
        assert a.line_end < b.line_start


@pytest.mark.parametrize("filename", ["sample.PY", "Sample.py"])
def test_python_extension_match_case_insensitive(tmp_path: Path, filename: str):
    f = tmp_path / filename
    f.write_text("def x(): return 1\n")
    assert PythonIngester().ingest(str(f)) is not None
