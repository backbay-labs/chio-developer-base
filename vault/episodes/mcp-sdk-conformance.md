---
id: episode.mcp-sdk-conformance
type: episode-architecture-summary
status: imported
scope: chio-repo
title: "MCP SDK conformance orientation"
graphiti_episode_name: "MCP SDK conformance orientation"
source_description: "Curated seed for MCP adapter and SDK conformance work."
authoritative_files:
  - "crates/chio-mcp-adapter/src/lib.rs"
  - "crates/chio-mcp-adapter/src/transport.rs"
  - "crates/chio-mcp-edge/src/runtime.rs"
  - "docs/conformance/verdict-matrix.md"
  - "tests/conformance/README.md"
tests:
  - "integrations/mcp-adapter/tests/transport_round_trip.rs"
  - "integrations/mcp-adapter/tests/conformance_suite.rs"
  - "crates/chio-mcp-adapter/tests/integration_smoke.rs"
  - "crates/chio-conformance/verdict_matrix/tests/verdict_matrix_cross_language.rs"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/mcp-sdk-conformance.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# MCP SDK conformance orientation

MCP and SDK conformance work should connect adapter transport code, MCP edge runtime, integration tests, conformance peers, verdict matrix docs, and cross-language conformance tests.

## Constraints

- Graph traversal should suppress generic docs and empty-path dependency crates before ranking MCP context.
- Conformance peer docs are useful context but generated result directories are not canonical sources.
- Validation commands should prefer adapter, edge, and conformance package tests.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. Linked from [[../spec/sdk-conformance]] via the `graphiti-episode:` frontmatter field. Running `make kb-migrate-seeds` will overwrite this file's machine portion (preserving anything below the marker) and add a `seed_content_hash:` for idempotency.
