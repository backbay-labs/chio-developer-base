"""End-to-end tests for the ingest pipeline using all-fake backing stores."""
from __future__ import annotations

import pathlib

import pytest

from kb_engine import IngestPipeline, Node, Edge, ParsedFile, Registry
from kb_engine.store import FakeEmbedder
from kb_engine.store.postgres import CodeChunk


class FakePostgres:
    """In-memory postgres-shape stub. Only what IngestPipeline calls."""

    def __init__(self):
        self.bootstrapped = False
        self.chunks: list[tuple[CodeChunk, list[float]]] = []

    def bootstrap(self):
        self.bootstrapped = True

    def insert_code_chunks(self, chunks, embeddings):
        for c, e in zip(chunks, embeddings):
            self.chunks.append((c, list(e)))
        return len(chunks)


class FakeNeo4j:
    """In-memory neo4j-shape stub."""

    def __init__(self):
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def apply_constraints(self, stmts):
        pass

    def upsert_nodes(self, nodes):
        self.nodes.extend(nodes)
        return len(nodes)

    def upsert_edges(self, edges):
        self.edges.extend(edges)
        return len(edges)


def _make_registry_for_rust():
    # Pack-only registry: these tests assert rust-ingester behavior without
    # the kb-engine builtins claiming .py/.md/.txt files.
    r = Registry(seed_builtins=False)

    def rust_ingester(file_path: str):
        if not file_path.endswith(".rs"):
            return None
        return ParsedFile(
            path=file_path, language="rust", text="",  # text filled by pipeline
            properties={"crate": "test-crate"},
        )

    def rust_projector(parsed):
        if parsed.language != "rust":
            return []
        return [
            Node(id=f"file:{parsed.path}", label="File", properties={"path": parsed.path}),
            Node(id="crate:test-crate", label="Crate", properties={"name": "test-crate"}),
            Edge(
                src_id="crate:test-crate",
                dst_id=f"file:{parsed.path}",
                relationship="CONTAINS",
            ),
        ]

    r.register_source_ingester(rust_ingester)
    r.register_graph_projector(rust_projector)
    return r


def test_ingest_python_via_builtin(tmp_path):
    """Wave 1: default Registry seeds PythonIngester; .py files are ingested."""
    src = tmp_path / "repo"
    src.mkdir()
    py = src / "x.py"
    py.write_text("def hello():\n    return 1\n")

    registry = Registry()  # builtins on
    pg = FakePostgres()
    neo = FakeNeo4j()
    # FakePostgres needs insert_doc_chunks too if routed as docs — python is code.
    if not hasattr(pg, "insert_doc_chunks"):
        pg.insert_doc_chunks = pg.insert_code_chunks  # type: ignore[attr-defined]
    pipeline = IngestPipeline(registry, postgres=pg, neo4j=neo, embedder=FakeEmbedder(dim=8))

    n_nodes, n_edges, n_chunks = pipeline.ingest_file(py, src)
    assert n_chunks >= 1
    assert pg.chunks
    assert pg.chunks[0][0].file_path == "x.py"
    assert pg.chunks[0][0].language == "python"


def test_ingest_single_rust_file(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    rs = src / "lib.rs"
    rs.write_text("fn hello() {}\n")

    registry = _make_registry_for_rust()
    pg = FakePostgres()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=pg, neo4j=neo, embedder=FakeEmbedder(dim=8))

    n_nodes, n_edges, n_chunks = pipeline.ingest_file(rs, src)
    assert n_nodes == 2
    assert n_edges == 1
    assert n_chunks == 1
    assert {n.label for n in neo.nodes} == {"File", "Crate"}
    assert neo.edges[0].relationship == "CONTAINS"
    chunk, embedding = pg.chunks[0]
    assert chunk.file_path == "lib.rs"
    assert chunk.language == "rust"
    assert chunk.chunk_text == "fn hello() {}\n"
    assert len(embedding) == 8


def test_ingest_skips_non_rust(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    py = src / "x.py"
    py.write_text("print('hi')\n")

    registry = _make_registry_for_rust()
    pg = FakePostgres()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=pg, neo4j=neo, embedder=FakeEmbedder(dim=8))

    n_nodes, n_edges, n_chunks = pipeline.ingest_file(py, src)
    assert (n_nodes, n_edges, n_chunks) == (0, 0, 0)
    assert pg.chunks == []
    assert neo.nodes == []


