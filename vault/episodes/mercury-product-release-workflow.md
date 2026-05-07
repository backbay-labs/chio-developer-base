---
id: episode.mercury-product-release-workflow
type: episode-architecture-summary
status: imported
scope: chio-repo
title: "Mercury product release workflow"
graphiti_episode_name: "Mercury product release workflow"
source_description: "Curated seed for Mercury product release, assurance, and renewal work."
authoritative_files:
  - "docs/mercury/README.md"
  - "docs/mercury/RELEASE_READINESS.md"
  - "docs/mercury/ASSURANCE_SUITE.md"
  - "docs/mercury/RENEWAL_QUALIFICATION.md"
  - "crates/chio-mercury/src/commands/assurance_release.rs"
  - "crates/chio-mercury/src/commands/renewal_qualification_lane.rs"
  - "crates/chio-mercury-core/src/release_readiness.rs"
  - "crates/chio-mercury-core/src/assurance_suite.rs"
tests:
  - "crates/chio-mercury/tests/cli.rs"
  - "crates/chio-mercury-core/tests/integration_smoke.rs"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/mercury-product-release-workflow.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Mercury product release workflow

Mercury product release work should stay distinct from protocol release qualification. Agents should orient through Mercury docs, Mercury command lanes, Mercury core package fixtures, and the Mercury CLI smoke tests before editing product release or renewal workflows.

## Constraints

- Do not use Mercury product release evidence as proof for protocol release qualification.
- For Mercury renewal work, prefer docs/mercury/RENEWAL_QUALIFICATION.md and renewal_qualification_lane.rs.
- For Mercury assurance work, prefer docs/mercury/ASSURANCE_SUITE.md and assurance_release.rs.
- Keep Mercury product context out of compliance certificate briefs unless Mercury is explicitly requested.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. Mercury is a Chio product that ships ON TOP of the Chio protocol, but its release workflow is intentionally separate from [[../playbooks/release-qualification|protocol release qualification]]. The first constraint here is the load-bearing one: Mercury evidence cannot prove protocol qualification — they're separate audit chains. Pairs with [[release-truth-boundary]].
