# CLAUDE.md — Claude Code in chio-developer-base

[`AGENTS.md`](AGENTS.md) covers the rules that apply to all agents here. Read it first.

## Claude-specific notes

- Source of truth is [`PLAN.md`](PLAN.md). Don't duplicate its contents in CLAUDE.md.
- The Backbay workspace root has its own [CLAUDE.md](../../CLAUDE.md) covering Moon, Bun, UV, and cluster ports — read that for cross-repo workflow questions.
- This repo's eval suite (`make kb-eval`) is the canonical regression gate. Run it before claiming a change is done.
- For multi-step refactors that span the engine/pack boundary, prefer `/gsd:plan-phase` over ad-hoc TodoWrite — the engine/pack split needs structured planning to stay clean.

## Don't

- Don't run `make kb-reset` without explicit user confirmation. It drops Postgres tables and clears Neo4j Chio nodes.
- Don't add Obsidian community plugins outside the pinned set in `.obsidian/community-plugins.json`. Plugin choices are an ADR-level decision.
- Don't write directly to `vault/decisions/ADR-*.md` to mark `Accepted`. Acceptance happens via PR review with the ADR's named owners.
- Don't add new top-level vault folders. The 7 in PLAN.md (`_meta/`, `spec/`, `crates/`, `decisions/`, `episodes/`, `playbooks/`, `daily/`) are fixed. An eighth requires an ADR.