def test_ingest_tree_walks_recursively_and_skips_dot_dirs(tmp_path):
    src = tmp_path / "repo"
    (src / "crates" / "foo" / "src").mkdir(parents=True)
    (src / "crates" / "foo" / "src" / "lib.rs").write_text("fn a() {}\n")
    (src / ".git").mkdir()
    (src / ".git" / "config.rs").write_text("fn skipped() {}\n")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "lib.rs").write_text("fn skipped2() {}\n")

    registry = _make_registry_for_rust()
    pg = FakePostgres()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=pg, neo4j=neo, embedder=FakeEmbedder(dim=8))

    stats = pipeline.ingest_tree(src)
    assert stats.files_ingested == 1  # only the real lib.rs, .git and node_modules skipped
    assert stats.nodes_upserted == 2
    assert stats.edges_upserted == 1
    assert stats.chunks_inserted == 1


def test_ingest_pipeline_works_without_postgres(tmp_path):
    """Pipeline degrades gracefully when no Postgres / no embedder."""
    src = tmp_path / "repo"
    src.mkdir()
    rs = src / "lib.rs"
    rs.write_text("fn x() {}\n")

    registry = _make_registry_for_rust()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=None, neo4j=neo, embedder=None)
    n_nodes, n_edges, n_chunks = pipeline.ingest_file(rs, src)
    assert n_nodes == 2
    assert n_edges == 1
    assert n_chunks == 0  # no postgres → no chunks


def test_ingest_pipeline_works_without_neo4j(tmp_path):
    src = tmp_path / "repo"
    src.mkdir()
    rs = src / "lib.rs"
    rs.write_text("fn x() {}\n")

    registry = _make_registry_for_rust()
    pg = FakePostgres()
    pipeline = IngestPipeline(registry, postgres=pg, neo4j=None, embedder=FakeEmbedder(dim=8))
    n_nodes, n_edges, n_chunks = pipeline.ingest_file(rs, src)
    assert n_nodes == 0
    assert n_edges == 0
    assert n_chunks == 1


def test_ingest_tree_respects_include_globs(tmp_path):
    """ingest_tree(include_globs=...) restricts the walk to matching files.

    Used by sources.toml's optional `glob = [...]` setting.
    """
    src = tmp_path / "repo"
    (src / "crates").mkdir(parents=True)
    (src / "crates" / "kept.rs").write_text("fn kept() {}\n")
    (src / "crates" / "skipped.rs").write_text("fn skipped() {}\n")

    registry = _make_registry_for_rust()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=None, neo4j=neo, embedder=None)
    stats = pipeline.ingest_tree(src, include_globs=["crates/kept.rs"])
    assert stats.files_ingested == 1
    assert all("kept" in n.id for n in neo.nodes if n.label == "File")


def test_ingest_tree_respects_exclude_globs(tmp_path):
    """ingest_tree(exclude_globs=...) drops matching files even if include accepts them."""
    src = tmp_path / "repo"
    (src / "crates").mkdir(parents=True)
    (src / "crates" / "kept.rs").write_text("fn kept() {}\n")
    (src / "crates" / "_archive.rs").write_text("fn archived() {}\n")

    registry = _make_registry_for_rust()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=None, neo4j=neo, embedder=None)
    stats = pipeline.ingest_tree(src, exclude_globs=["crates/_archive.rs"])
    assert stats.files_ingested == 1


def test_ingest_tree_empty_globs_includes_everything(tmp_path):
    """Default `include_globs=()` is "include everything" — back-compat."""
    src = tmp_path / "repo"
    (src / "crates").mkdir(parents=True)
    (src / "crates" / "a.rs").write_text("fn a() {}\n")
    (src / "crates" / "b.rs").write_text("fn b() {}\n")

    registry = _make_registry_for_rust()
    neo = FakeNeo4j()
    pipeline = IngestPipeline(registry, postgres=None, neo4j=neo, embedder=None)
    stats = pipeline.ingest_tree(src)
    assert stats.files_ingested == 2


def test_glob_match_double_star_matches_zero_or_more_segments():
    """`dir/**/*.md` must match both `dir/a.md` and `dir/sub/a.md`.

    Plain fnmatch fails the single-segment case because `**` becomes
    two `*` tokens that still require a `/` between them.
    """
    from kb_engine.ingest import _glob_match

    assert _glob_match("decisions/ADR-0000-charter.md", "decisions/**/*.md")
    assert _glob_match("decisions/nested/x.md", "decisions/**/*.md")
    assert not _glob_match("other/ADR.md", "decisions/**/*.md")
    assert _glob_match("vault/playbooks/governed-agent-memory.md", "vault/playbooks/**/*.md")
    assert _glob_match("kb-engine/kb_engine/chunker.py", "kb-engine/**/*.py")
    assert _glob_match(".cursor/scratchpad.md", ".cursor/**")
    assert _glob_match("pkg/__pycache__/x.pyc", "**/__pycache__/**")
