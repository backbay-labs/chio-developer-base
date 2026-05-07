# kb-engine/

> **Status:** Phase 1.2 contract surface landed (commit [`0f275da`+](https://github.com/backbay-labs/chio-developer-base/commits/main/kb-engine/)). The four plugin protocols + registry exist and are tested. Backing stores (pgvector / Neo4j / Graphiti / MCP server framework) are Phase 1.3+.

The generic retrieval / graph / MCP framework. **Zero Chio knowledge.**

## Boundary contract

This package MUST NOT import anything from `chio_pack` or any other domain pack. The boundary is enforced by [`ops/ci/check-imports.py`](../ops/ci/check-imports.py) and stated in [`AGENTS.md`](../AGENTS.md#hard-rules) hard rule #3.

If `kb_engine/` ever needs Chio-specific behavior, the answer is to **register a plugin** via the four hooks below — never to leak Chio names into the engine.

## Current layout (Phase 1.2)

```
kb-engine/
├── pyproject.toml
├── kb_engine/
│   ├── __init__.py              ← public API (protocols + types)
│   ├── plugin.py                ← the four hook protocols + Registry
│   └── types.py                 ← ParsedFile, Symbol, Node, Edge, DerivedRecord
└── tests/
    └── test_plugin.py           ← Registry dispatch, hook protocol conformance
```

## Planned (Phase 1.3+)

```
kb_engine/
├── ingest/
│   ├── code.py                  CocoIndex hooks for source repos
│   ├── docs.py                  CocoIndex hooks for docs/specs
│   └── vault.py                 frontmatter parser; emits pgvector + graphiti
├── graph/                       Neo4j projector framework (schema-pack pluggable)
├── search/                      ranker, filters, rank_components emission
├── mcp/                         MCP server framework, tool registrar
└── receipt/                     signed-retrieval envelope (Phase 2B)
```

## The four plugin hooks

A schema pack (`chio-pack`, future `<team>-pack`) registers any subset of:

| Hook | Signature | What it does |
| ---- | --------- | ------------ |
| `SourceIngester` | `(file_path) -> Optional[ParsedFile]` | Decide if/how to index a file. Chio-pack's `chio_pack/projectors/rust.py` is one. |
| `GraphProjector` | `(parsed) -> Iterable[NodeOrEdge]` | Take parsed AST/symbols; emit nodes + edges using your pack's vocabulary. |
| `ToolRegistrar` | `(server) -> None` | Declare new MCP tools on the gateway (chio-pack's `kb_brief_feature` registers here). |
| `FrontmatterHandler` | `(type, frontmatter) -> Iterable[DerivedRecord]` | Interpret a vault note's `type:` value to decide what derived store(s) to write. |

A plugin is a Python package implementing any subset. **No fork, no monkey-patch.**

## What does NOT belong here

- Chio-specific node labels (`Chio*`).
- Domain-specific MCP tools (`kb_brief_feature`, `kb_impact`'s Chio-flavored ranking).
- The 9 retrieval eval categories (those move into `chio-pack/eval/retrieval.yml`).
- Anything that knows about capabilities, receipts, guards, policies, or protocols.

## See also

- [PLAN.md](../PLAN.md#the-kb-engine--chio-pack-boundary) — the boundary section
- [AGENTS.md](../AGENTS.md#hard-rules) — the import rule
- [`chio-pack/`](../chio-pack/) — the reference pack implementing all four hooks
