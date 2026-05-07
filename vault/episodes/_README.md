---
id: meta.episodes-readme
type: meta
---

# `vault/episodes/`

Curated temporal episodes that the vault-sync daemon (Phase 1) derives Graphiti episodes from.

## What goes here

- **Architecture summaries** — what's true at a point in time about a major system.
- **Planning decisions** — especially decisions *not* to do something.
- **Release notes** (the curated form, not the changelog).
- **Agent session notes** — only the load-bearing ones. Most session notes do not belong here.
- **PR repair summaries** — when a PR taught us something durable about Chio behavior.

## What does NOT go here

- Raw source code or excerpts. Source lives in arc / platform / opus and is referenced by stable path + symbol.
- One-off questions. Those go in [[../daily|daily notes]].
- Boilerplate or "history" that the git log already captures.
- API reference. Generated docs win; link out, don't duplicate.

## How to add an episode

1. Use the [[../_meta/templates/episode|episode template]].
2. Set `status: draft` while you're working.
3. Move to `status: accepted` only when the episode has been through the `episode-promoter` (Phase 3) confirmation flow OR a human reviewer has approved it.
4. Frontmatter `graphiti_episode_name` is the contract — the vault-sync daemon uses it as the Graphiti node identifier.

## How to remove an episode

You don't, generally — Graphiti is append-mostly. To deprecate an episode:

- Mark its frontmatter `status: superseded`.
- Add a `supersedes:` link from the new note that replaces it.
- The daemon respects `supersedes` and will route queries to the latest accepted node.

## Origin

Initial episodes are migrated from arc PR #599's `seeds/graphiti/*.json` via `make kb-migrate-seeds`. Migrated episodes carry frontmatter `imported_from:` for provenance and a `seed_content_hash:` so the migration script can detect drift on re-runs.
