---
id: "episode.chio-agent-workflow-constraints"
type: "episode-workflow-constraint"
status: "imported"
scope: "chio-repo"
title: "Chio agent workflow constraints"
graphiti_episode_name: "Chio agent workflow constraints"
source_description: "Curated seed for local agent workflow constraints."
preferred_tools:
  - "kb_brief_feature"
  - "kb_search_code"
  - "kb_search_docs"
  - "kb_find_tests"
  - "kb_context"
  - "kb_impact"
imported_from: "../arc/ops/knowledge-base/seeds/graphiti/agent-workflow-constraints.json @ codex/chio-kb-a-grade-dogfood"
imported_at: "2026-05-09T02:53:49Z"
seed_content_hash: "sha256:e701aef9fabcb3bbe44a62fa1d46dd685d184589307055b3c69693e3d9de7e40"
---

# Chio agent workflow constraints

Agents using the local Chio KB should treat kb_brief_feature as orientation, then verify with repo files and local tests. The KB accelerates retrieval but never replaces source, CI, or release gates.

## Constraints

- Use focused validation commands from KB output before broad workspace gates.
- Cross-check graph results against code and docs when editing shared protocol behavior.
- If a brief reports coverage gaps, run targeted kb_search_code, kb_search_docs, and kb_find_tests queries before implementation.
- Do not feed raw source or bulk docs into Graphiti.

<!-- HUMAN EDITS BELOW THIS LINE -->

> Re-derived M0-D.3 from `../arc/ops/knowledge-base/seeds/graphiti/agent-workflow-constraints.json`. The `preferred_tools` body field is now mapped to typed-list frontmatter by [`migrate-seeds.py`](../../ops/scripts/migrate-seeds.py) (per the M0-D.3 extension), so the previous unmapped-body-fields JSON block produced by the migrator no longer renders here. The six-tool ordering (kb_brief_feature first, kb_search_code/docs second, kb_find_tests/context/impact third) reflects an orientation→specifics→cross-cutting cadence worth honoring.
>
> File renamed from `agent-workflow-constraints.md` → `chio-agent-workflow-constraints.md` to align with the slug derived from the seed's canonical name (`Chio agent workflow constraints`). No external backlinks reference the old path.
