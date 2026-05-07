---
id: episode.chio-architecture-summary
type: episode-architecture-summary
status: imported
scope: chio-repo
title: "Chio architecture summary"
graphiti_episode_name: "Chio architecture summary"
source_description: "Curated seed for agent orientation in the Chio repository."
authoritative_files:
  - "spec/PROTOCOL.md"
  - "crates/chio-core-types/src/capability.rs"
  - "crates/chio-kernel/src/kernel/mod.rs"
  - "crates/chio-guards/src"
  - "crates/chio-policy/src"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/architecture-summary.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Chio architecture summary

Chio is a secure, attested tool access protocol. Agents are untrusted. The runtime kernel validates time-bounded capability tokens, runs guard and policy evaluation before tool calls cross trust boundaries, and signs append-only receipt records.

## Guidance

- Start with protocol and core type contracts before changing kernel behavior.
- Use kb_brief_feature for major work because it combines code, docs, tests, graph impact, memory, and validation commands.
- Repo files and current CI remain authoritative. The graph is retrieval support only.

<!-- HUMAN EDITS BELOW THIS LINE -->

> This file is hand-seeded to demonstrate the post-migration episode shape. Running `make kb-migrate-seeds` against arc on branch `codex/chio-kb-a-grade-dogfood` will overwrite this file and add a `seed_content_hash:` to the frontmatter (used by the migration script for idempotency). Any edits below this marker will be preserved across re-runs.
>
> The four worked specs that reference this episode by `graphiti-episode:` field:
> - [[../spec/capability-revocation]]
> - [[../spec/receipt-commitment]]
> - [[../spec/guard-pipeline]]
> - [[../spec/policy-compiler]]
