"""kb-engine — generic retrieval / graph / MCP framework.

Phase 1.2 deliverable. This module exposes the engine's public API: the
four plugin hooks that domain packs (chio-pack, and future <team>-pack)
implement against, plus the registry that loads and dispatches them.

There is **no Chio knowledge** in this package. Per PLAN.md and ADR-0003,
`kb_engine/` MUST NOT import anything `chio_*`. The boundary is enforced
at CI time by ops/ci/check-imports.py.

What's here today
-----------------
- The four plugin protocols (SourceIngester, GraphProjector,
  ToolRegistrar, FrontmatterHandler).
- A `Registry` that loads plugin classes by entry point or by direct
  registration in tests.
- Shared dataclasses for parsed files, graph nodes/edges, derived records.

What's NOT here yet (deferred to Phase 1.3+)
--------------------------------------------
- pgvector / Neo4j / Graphiti backing stores.
- The MCP server framework that ToolRegistrar hooks into.
- The CocoIndex ingestion pipeline.
- Any actual ranking or retrieval logic.

The engine today is the **boundary contract**. Functional ingestion lands
when Phase 1.3+ wires backing stores into the registered hooks.
"""
from .plugin import (
    FrontmatterHandler,
    GraphProjector,
    Registry,
    SourceIngester,
    ToolRegistrar,
)
from .types import (
    DerivedRecord,
    Edge,
    Node,
    ParsedFile,
    Symbol,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Plugin protocols
    "SourceIngester",
    "GraphProjector",
    "ToolRegistrar",
    "FrontmatterHandler",
    "Registry",
    # Types
    "ParsedFile",
    "Symbol",
    "Node",
    "Edge",
    "DerivedRecord",
]
