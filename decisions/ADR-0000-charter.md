# ADR-0000 — Charter: chio-developer-base

- **Status:** Accepted
- **Date:** 2026-05-07
- **Owners:** @connor
- **Supersedes:** —
- **Superseded by:** —

## Context

The arc repo's PR #599 (`codex/chio-kb-a-grade-dogfood`) shipped a working local KB stack for Chio: pgvector + Neo4j + Graphiti MCP + a Python MCP gateway exposing 10 retrieval/graph tools, with an A-grade dogfood eval (22/22 fixtures, p@5 ≥ 0.99, MRR ≥ 0.97, p95 < 1.5s).

It works, but it conflates three things that want to be separated:

1. A generic retrieval engine (pgvector + Neo4j + ranker + MCP framework).
2. A Chio-specific schema and tool set (`ChioCapability`, `ChioReceipt`, the 10 `kb_*` tools, evals).
3. A knowledge surface (today: JSON Graphiti seeds; tomorrow: a vault for humans + agents).

Without separating these, the codebase will calcify around Chio assumptions inside what should be a reusable engine, and the vault question will be answered by accident rather than by design.

A four-agent brainstorm (architect, Obsidian/UX, moonshot, skeptic) produced [PLAN.md](../PLAN.md), which proposes a tri-layer architecture, a vault-as-canonical inversion, two Chio-specific moonshots, and an evals-first phasing.

## Decision

Adopt PLAN.md as the design for `chio-developer-base`. Specifically commit to:

1. **Three-layer split.** `kb-engine/` (generic) + `chio-pack/` (Chio) + `vault/` (canonical). Engine cannot import `chio_*`; enforced in CI.
2. **Vault as canonical store** for episodes, ADRs, briefs, playbooks. Graphiti is a derived index. The vault-sync daemon is the only writer to Graphiti. Migrate `seeds/graphiti/*.json` from PR #599 into `vault/episodes/*.md` with frontmatter.
3. **Two moonshots in v1.** PR-time `kb_impact` gate, and self-evidencing retrieval. Both must pass dedicated evals before they merge their first feature commit.
4. **Evals-first phasing.** Phase 0 ships outcome evals (`time-to-first-correct-fix`, `repeated-mistake-rate`, `conformance-harness-recall`, `capability-error-explanation`) *before* any new feature. PR #599's retrieval eval (overall A across 9 categories) is the regression floor.
5. **No federation, no resident agent, no auto-ADRs in v1.** See PLAN.md "Non-goals."
6. **Standalone repo from day one, with a graduation review at Phase 4.** The decision to stay standalone vs. roll back to an arc subdirectory is gated by [ADR-0001](ADR-0001-repo-graduation.md).

## Consequences

**Positive**

- Engine becomes reusable for platform / opus / alpha without forking.
- Vault provides a single, git-versioned, agent- and human-readable knowledge surface.
- Outcome evals make every later claim of "the KB helps" falsifiable.
- The two moonshots are Chio-specific and earn their complexity by dogfooding the protocol Chio ships.

**Negative**

- Standalone repo introduces two-repo coordination cost between arc and chio-developer-base. Mitigated by ADR-0001's graduation review at Phase 4.
- Vault inversion (vault → graphiti) is load-bearing; if the daemon's idempotency is wrong, episodes can be lost. Mitigation: every episode has a content hash; the daemon refuses overwrites on mismatch without `--force`.
- Maintenance footprint grows (Postgres + Neo4j + Graphiti + MCP gateway + Obsidian plugin set). Outcome evals must justify the additional surface.
- Phase 0 spends ~1 week on evals before producing user-visible features. Required cost of disciplined design.

## Alternatives considered

- **Incubate inside `arc/ops/knowledge-base/` until a second adopter exists.** Lower coordination cost, lower ambition. Rejected for now but explicitly preserved as a fallback in ADR-0001 — Phase 4 graduation review may flip back to this.
- **Keep PR #599's `seeds/graphiti/*.json` as canonical, treat the vault as a UI layer.** Rejected: gives two truths and a sync nightmare. The architect agent's argument carried.
- **Build all 7 moonshots from the brainstorm.** Rejected: maintenance math doesn't survive single-maintainer + agent-fleet operation. PLAN cuts to two.
- **Skip the vault entirely; let Cursor / Claude Code be the only knowledge surface.** Rejected because it loses the git-versioned, reviewable knowledge artifact that the protocol-grade ambitions of Chio deserve. The skeptic's vault-as-museum risk is real and is mitigated by (a) the vault holding only curated non-source content, and (b) outcome evals catching staleness within 30 days.

## References

- [PLAN.md](../PLAN.md)
- [ADR-0001 — Repo graduation](ADR-0001-repo-graduation.md)
- arc PR #599: `codex/chio-kb-a-grade-dogfood`
- Brainstorm synthesis: PLAN.md "Two moonshots" and "Non-goals" sections

## Acceptance

This ADR is accepted by @connor on 2026-05-07. Phase 0 may begin once the four outcome-eval definitions in [`chio-pack/eval/PHASE-0.md`](../chio-pack/eval/PHASE-0.md) are reviewed and signed off (an explicit comment on this ADR's PR is sufficient).
