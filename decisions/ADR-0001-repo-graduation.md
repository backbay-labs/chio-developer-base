---
id: decisions.ADR-0001
type: adr
status: proposed
date: 2026-05-07
date-decision: TBD
title: "Repo graduation: standalone vs. arc submodule"
owners:
  - "@connor"
supersedes: []
related:
  - decisions.ADR-0000
---

# ADR-0001 — Repo graduation: standalone vs. arc submodule

- **Status:** Proposed (decision deferred to Phase 4 review)
- **Date filed:** 2026-05-07
- **Decision date:** TBD (Phase 4 milestone, ~week 10 from charter)
- **Owners:** @connor
- **Related:** [ADR-0000 (charter)](ADR-0000-charter.md)

## Context

ADR-0000 commits to a standalone repo from day one. The skeptic position from the brainstorm — that two-repo coordination is expensive for a single-maintainer + agent-fleet team and that the carve-out should be deferred until a second adopter exists — has merit and should be revisited explicitly rather than allowed to drift into a permanent default.

This ADR establishes the criteria and the review milestone for that revisit.

## Decision

At the end of Phase 4 (target: week 10 from charter acceptance), evaluate the standalone-repo decision against the criteria below. Choose one of three outcomes:

- **A. Graduate.** Continue as a fully standalone repo. arc imports via submodule or a thin Make wrapper. Other adopters (platform, opus, alpha) onboard via the second-adopter playbook.
- **B. Rollback.** Move `chio-developer-base/` back into `arc/ops/knowledge-base/` (or `arc/ops/chio-developer-base/`) as a directory inside arc. Preserve the engine/pack split as a code-organization convention; drop the cross-repo coordination cost. The vault stays git-versioned inside arc.
- **C. Hold.** Keep standalone but defer further investment in the engine/pack productization (e.g., do not ship a public plugin loader) until a real second adopter signs up.

## Decision criteria (graded at Phase 4 review)

| Criterion | A (Graduate) | B (Rollback) | C (Hold) |
| --- | --- | --- | --- |
| **Second adopter committed?** | Yes (platform / opus / alpha lead has signed up with working code by week 10) | No, and none likely within next quarter | No, but plausible interest |
| **Two-repo coord cost (hr/mo)** | < 4 hr/mo measured | > 8 hr/mo measured | 4–8 hr/mo |
| **Retrieval eval regressions since carve-out** | 0 caused by repo-split version skew | ≥ 1 caused by repo-split version skew | 0–1 |
| **Outcome evals (Phase 0) baselined and improving** | Yes, with ≥ 2 categories trending up vs. baseline | No, or trending flat / down | Partial |
| **Maintenance hours / mo (estimated)** | < 20 hr/mo | > 30 hr/mo | 20–30 hr/mo |

If 3+ rows favor a single column, that column wins. Otherwise the decision goes to a structured review session with named stakeholders, recorded as ADR-00XX.

## Consequences

**Positive**

- Forces an explicit revisit instead of letting "we already started standalone" become an accidental commitment.
- Gives the skeptic position a defined, time-bounded fair hearing.
- Provides a clean rollback path that doesn't lose work — the engine/pack split is valuable as code organization regardless of repo topology.

**Negative**

- Adds a Phase 4 ceremony cost (~half a day for the review).
- A rollback at week 10 means re-doing CI wiring and any external links / submodules. Mitigation: keep external integrations behind the `chio-dev` CLI surface so they survive a repo move.

## Open questions

- Does "second adopter committed" require working code, or a verbal commitment? **Default: a working `chio-dev ingest --pack <other>` against a real cluster repo by Phase 4 review.** Verbal commitments without code do not count.
- If outcome **C ("Hold")** is chosen, what's the next review milestone? **Default: Phase 4 + 8 weeks**, recorded as ADR-00XX at the time.
- What metric source for "two-repo coord cost"? **Default: count of PRs requiring synchronized merges across arc and chio-developer-base × 30 minutes per PR**, plus measured CI wait time on cross-repo updates. Logged in `vault/_meta/dashboards/coordination-cost.md`.

## References

- [ADR-0000](ADR-0000-charter.md)
- [PLAN.md](../PLAN.md) — section "Open decisions / risks", item 1
- Skeptic position: PLAN.md "Non-goals" rationale and the brainstorm synthesis archive
