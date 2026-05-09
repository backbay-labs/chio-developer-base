# infra/

> **Status:** placeholder. The compose stack lands in **Phase 1.1** ([PLAN.md](../PLAN.md) phased delivery).

Docker Compose configuration and per-service bootstrap for the Phase 1+ stack.

## Planned layout

```
infra/
├── docker-compose.yml          ← four services: postgres, neo4j, graphiti-mcp, chio-kb-mcp
├── postgres/
│   └── init/
│       └── 001-vector.sql      ← creates the pgvector extension (mirrors PR #599)
└── graphiti/
    └── config.yaml             ← Graphiti MCP config; group_id = chio-repo

Per-pack Neo4j constraints live in pack code (chio_pack.plugin.chio_bootstrap_constraints
returns ConstraintSpec dataclasses); the engine's IngestPipeline.bootstrap()
collects every loaded pack's specs and applies them idempotently. There is
no longer a static infra/neo4j/constraints.cypher.
```

## Services

| Service | URL | Purpose |
| ------- | --- | ------- |
| `kb-postgres` (pgvector) | `localhost:55432` | Semantic code + docs vector tables under schema `chio_kb` |
| `kb-neo4j` | `http://localhost:7474` and `bolt://localhost:7687` | Chio property graph |
| `graphiti-mcp` | `http://localhost:8000/mcp` | Temporal episodic memory |
| `chio-kb-mcp` | `http://localhost:8111/mcp/` | Agent-facing MCP gateway with the 10 `kb_*` tools |

Defaults match PR #599 to ease the migration. The `.env.example` at the repo root documents all envs.

## Phase 1 acceptance

- `make kb-up` brings all four services up.
- Health endpoints respond within 60s on a fresh-cloned laptop (per PLAN.md "10-minute fresh-laptop onboarding").
- `make kb-smoke` lists the 10 `kb_*` tools without errors.
- `make kb-eval-retrieval` reports overall A on the 9 PR #599 categories.

## What does NOT belong here

- Eval fixtures or runners. Those are in [`chio-pack/eval/`](../chio-pack/eval/).
- Vault content. Vault is at [`vault/`](../vault/).
- Schema packs or domain code. Those are in [`chio-pack/`](../chio-pack/) (or future `<team>-pack/`).

## See also

- [PLAN.md](../PLAN.md#repo-layout) — the architecture diagram
- arc PR #599 (`codex/chio-kb-a-grade-dogfood`) — origin of the compose layout we're inheriting
