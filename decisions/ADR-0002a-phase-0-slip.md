---
id: decisions.ADR-0002a
type: adr
status: accepted
date: 2026-07-08
date-accepted: 2026-07-08
title: "Phase 0 slip: continue carve-out with a 20-working-day credibility floor"
owners:
  - "@connor"
supersedes: []
related:
  - decisions.ADR-0000
  - decisions.ADR-0001
  - decisions.ADR-0002
---

# ADR-0002a — Phase 0 slip: continue with a credibility floor

- **Status:** Accepted
- **Date filed:** 2026-07-08
- **Date accepted:** 2026-07-08
- **Owners:** @connor
- **Related:** [ADR-0002](ADR-0002-phase-0-baselines.md), [ADR-0001](ADR-0001-repo-graduation.md), [ADR-0000](ADR-0000-charter.md)

## Context

[ADR-0002](ADR-0002-phase-0-baselines.md) was filed 2026-05-07 as the Phase 0 baseline-acceptance vehicle. Its own risk section requires:

> If `Date accepted` is more than 7 working days after `Date filed`, file a follow-up ADR explaining the slip and decide explicitly whether to continue or roll back.

As of 2026-07-08 that clock is ~43 working days overdue. ADR-0002 remains `pending` with all four baseline cells `TBD`. Meanwhile M0/M1 scaffolding landed (plugin protocol, `init-pack`, `sources.toml`, schema parameterization, ~312 unit tests), but the operational stack is still Phase 1.1: the MCP container is a health stub, all 10 `kb_*` tools return `status: stub`, and retrieval-A has never been re-measured on this tree.

Silence is the failure mode ADR-0002 warned against. This ADR closes that silence.

## Decision

**Continue the carve-out** (ADR-0001 Decision-A path), subject to a hard **20-working-day credibility floor** starting 2026-07-08 (deadline: **2026-08-05**).

Within that window the following must land:

1. **Wave 0 (this ADR + truth repair):** orphaned `crates/chio-receipts` references corrected to `crates/core/chio-core-types` / `chio-eval-receipt`; CI greps for the orphaned path.
2. **Wave 1 — Phase 1.3 real retrieval:** replace the MCP health stub; wire at least `kb_search_code`, `kb_search_docs`, and `kb_add_episode` to real stores; `make kb-eval-retrieval` produces a real grade on this tree.
3. **Wave 2 — Protocol extraction:** `VectorStore` + `Signer`/`Verifier` Protocols in `kb-engine`; synthetic `demo-pack` proves a second pack can cross the engine.

ADR-0002 itself remains the baseline-acceptance vehicle. Filling its table (Run-0 rater-A + outcome runners) is part of the floor, not a separate decision. If the floor slips past 2026-08-05 without Waves 1–2 binary acceptance, exercise [ADR-0001](ADR-0001-repo-graduation.md) Decision-B (roll back to arc-incubation) rather than filing another slip ADR.

## Why continue (not roll back)

- The engine/pack boundary, vault-sync daemon, and reusability scaffolding (`init-pack`, `sources.toml`, schema param) are real and would be expensive to re-derive inside arc.
- Arc still hosts the working A-grade stack at `tools/knowledge-base/`; the cutover lever (`KB_DIR`) is intact. Continuing does not orphan a production path.
- The failure mode is operational stubs, not architectural wrongness. Wiring tools is cheaper than undoing the carve-out.

## Consequences

- Ambitious bets (TurboVec promotion, signed-retrieval as a Chio-capability boot dependency, PR-impact gate as blocking, Governed Agent Memory) remain frozen until the credibility floor is green.
- ADR-0002's 7-working-day kill-switch is superseded for the slip question by this ADR's 20-working-day floor. Baseline *acceptance* still requires real numbers in ADR-0002's table.
- A CI check for orphaned `crates/chio-receipts` paths lands with this ADR so the vault/docs contract cannot silently re-drift.

## References

- [ADR-0002](ADR-0002-phase-0-baselines.md) — Phase 0 baselines (still pending numbers)
- [ADR-0001](ADR-0001-repo-graduation.md) — graduation / roll-back decision
- Consensus roadmap (2026-07-08 4-agent debate): credibility floor before moonshots
