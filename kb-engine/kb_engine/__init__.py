"""kb-engine — generic retrieval / graph / MCP framework.

Phase 1.3 surface. Exposes:

  - The four plugin protocols (SourceIngester, GraphProjector,
    ToolRegistrar, FrontmatterHandler).
  - A `Registry` that loads plugin classes by entry point or direct
    registration.
  - Shared dataclasses (ParsedFile, Symbol, Node, Edge, DerivedRecord).
  - `IngestPipeline` orchestrating Registry hooks against backing stores.
  - Backing stores under `kb_engine.store` (PostgresStore, Neo4jStore,
    Embedder + impls).

There is **no Chio knowledge** in this package. Per PLAN.md and
ADR-0003, `kb_engine/` MUST NOT import anything `chio_*`. The boundary
is enforced at CI time by `ops/ci/check-imports.py` and at unit-test
time by `chio-pack/tests/test_plugin.py::test_engine_does_not_import_chio_modules`.

Phase 1.4+ adds the vault-sync daemon and the real chunker (today's
ingest is "one chunk per file"). Phase 1.3+ wires the MCP server
framework that ToolRegistrar hooks into.
"""
from .ingest import IngestPipeline, IngestStats
from .plugin import (
    ConstraintProvider,
    FrontmatterHandler,
    GraphProjector,
    Registry,
    SourceIngester,
    ToolRegistrar,
)
from .types import (
    ConstraintKind,
    ConstraintSpec,
    DerivedRecord,
    Edge,
    Node,
    ParsedFile,
    Symbol,
)

__version__ = "0.2.0"

__all__ = [
    "__version__",
    # Plugin protocols
    "SourceIngester",
    "GraphProjector",
    "ToolRegistrar",
    "FrontmatterHandler",
    "ConstraintProvider",
    "Registry",
    # Types
    "ParsedFile",
    "Symbol",
    "Node",
    "Edge",
    "DerivedRecord",
    "ConstraintSpec",
    "ConstraintKind",
    # Pipeline
    "IngestPipeline",
    "IngestStats",
]
