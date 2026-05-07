---
id: decisions.ADR-0003
type: adr
status: accepted
date: 2026-05-07
title: "Vault root is the repo root"
owners:
  - "@connor"
supersedes: []
---

# ADR-0003 — Vault root is the repo root

- **Status:** Accepted
- **Date:** 2026-05-07
- **Owners:** @connor
- **Supersedes:** —
- **Related:** [PLAN.md](../PLAN.md) repo layout, [`vault/_meta/MOC.md`](../vault/_meta/MOC.md) "Open questions"

## Context

The original [PLAN.md](../PLAN.md) described two parallel structures:

- `decisions/` at **repo root** (where ADRs actually live).
- `vault/` as a **subfolder** for curated knowledge (spec, episodes, playbooks, daily, _meta).

The Obsidian config was placed at `vault/.obsidian/` on the implicit assumption that `vault/` would be the Obsidian vault root. That choice has a real cost:

- Wikilinks from vault notes to ADRs (e.g., `[[../decisions/ADR-0000-charter]]`) traverse out of the vault. Obsidian wikilinks resolve by filename across the whole vault, so they happen to work, but the `../` prefix is misleading and brittle.
- The graph view and bookmarks couldn't reach repo-root files (PLAN.md, README.md, ADRs).
- Plain-markdown links like `[PLAN.md](../../PLAN.md)` work but feel like a workaround.

The MOC introduced in [`18bbf93`](https://github.com/backbay-labs/chio-developer-base/commit/18bbf93) explicitly flagged this as an open question. The bookmarks file committed in the same change implicitly answered it — its paths assumed vault root = repo root.

## Decision

**The Obsidian vault root is the repo root** (`chio-developer-base/`).

Specifically:

1. `.obsidian/` lives at the repo root, not under `vault/.obsidian/`.
2. Plugin configs that take vault-relative paths use `vault/<subdir>` (e.g., the Templater `templates_folder` is `vault/_meta/templates`).
3. The folder named `vault/` is **historical**: it predates this decision and continues to hold the bulk of curated knowledge. It is no longer the Obsidian vault root.
4. Wikilinks across the boundary (`[[ADR-0000-charter]]`, `[[capability-revocation]]`) work uniformly. Path-prefix forms like `[[../decisions/...]]` are obsolete cosmetic noise; they still resolve via Obsidian's filename matcher and are worth cleaning up over time but don't have to be removed in one pass.

## Consequences

**Positive**

- Wikilinks work uniformly across the entire repo.
- The Obsidian graph view captures ADRs, PLAN.md, AGENTS.md alongside vault notes.
- Bookmarks (already authored in this state) are now consistent with the rest of the config.
- Single-folder onboarding: "Open `chio-developer-base/` in Obsidian" is the only setup instruction.

**Negative**

- Obsidian's file explorer now shows `chio-pack/`, `kb-engine/`, `chio-pr-gate/`, `infra/`, `ops/`, `.github/` etc. alongside `vault/`. These contain code and config, not notes. Users can collapse them visually but can't hide them via committed config (the "Excluded files" list lives in `app.json`, which is per-user and gitignored).
- The folder name `vault/` is now slightly misleading — it's a subfolder of the (now-larger) Obsidian vault, not the vault root itself.
- Renaming `vault/` to something more accurate (`kb/`, `notes/`, or spreading its contents at repo root) would be a larger refactor. Out of scope for this ADR.

## Alternatives considered

1. **Keep vault root at `vault/`; move `decisions/` into `vault/decisions/`.** Would have made the vault self-contained without the repo-root flip. Rejected: ADRs are referenced by *many* paths from outside the vault (Makefile, CODEOWNERS, top-level docs); rewriting all of them is at least as disruptive as moving `.obsidian/`. PLAN.md, README.md, AGENTS.md would still be outside the vault.
2. **Spread `vault/` contents at repo root.** No vault subfolder at all — `spec/`, `episodes/`, etc. directly at repo root. Most "structurally clean" but would touch hundreds of references throughout the repo and bookmarks/snippets/queries that already exist. Out of scope.
3. **Keep the status quo and document that wikilinks-across-boundaries don't work.** Rejected: the bookmarks file already implicitly committed to vault-root-equals-repo-root, and the MOC flagged this as a question to resolve, not live with.

## Migration

Performed in the commit that lands this ADR:

- Move `vault/.obsidian/` → `.obsidian/` at repo root.
- Update plugin configs that take vault-relative paths:
  - `templater-obsidian/data.json` (`templates_folder`, `user_scripts_folder`, `folder_templates`)
  - `periodic-notes/data.json` (`daily.folder`, `daily.template`)
  - `obsidian-icon-folder/data.json` (folder paths get `vault/` prefix; `decisions` already at repo root)
  - `obsidian-excalidraw-plugin/data.json` (`folder`)
  - `episode-promoter/src/main.ts` (`DEFAULT_SETTINGS.episodesFolder`, `isDailyNote` check)
- Update `.gitignore` patterns to use `.obsidian/...` instead of `vault/.obsidian/...`.
- Update PLAN.md, CLAUDE.md, CONTRIBUTING.md, MOC.md, episode-promoter/README.md, onboard playbook to reference the new path.
- Wikilinks already authored across vault notes continue to work; cosmetic cleanup of `[[../...]]` prefixes is a nice-to-have, not required by this ADR.

## References

- [PLAN.md](../PLAN.md) — repo layout
- [`vault/_meta/MOC.md`](../vault/_meta/MOC.md) — "Open Questions" section that flagged this
- [`vault/.obsidian/bookmarks.json`](../vault/.obsidian/bookmarks.json) (pre-migration path; will move to `.obsidian/bookmarks.json`) — implicitly assumed this resolution
- [ADR-0000](ADR-0000-charter.md) — original charter
