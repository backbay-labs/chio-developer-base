---
id: meta.moc
type: meta
---

# Map of content

> One-page entry to the vault. Bookmarked under **Start here**. Update whenever a new top-level area is added.

## Start here

- [[../playbooks/onboard-a-chio-developer|Day 1 onboarding]] — first thing to read if you're new
- [README.md](../../README.md) — quickstart for the whole repo
- [PLAN.md](../../PLAN.md) — full design doc
- [AGENTS.md](../../AGENTS.md) — the five hard rules

## Daily

- [[templates/daily-note]] — what gets created when you press `Cmd+N` in `vault/daily/`
- [[queries/stale-specs]] — specs >90 days unvalidated (org-wide)
- [[queries/open-adrs]] — ADRs in `proposed` status
- [[queries/unowned-capabilities]] — accepted spec nodes with no `owners:`
- [[dashboards/eval-outcomes]] — outcome-eval status (auto-generated)

## Specs (the canonical Chio concepts)

- [[../spec/_README|spec/]] — folder overview + how to add one
- [[../spec/capability-revocation]] — Capability node, the worked example
- [[../spec/receipt-commitment]] — Receipt node, the Merkle commitment chain
- [[../spec/guard-pipeline]] — Guard node, the fail-closed pipeline

## Playbooks

- [[../playbooks/onboard-a-chio-developer]] — Day 1 (also in Start here)
- [[../playbooks/release-qualification]] — cut a release
- [[../playbooks/revoke-a-capability]] — revoke a capability
- [[../playbooks/adopt-chio-developer-base]] — adopt this stack for your repo

## Decisions

- [ADR-0000 — charter](../../decisions/ADR-0000-charter.md) (Accepted)
- [ADR-0001 — repo graduation](../../decisions/ADR-0001-repo-graduation.md) (Proposed)
- [ADR-0002 — Phase-0 baselines](../../decisions/ADR-0002-phase-0-baselines.md) (Pending)

> ADRs live at `decisions/` (repo root), one level above this vault. Click-throughs work in Obsidian as regular file links; wikilinks would require the vault root to be the repo root (see [open question on vault layout](#open-questions)).

## Episodes (Graphiti seeds + promoted)

- [[../episodes/_README|episodes/]] — folder overview + how to promote
- *(individual episodes appear after `make kb-migrate-seeds` — see [migrate-seeds.py](../../ops/scripts/migrate-seeds.py))*

## Eval & raters

- [PHASE-0.md](../../chio-pack/eval/PHASE-0.md) — the four outcome evals defined
- [RATERS.md](../../chio-pack/eval/RATERS.md) — who scores Eval 4
- [rubrics.md](../../chio-pack/eval/rubrics.md) — how scores are assigned
- [[dashboards/rater-calibration]] — drift over time
- [[dashboards/eval-outcomes]] — current eval status

## Templates

- [[templates/daily-note]] — Templater + Periodic Notes scaffold
- [[templates/spec]] — for new normative spec notes
- [[templates/adr]] — for new ADRs
- [[templates/episode]] — for new Graphiti episode candidates
- [[templates/playbook]] — for new operational runbooks

## Diagrams (placeholders — open in Excalidraw)

- [[diagrams/capability-lifecycle]]
- [[diagrams/receipt-commitment-chain]]
- [[diagrams/release-qualification-flow]]

New Excalidraw drawings save to `vault/_meta/diagrams/` by default — see [`vault/.obsidian/plugins/obsidian-excalidraw-plugin/data.json`](../.obsidian/plugins/obsidian-excalidraw-plugin/data.json).

## Recently active vault notes

```dataview
TABLE WITHOUT ID
  file.link as Note,
  file.mtime as Edited
FROM "vault/spec" OR "vault/playbooks" OR "vault/episodes"
WHERE file.mtime >= date(today) - dur(14 days)
SORT file.mtime DESC
LIMIT 10
```

## Open questions

- **Vault layout: vault root vs. repo root.** Today the Obsidian vault root is `vault/`, and repo-root files (PLAN, AGENTS, decisions/) need to be linked as plain markdown rather than wikilinks. The alternative — making the *repo root* the Obsidian vault root — would let everything be wikilinked, at the cost of `chio-pack/`, `kb-engine/`, etc. appearing in the Obsidian file explorer. No ADR yet; flagged here so the question is visible.
