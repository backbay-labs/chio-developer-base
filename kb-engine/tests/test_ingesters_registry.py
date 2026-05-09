"""End-to-end tests for builtin-ingester registration on `Registry`.

Covers:
  - `Registry()` auto-seeds the kb-engine builtins on construction.
  - `Registry.ingest_file(...)` routes `.py` / `.ts` / `.md` to the
    correct builtin and returns the expected `ParsedFile`.
  - The pack > builtin precedence rule: a pack-registered hook for the
    same extension wins over the builtin.
  - `seed_builtins=False` produces a strictly empty registry.
  - `clear_builtin_ingesters()` removes the seeded builtins.
  - Re-calling `register_builtin_ingesters()` is idempotent.
  - The full `load_entry_points()` path coexists with builtins.
"""
from __future__ import annotations

from pathlib import Path

from kb_engine import ParsedFile, Registry

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "text-ingest"


def test_registry_seeds_builtins_on_construction():
    r = Registry()
    # Three builtins: python, typescript, markdown.
    assert len(r._builtin_source_ingesters) == 3


def test_registry_ingest_file_routes_python_to_builtin():
    r = Registry()
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.py"))
    assert isinstance(parsed, ParsedFile)
    assert parsed.language == "python"
    # 1 module + 2 functions + 1 class = 4 chunks
    assert len(parsed.symbols) == 4
    assert {s.name for s in parsed.symbols} == {
        "<module>", "add", "multiply", "Calculator",
    }


def test_registry_ingest_file_routes_typescript_to_builtin():
    r = Registry()
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.ts"))
    assert isinstance(parsed, ParsedFile)
    assert parsed.language == "typescript"
    assert {s.name for s in parsed.symbols} == {
        "<module>", "greet", "User", "formatUser",
    }


def test_registry_ingest_file_routes_markdown_to_builtin():
    r = Registry()
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.md"))
    assert isinstance(parsed, ParsedFile)
    assert parsed.language == "markdown"
    assert len(parsed.symbols) == 4


def test_registry_no_builtin_match_returns_none():
    r = Registry()
    # Unknown extension — no builtin matches.
    assert r.ingest_file("/tmp/nope.unknownext") is None


def test_pack_ingester_takes_precedence_over_builtin():
    """A pack-registered hook for `.py` MUST shadow the builtin."""
    r = Registry()

    sentinel = ParsedFile(
        path="sentinel.py",
        language="custom-python",
        text="",
        properties={"from": "pack"},
    )

    def pack_python_ingester(file_path: str) -> ParsedFile | None:
        if file_path.endswith(".py"):
            return sentinel
        return None

    r.register_source_ingester(pack_python_ingester)
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.py"))
    assert parsed is sentinel  # not the builtin's ParsedFile
    assert parsed.language == "custom-python"
    assert parsed.properties["from"] == "pack"


def test_pack_ingester_returning_none_falls_through_to_builtin():
    """If a pack hook returns None for a file, the builtin still gets a turn."""
    r = Registry()

    def pack_skipper(file_path: str) -> ParsedFile | None:
        return None  # never claims anything

    r.register_source_ingester(pack_skipper)
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    assert parsed.language == "python"  # builtin handled it


def test_seed_builtins_false_yields_empty_registry():
    r = Registry(seed_builtins=False)
    assert r._builtin_source_ingesters == []
    assert r.ingest_file(str(FIXTURE_DIR / "sample.py")) is None


def test_clear_builtin_ingesters_removes_them():
    r = Registry()
    assert r._builtin_source_ingesters
    r.clear_builtin_ingesters()
    assert r._builtin_source_ingesters == []
    assert r.ingest_file(str(FIXTURE_DIR / "sample.py")) is None


def test_register_builtin_ingesters_is_idempotent():
    r = Registry()
    n_first = len(r._builtin_source_ingesters)
    r.register_builtin_ingesters()
    r.register_builtin_ingesters()
    assert len(r._builtin_source_ingesters) == n_first


def test_load_entry_points_coexists_with_builtins(monkeypatch):
    """A simulated entry-point registers a pack ingester. Builtins survive."""
    r = Registry()
    initial_pack = len(r.source_ingesters)
    initial_builtins = len(r._builtin_source_ingesters)

    # Simulate what an entry-point would do: register a pack hook.
    def fake_pack_register(reg: Registry) -> None:
        def fake_rust_ingester(file_path: str) -> ParsedFile | None:
            if file_path.endswith(".rs"):
                return ParsedFile(path=file_path, language="rust", text="")
            return None
        reg.register_source_ingester(fake_rust_ingester)

    fake_pack_register(r)
    assert len(r.source_ingesters) == initial_pack + 1
    assert len(r._builtin_source_ingesters) == initial_builtins  # unchanged

    # Pack hook handles .rs; builtins still handle .py / .ts / .md
    assert r.ingest_file("crates/foo/src/lib.rs") is not None
    assert r.ingest_file(str(FIXTURE_DIR / "sample.py")) is not None
    assert r.ingest_file(str(FIXTURE_DIR / "sample.md")) is not None


def test_full_pipeline_python_fixture_via_registry():
    """Acceptance signal from the spec: PythonIngester via Registry returns
    a ParsedFile with N chunks for a fixture with N top-level definitions.
    """
    r = Registry()
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    # 2 functions + 1 class = 3 top-level definitions, plus 1 module preamble.
    n_definitions = sum(1 for s in parsed.symbols if s.kind in {"function", "class"})
    assert n_definitions == 3
    # Chunks list aligns 1:1 with symbols.
    assert len(parsed.properties["chunks"]) == len(parsed.symbols)


def test_full_pipeline_via_load_entry_points_returns_chunks():
    """Acceptance signal: `Registry().load_entry_points(); ingest_file(...)`
    returns chunks.

    The spec asks for the `load_entry_points()` path to be exercised. We
    invoke it on the live entry-point group ("kb_engine.plugins"). chio-pack
    is installed in this test environment and registers a Rust ingester;
    that does not interfere with the Python builtin.
    """
    r = Registry()
    r.load_entry_points()
    parsed = r.ingest_file(str(FIXTURE_DIR / "sample.py"))
    assert parsed is not None
    assert parsed.language == "python"
    assert len(parsed.symbols) == 4
    assert len(parsed.properties["chunks"]) == 4
