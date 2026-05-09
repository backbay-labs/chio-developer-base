"""Tests for `kb_engine.ingesters.typescript`.

Covers:
  - Chunk count for the canonical fixture (function + interface + arrow
    binding + module preamble = 4).
  - Chunk text is whole-line.
  - Line ranges are monotonic, non-overlapping, span 1 .. EOF.
  - Vendor / build directories (`node_modules/`, `dist/`, `.next/`) are
    skipped even when handed in directly.
  - `.d.ts` declaration files are skipped (header-only, not source).
  - The function-style alias works the same as the class form.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_engine.ingesters import TypescriptIngester
from kb_engine.ingesters.typescript import (
    chunk_typescript,
    typescript_source_ingester,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "text-ingest"


def test_typescript_ingester_returns_parsed_file():
    parsed = TypescriptIngester().ingest(str(FIXTURE_DIR / "sample.ts"))
    assert parsed is not None
    assert parsed.language == "typescript"
    # Module preamble + greet + User + formatUser = 4 symbols.
    assert len(parsed.symbols) == 4


def test_typescript_ingester_emits_one_chunk_per_top_level_decl():
    parsed = TypescriptIngester().ingest(str(FIXTURE_DIR / "sample.ts"))
    assert parsed is not None
    kinds = [s.kind for s in parsed.symbols]
    names = [s.name for s in parsed.symbols]
    assert kinds == ["module", "function", "interface", "binding"]
    assert names == ["<module>", "greet", "User", "formatUser"]


def test_typescript_ingester_line_ranges_monotonic_and_non_overlapping():
    parsed = TypescriptIngester().ingest(str(FIXTURE_DIR / "sample.ts"))
    assert parsed is not None
    syms = parsed.symbols
    for a, b in zip(syms, syms[1:]):
        assert a.line_start < b.line_start
        assert a.line_end < b.line_start
    assert syms[0].line_start == 1
    file_lines = (FIXTURE_DIR / "sample.ts").read_text().splitlines()
    assert syms[-1].line_end == len(file_lines)


def test_typescript_chunks_are_whole_line():
    parsed = TypescriptIngester().ingest(str(FIXTURE_DIR / "sample.ts"))
    assert parsed is not None
    file_lines = (FIXTURE_DIR / "sample.ts").read_text().splitlines()
    for sym, chunk_text in zip(parsed.symbols, parsed.properties["chunks"]):
        expected = "\n".join(file_lines[sym.line_start - 1:sym.line_end])
        assert chunk_text == expected


def test_typescript_ingester_skips_vendored_path(tmp_path: Path):
    # Path containing `node_modules` must be skipped.
    p = FIXTURE_DIR / "node_modules" / "some-pkg" / "index.ts"
    assert p.exists(), "fixture missing"
    assert TypescriptIngester().ingest(str(p)) is None

    # Synthetic dist/ path
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    f = dist_dir / "bundle.js"
    f.write_text("export function x(){return 1;}\n")
    assert TypescriptIngester().ingest(str(f)) is None


def test_typescript_skips_declaration_files(tmp_path: Path):
    f = tmp_path / "types.d.ts"
    f.write_text("export interface X { a: number }\n")
    assert TypescriptIngester().ingest(str(f)) is None


def test_typescript_handles_jsx_and_javascript(tmp_path: Path):
    jsx = tmp_path / "Comp.jsx"
    jsx.write_text("export function Comp() { return null; }\n")
    parsed = TypescriptIngester().ingest(str(jsx))
    assert parsed is not None
    assert parsed.language == "javascript"

    tsx = tmp_path / "Comp.tsx"
    tsx.write_text("export function Comp() { return null; }\n")
    parsed = TypescriptIngester().ingest(str(tsx))
    assert parsed is not None
    assert parsed.language == "typescript"


def test_typescript_function_alias_works():
    parsed = typescript_source_ingester(str(FIXTURE_DIR / "sample.ts"))
    assert parsed is not None
    assert len(parsed.symbols) == 4


def test_typescript_chunk_oversize_falls_back_to_size_split():
    big = "export const huge = (\n" + "\n".join(f"  v{i}: {i}," for i in range(1000)) + "\n);\n"
    chunks = chunk_typescript(big, max_chars=200)
    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:]):
        assert a.line_end < b.line_start


def test_typescript_handles_class_with_decorator(tmp_path: Path):
    src = (
        "import { Component } from '@angular/core';\n"
        "\n"
        "@Component({ selector: 'app-x' })\n"
        "export class XComponent {\n"
        "  title = 'x';\n"
        "}\n"
    )
    f = tmp_path / "x.ts"
    f.write_text(src)
    parsed = TypescriptIngester().ingest(str(f))
    assert parsed is not None
    cls = next(s for s in parsed.symbols if s.kind == "class")
    chunks = parsed.properties["chunks"]
    cls_text = chunks[parsed.symbols.index(cls)]
    assert "@Component" in cls_text


@pytest.mark.parametrize(
    "filename,expected_lang",
    [("a.ts", "typescript"), ("a.tsx", "typescript"),
     ("a.js", "javascript"), ("a.jsx", "javascript"),
     ("a.mts", "typescript"), ("a.cts", "typescript")],
)
def test_typescript_extension_dispatch(tmp_path: Path, filename: str, expected_lang: str):
    f = tmp_path / filename
    f.write_text("export function foo(){return 1;}\n")
    parsed = TypescriptIngester().ingest(str(f))
    assert parsed is not None
    assert parsed.language == expected_lang
