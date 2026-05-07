---
id: episode.capability-revocation-architecture
type: episode-architecture-summary
status: imported
scope: chio-repo
title: "Capability revocation architecture"
graphiti_episode_name: "Capability revocation architecture"
source_description: "Curated seed for capability revocation feature work."
authoritative_files:
  - "crates/chio-kernel/src/kernel/delegation.rs"
  - "crates/chio-kernel/src/revocation_store.rs"
  - "crates/chio-core-types/src/capability.rs"
  - "crates/chio-kernel-core/src/capability_verify.rs"
  - "spec/PROTOCOL.md"
tests:
  - "crates/chio-revocation-oracle/tests/swarm_revocation_e2e.rs"
  - "crates/chio-revocation-oracle/tests/receipt_chain_proof.rs"
  - "crates/chio-revocation-oracle/tests/property_oracle.rs"
  - "crates/chio-kernel-core/tests/revocation_view_concurrency.rs"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/capability-revocation-architecture.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Capability revocation architecture

Capability revocation work starts in kernel delegation and revocation stores, checks core capability token and grant semantics, and validates behavior through revocation-oracle plus kernel/core tests.

## Constraints

- Treat revocation as part of capability validation and receipt evidence, not an isolated product feature.
- Prefer revocation-oracle tests before broad semantic test matches when the query includes revocation.
- Do not infer release truth from Graphiti memory.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. Linked from [[../spec/capability-revocation]] via the `graphiti-episode:` frontmatter field. Running `make kb-migrate-seeds` will overwrite this file's machine portion (preserving anything below the marker) and add a `seed_content_hash:` for idempotency.
