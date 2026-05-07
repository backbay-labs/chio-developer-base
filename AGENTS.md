# AGENTS.md — guidance for AI agents working in chio-developer-base

## Source of truth

[`PLAN.md`](PLAN.md) is canonical. Where this file and PLAN.md disagree, PLAN.md wins. Where ADRs in [`decisions/`](decisions/) supersede PLAN.md, the latest accepted ADR wins.

This repo carves out and expands the Chio knowledge base originally landed in arc PR #599 (`codex/chio-kb-a-grade-dogfood`).

## Architecture in 5 lines

1. **`kb-engine/`** — generic retrieval / graph / MCP. Zero Chio knowledge.
2. **`chio-pack/`** — Chio schema (`ChioCapability`, `ChioReceipt`, …), the 10 `kb_*` MCP tools, evals.
3. **`vault/`** — markdown + frontmatter, git-versioned, **canonical** for non-source knowledge.
4. **vault-sync daemon** — only writer to Graphiti. Graphiti is a derived index.
5. **MCP gateway on `:8111`** — exposes the `kb_*` tools. Phase 2: every response is wrapped in a signed retrieval receipt.

## Hard rules

- **Never write to Graphiti directly.** The vault-sync daemon is the only writer. To add an episode, write `vault/episodes/<id>.md` with valid frontmatter; the `kb_add_episode` tool does this for you.
- **Never duplicate code into the vault.** Source code lives in arc / platform / opus / etc. and is referenced by stable path + symbol. The vault holds curated non-source content only.
- **`kb-engine/` cannot import `chio_*`.** The boundary is enforced by `ops/ci/check-imports.py`. To extend the engine, register a plugin via `kb_engine.plugin` hooks (`SourceIngester`, `GraphProjector`, `ToolRegistrar`, `FrontmatterHandler`); don't leak Chio names into the engine.
- **Vault frontmatter is a contract.** Every note has `id`, `type`, `status`. See PLAN.md "Vault layout" for the full schema. Bad frontmatter fails CI.
- **Retrieval eval is the regression floor.** Overall A required across the 9 categories from PR #599. If `make kb-eval` drops below A on retrieval, revert; don't patch.
- **No new outcome eval ships without an ADR.** Outcome evals (Phase 0) define what "the carve-out works" means. Changing the targets is a real decision.

## The 10 MCP tools

`kb_search_code`, `kb_search_docs`, `kb_find_tests`, `kb_find_docs`, `kb_neighbors`, `kb_context`, `kb_impact`, `kb_brief_feature`, `kb_eval`, `kb_add_episode`. Filter shapes and `rank_components` semantics are in arc PR #599's README until migrated to `chio-pack/`.

## Where work belongs

| If you're … | Edit / write here |
| --- | --- |
| Fixing a retrieval ranking bug | `kb-engine/kb_engine/search/` |
| Adding a Chio-specific MCP tool | `chio-pack/chio_pack/tools/` and register via plugin |
| Adding / changing a Chio graph node or edge type | `chio-pack/chio_pack/schema.py` + ADR if user-visible |
| Writing a new spec, ADR, or episode | `vault/spec/`, `vault/decisions/`, `vault/episodes/` |
| Adjusting an eval target | `chio-pack/eval/outcomes.yml` + ADR |
| Touching the engine ↔ pack boundary | Always opens with an ADR |

## Phase awareness

The repo is in **Phase 0 (evals first)** until baselines for the four outcome evals in [`chio-pack/eval/PHASE-0.md`](chio-pack/eval/PHASE-0.md) are committed to `vault/_meta/dashboards/eval-outcomes.md`. Do not ship feature code that is not eval-gated.

## Workspace context

This repo lives at `/Users/connor/Medica/backbay/standalone/chio-developer-base/` inside the Backbay multi-repo workspace. The workspace root [`/Users/connor/Medica/backbay/CLAUDE.md`](../../CLAUDE.md) is authoritative for cross-repo dev workflow (Moon, Bun, UV, cluster ports). This file is authoritative for working *inside* this repo.

## Linked work in arc

- PR #599 `codex/chio-kb-a-grade-dogfood` — the origin stack. Will be replaced by a thin Make wrapper or submodule reference once Phase 1 lands.
- arc's `tests/conformance/` — source of truth for SDK conformance fixtures used by the `conformance-harness-recall` outcome eval.
- arc's `crates/chio-receipts/` — used by signed-retrieval verification (Phase 2).
