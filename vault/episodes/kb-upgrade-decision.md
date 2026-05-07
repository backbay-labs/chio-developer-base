---
id: episode.a-grade-local-kb-upgrade-decision
type: episode-architecture-decision
status: imported
scope: chio-repo
title: "A-grade local KB upgrade decision"
graphiti_episode_name: "A-grade local KB upgrade decision"
source_description: "Curated seed for the local knowledge-base upgrade."
validation:
  - "make kb-reset"
  - "make kb-reseed"
  - "make kb-eval"
  - "make kb-dogfood"
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/kb-upgrade-decision.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# A-grade local KB upgrade decision

The local Chio KB keeps OpenAI embeddings as the default, uses deterministic Postgres vector ingestion for code and docs, uses deterministic Neo4j seeding for Chio graph facts, and reserves Graphiti for curated temporal episodes.

## Decisions

- Normalize all paths before classification so Docker /workspace paths, absolute checkout paths, and repo-relative paths map to the same metadata.
- Keep bulk source and docs out of Graphiti. Seed only architecture summaries, decisions, release gates, repair summaries, and workflow constraints.
- Prefer scoped concept nodes such as capability:kernel-validation and guard:pipeline over broad global concept hubs during graph traversal.
- Use fixed dogfood fixtures to gate retrieval quality before calling the KB A-grade.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. This episode is the architectural-decision counterpart to [[chio-architecture-summary]] — where the architecture-summary describes WHAT the KB is, this one describes the load-bearing CHOICES that produced it. Specifically the deliberately narrow Graphiti policy (curated episodes only, never raw source) and the path-normalization rule that lets Docker bind-mount paths and host-checkout paths share metadata.
