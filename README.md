# chio-developer-base

The dedicated knowledge base, vault, and developer-tooling stack for Chio — Backbay's capability-based agent runtime with signed receipts.

> **Status:** planning. The carve-out from `arc/ops/knowledge-base/` (PR #599) is scoped in [PLAN.md](PLAN.md). Phase 0 begins after [ADR-0000](decisions/ADR-0000-charter.md) is accepted.

## What this is

A three-layer stack:

- **`kb-engine/`** — generic retrieval / graph / MCP framework (pgvector + Neo4j + Graphiti). Zero Chio knowledge.
- **`chio-pack/`** — Chio schema, the 10 `kb_*` MCP tools, evals.
- **`vault/`** — git-versioned markdown that **is** the canonical store for episodes, ADRs, briefs, playbooks. Obsidian renders it; agents read it as files; Graphiti is derived from it.

Plus two ambitious bets unique to Chio:

- A **PR-time `kb_impact` gate** that fails PRs touching guards / policies / protocol contracts without acknowledging downstream blast radius.
- **Self-evidencing retrieval** — every `kb_search_*` returns a signed receipt. The KB demos the protocol it documents.

## Quickstart

> Phase 1 has not started. The sketch below is the target post-Phase-1 surface; nothing runs from this repo yet.

```sh
chio-dev up         # docker compose up + wait for health
chio-dev ingest     # incremental index of source repos + vault
chio-dev query "capability revocation receipt"
chio-dev eval       # retrieval + outcome evals
```

## Where to look

- [`PLAN.md`](PLAN.md) — full design, repo layout, phased delivery
- [`AGENTS.md`](AGENTS.md) — guidance for AI agents working in this repo
- [`CLAUDE.md`](CLAUDE.md) — Claude Code-specific notes
- [`decisions/`](decisions/) — ADRs (start at [ADR-0000](decisions/ADR-0000-charter.md))
- [`chio-pack/eval/PHASE-0.md`](chio-pack/eval/PHASE-0.md) — outcome evals that gate everything in Phases 1–4

## Origin and floor

Carved out of arc PR #599 (`codex/chio-kb-a-grade-dogfood`). The current A-grade retrieval eval (22/22 fixtures, p@5 ≥ 0.99, MRR ≥ 0.97, p95 < 1.5s) is the regression floor — no feature ships if it breaks.

## Workspace context

This repo lives inside the Backbay multi-repo workspace at `/Users/connor/Medica/backbay/standalone/chio-developer-base/`. The workspace root [CLAUDE.md](../../CLAUDE.md) is authoritative for cross-repo dev workflow (Moon, Bun, UV, cluster ports).
