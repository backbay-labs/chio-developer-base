---
id: episode.guard-policy-fail-closed
type: episode-workflow-constraint
status: imported
scope: chio-repo
title: "Guard policy fail-closed behavior"
graphiti_episode_name: "Guard policy fail-closed behavior"
source_description: "Curated seed for guard and policy implementation work."
authoritative_files:
  - "crates/chio-guards/src/pipeline.rs"
  - "crates/chio-guards/src/lib.rs"
  - "crates/chio-kernel/src/kernel/evaluator.rs"
  - "crates/chio-policy/src/validate.rs"
  - "crates/chio-policy/src/evaluate/engine.rs"
tests:
  - "crates/chio-guards/tests/integration.rs"
  - "crates/chio-guards/tests/output_sanitization.rs"
  - "crates/chio-policy/tests/compile_policy.rs"
  - "crates/chio-policy/tests/validate_boundary.rs"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/guard-policy-fail-closed.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Guard policy fail-closed behavior

Guard and policy work should route through native guard pipeline behavior, policy validation and compiler code, and fail-closed tests. Guard denial and redaction evidence must remain connected to receipt and conformance surfaces.

## Constraints

- Invalid policies reject at load time.
- Guard and policy errors deny access.
- Agents should inspect both runtime evaluator code and policy compiler code before changing guard semantics.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. Shared lineage between [[../spec/guard-pipeline]] and [[../spec/policy-compiler]] — both worked specs reference this episode by `graphiti-episode:` field because the fail-closed obligation runs across both surfaces. Running `make kb-migrate-seeds` will overwrite this file's machine portion (preserving anything below the marker) and add a `seed_content_hash:` for idempotency.
