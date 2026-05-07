---
id: episode.chio-agent-workflow-constraints
type: episode-workflow-constraint
status: imported
scope: chio-repo
title: "Chio agent workflow constraints"
graphiti_episode_name: "Chio agent workflow constraints"
source_description: "Curated seed for local agent workflow constraints."
imported_from: "(hand-seeded for v0.0.0-scaffold; will be overwritten by `make kb-migrate-seeds` against arc PR #599 seeds/graphiti/agent-workflow-constraints.json)"
imported_at: "2026-05-07T00:00:00Z"
---

# Chio agent workflow constraints

Agents using the local Chio KB should treat kb_brief_feature as orientation, then verify with repo files and local tests. The KB accelerates retrieval but never replaces source, CI, or release gates.

## Constraints

- Use focused validation commands from KB output before broad workspace gates.
- Cross-check graph results against code and docs when editing shared protocol behavior.
- If a brief reports coverage gaps, run targeted kb_search_code, kb_search_docs, and kb_find_tests queries before implementation.
- Do not feed raw source or bulk docs into Graphiti.

## Unmapped body fields (review)

```json
{
  "preferred_tools": [
    "kb_brief_feature",
    "kb_search_code",
    "kb_search_docs",
    "kb_find_tests",
    "kb_context",
    "kb_impact"
  ]
}
```

<!-- HUMAN EDITS BELOW THIS LINE -->

> Hand-seeded for v0.0.0-scaffold. The `preferred_tools` field is unmapped because [`migrate-seeds.py`](../../ops/scripts/migrate-seeds.py) doesn't currently recognize it as either a typed-list (alongside `authoritative_files`/`tests`/`validation`) or a prose section (alongside `constraints`/`decisions`). It surfaces in an "Unmapped body fields (review)" section as a JSON block — exactly what the script will produce when run against the real seed. The four-tool ordering (kb_brief_feature first, kb_search_code/docs second, kb_find_tests/context/impact third) reflects an orientation→specifics→cross-cutting cadence worth honoring.
