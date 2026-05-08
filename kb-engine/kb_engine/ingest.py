"""Ingest pipeline. Glues plugin hooks to backing stores.

A pipeline run:

  1. For each file path under the configured source root:
     - Run Registry.ingest_file() — first matching plugin parses.
     - If a ParsedFile is produced:
       a. Run Registry.project_graph() to get nodes/edges.
       b. Optionally chunk + embed the text and write to PostgresStore.
       c. Write nodes + edges to Neo4jStore.

  2. Nodes are upserted before edges (referenced endpoints must exist).

  3. The pipeline is idempotent — re-running on the same input is safe
     (Cypher MERGE on Neo4j; pgvector inserts are append-only by design,
     so deduplication for code chunks is a chunker concern, not the
     pipeline's).

For Phase 1.3 the chunker is naive: one chunk per ParsedFile, the
chunk_text is parsed.text. Phase 1.4+ replaces with a real chunker
(splits long files, tracks symbol-aligned boundaries).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .plugin import Registry
from .store import Embedder, Neo4jStore, PostgresStore
from .store.postgres import CodeChunk
from .types import Edge, Node, ParsedFile


@dataclass
class IngestStats:
    files_seen: int = 0
    files_ingested: int = 0
    nodes_upserted: int = 0
    edges_upserted: int = 0
    chunks_inserted: int = 0


def _walk_source(source_root: Path) -> Iterable[Path]:
    """Yield candidate file paths. Skips dot-dirs and common cruft."""
    skip_names = {".git", ".obsidian", "node_modules", "target", ".venv",
                  "__pycache__", ".pytest_cache"}
    for dirpath, dirnames, filenames in os.walk(source_root):
        dirnames[:] = [d for d in dirnames if d not in skip_names]
        for fname in filenames:
            yield Path(dirpath) / fname


class IngestPipeline:
    """Orchestrates Registry hooks against backing stores."""

    def __init__(
        self,
        registry: Registry,
        *,
        postgres: PostgresStore | None = None,
        neo4j: Neo4jStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.registry = registry
        self.postgres = postgres
        self.neo4j = neo4j
        self.embedder = embedder

    def ingest_file(self, file_path: Path, source_root: Path) -> tuple[int, int, int]:
        """Run all hooks for a single file. Returns (n_nodes, n_edges, n_chunks)."""
        rel_path = str(file_path.relative_to(source_root))
        parsed = self.registry.ingest_file(rel_path)
        if parsed is None:
            return 0, 0, 0

        # Read the actual file text if the ingester didn't already
        if not parsed.text:
            try:
                parsed = ParsedFile(
                    path=parsed.path,
                    language=parsed.language,
                    text=file_path.read_text(encoding="utf-8", errors="replace"),
                    symbols=parsed.symbols,
                    properties=parsed.properties,
                )
            except OSError:
                # Binary file or unreadable; skip
                return 0, 0, 0

        graph_out = self.registry.project_graph(parsed)
        nodes = [x for x in graph_out if isinstance(x, Node)]
        edges = [x for x in graph_out if isinstance(x, Edge)]

        n_nodes = self.neo4j.upsert_nodes(nodes) if self.neo4j else 0
        n_edges = self.neo4j.upsert_edges(edges) if self.neo4j else 0

        n_chunks = 0
        if self.postgres and self.embedder and parsed.text:
            chunk = CodeChunk(
                file_path=parsed.path,
                source_root=str(source_root),
                language=parsed.language,
                line_start=1,
                line_end=parsed.text.count("\n") + 1,
                chunk_text=parsed.text,
                properties=dict(parsed.properties),
            )
            embeddings = self.embedder([chunk.chunk_text])
            n_chunks = self.postgres.insert_code_chunks([chunk], embeddings)

        return n_nodes, n_edges, n_chunks

    def ingest_tree(self, source_root: Path) -> IngestStats:
        """Walk source_root and ingest every recognized file. Returns aggregate stats."""
        stats = IngestStats()
        for path in _walk_source(source_root):
            stats.files_seen += 1
            n_nodes, n_edges, n_chunks = self.ingest_file(path, source_root)
            if n_nodes or n_edges or n_chunks:
                stats.files_ingested += 1
                stats.nodes_upserted += n_nodes
                stats.edges_upserted += n_edges
                stats.chunks_inserted += n_chunks
        return stats
