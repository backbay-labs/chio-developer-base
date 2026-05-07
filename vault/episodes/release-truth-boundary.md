---
id: episode.chio-release-truth-boundary
type: episode-workflow-constraint
status: imported
scope: chio-repo
title: "Chio release truth boundary"
graphiti_episode_name: "Chio release truth boundary"
source_description: "Curated seed for release and qualification work."
authoritative_files:
  - "docs/release/QUALIFICATION.md"
  - "docs/release/RELEASE_AUDIT.md"
  - "docs/conformance/verdict-matrix.md"
  - "tests/conformance/README.md"
  - "spec/COMPLIANCE-CERTIFICATE.md"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/release-truth-boundary.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Chio release truth boundary

Chio release claims must not outrun repo truth. Treat release docs, conformance fixtures, local gates, and current CI as release evidence. Marketing or roadmap language should remain behind actual qualification evidence.

## Constraints

- Do not treat the knowledge graph as a source of release truth.
- Do not promote GA claims without current qualification evidence.
- When hosted CI is unavailable, record local executor evidence explicitly.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. The first constraint is **load-bearing for the entire vault**: it's why [[../playbooks/release-qualification]] explicitly says "Do not infer release truth from Graphiti memory." The KB is a retrieval aid; the receipt log and conformance verdicts are the truth. Pairs with [[mercury-product-release-workflow]] (Mercury release ≠ protocol release).
