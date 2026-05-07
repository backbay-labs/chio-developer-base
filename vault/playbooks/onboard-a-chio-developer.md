---
id: playbooks.onboard-a-chio-developer
type: playbook
status: draft
owners: []
last-validated: 2026-05-07
---

# Onboard a Chio developer (Day 1)

> Where to look first. What to skip. What changes for you when this repo is your daily driver.

## What this repo is (and isn't)

**Is:**

- A retrieval / graph / vault stack that helps you (and agents) navigate the Chio codebase, specs, and prior decisions.
- A canonical store for non-source knowledge — episodes, ADRs, briefs, playbooks.
- A regression-eval gate on retrieval quality and (Phase 0+) outcome quality.

**Isn't:**

- A code editor. Cursor / Claude Code / VS Code remain your editor.
- A PR review tool. Use `gh`.
- Documentation for the protocol itself — that lives in arc (`spec/PROTOCOL.md`) and is referenced from here, never duplicated.
- A wiki for "things you remember." Most things you remember go in your daily note or git history, not a permanent vault note.

## First-hour checklist

- [ ] Clone the repo and `cd` in.
- [ ] Read [[../PLAN]] end-to-end. Yes, all of it. It's the source of truth.
- [ ] Skim [[../AGENTS]]. The five hard rules are the contract you sign by working here.
- [ ] Skim [[../decisions/ADR-0000-charter|ADR-0000]]. It tells you what we are and aren't building.
- [ ] Run `make kb-status`. Phase 0 deps should be green; Phase 1+ may still be blocked depending on where the project is.
- [ ] If Phase 1 has landed: `cp .env.example .env`, fill in `OPENAI_API_KEY`, then `make kb-up`. Wait for the `ready` message.
- [ ] `make kb-smoke`. Confirm 10 `kb_*` tools list cleanly.
- [ ] Open the `vault/` folder in Obsidian. (See "Obsidian setup" below — optional.)

## First-day orientation

After the checklist, spend the rest of Day 1 here:

1. **Open [[../_meta/templates/daily-note]].** This is what your daily looks like. The morning brief surfaces episodes, open ADRs, stale specs you own, and live conformance failures.
2. **Walk through one episode.** [[../episodes/chio-architecture-summary]] (post-`make kb-migrate-seeds`) is the canonical "what is Chio" episode. Read it. Click the links. Notice that all of them resolve to either real arc files or other vault notes — never to fabricated paths.
3. **Read one ADR.** Start with [[../decisions/ADR-0000-charter|ADR-0000]], then jump to whatever ADR landed most recently.
4. **Read one playbook.** [[release-qualification]] is the most opinionated and shows how a real Chio operation links spec + receipts + tests.
5. **Try a `kb_search_code` call.** From your daily note, type `%% kb_search_code: capability revocation %%` and let the bridge plugin (Phase 3) render results inline. Pre-Phase-3, run `curl http://localhost:8111/mcp/ -d '{...}' | jq` per the README.

## The five hard rules

From [[../AGENTS]]. Internalize on Day 1:

1. **Never write to Graphiti directly.** The vault-sync daemon is the only writer. To add an episode, write `vault/episodes/<id>.md`.
2. **Never duplicate code into the vault.** Source lives in arc / platform / opus. The vault references by stable path + symbol.
3. **`kb-engine/` cannot import `chio_*`.** The boundary is enforced by CI. Register a plugin; don't fork.
4. **Vault frontmatter is a contract.** Bad frontmatter fails CI.
5. **Retrieval eval is the regression floor.** Overall A required. If `make kb-eval` drops below A on retrieval, revert; don't patch.

## Daily workflow (Days 2+)

A typical day with the vault open:

| Time | What you do |
| ---- | ----------- |
| Morning | Open today's daily note. Templater scaffolds it from [[../_meta/templates/daily-note]]. Morning brief: recent episodes, open ADRs, stale specs you own, conformance regressions since yesterday. |
| Mid-morning | Coding in Cursor / Claude Code. The KB serves you via MCP — `kb_search_code`, `kb_brief_feature`, `kb_impact`. You don't manually consult the vault for code questions. |
| Afternoon | Editing or proposing an ADR? Use [[../_meta/templates/adr]]. Linking a spec to its ADR? Use [[../_meta/templates/spec]]. Drafting an episode? [[../_meta/templates/episode]]. |
| 5pm | Jot "What I learned" in your daily note. The `episode-promoter` plugin (Phase 3) offers to convert it into an episode IF the content is substantive. Most days, skip. |
| Friday | Glance at [[../_meta/queries/stale-specs]]. Bump `last-validated:` on any spec you re-read this week. |

## Where Obsidian is the wrong tool

Be honest about this on Day 1:

- **Reading Rust source.** Don't. Open Cursor. The vault links to code; it doesn't host it.
- **PR review.** Use `gh`. Don't try to mirror PRs into notes.
- **Live debugging or log spelunking.** Wrong tool entirely.
- **API reference.** Generated docs win. Link out, don't duplicate.

If you find yourself reaching for Obsidian to do any of the above, you're doing it wrong. The vault is for curated knowledge — episodes, decisions, briefs, playbooks. Everything else has a better tool.

## Obsidian setup (optional)

Obsidian is **one renderer** of the vault — the vault works without it. Cursor, agents, and `grep` all read the markdown directly. Obsidian is the most pleasant UI for the daily-note flow, nothing more.

- Install Obsidian: <https://obsidian.md>.
- Open `vault/` as your vault.
- The first time you open it, Obsidian creates `vault/.obsidian/`. Most of that is gitignored (per-user state). The committed parts (`community-plugins.json`, themes, snippets) load automatically once Phase 3 lands.
- Pinned plugins (Phase 3): Dataview, Templater, Obsidian Git, Excalidraw, Tasks, Periodic Notes, Iconize, Style Settings. **Don't add others** without an ADR.

## Before you ship anything

- [ ] You've opened a daily note for at least 3 days. You have a feel for the morning brief.
- [ ] You've read at least 5 episodes and 3 ADRs. You've internalized the writing style.
- [ ] You've run `make kb-eval-outcomes`. You understand what's blocked, what's the regression floor, and why.
- [ ] You've re-read [[../AGENTS]] more carefully. Different things will jump out the second time.

## Your first contributions (Days 3-7)

In rough order:

1. **A daily note that records something you learned.** Promote one to an episode if it's load-bearing.
2. **A bumped `last-validated:` on a spec you re-read.** Smallest possible contribution; high signal that you're paying attention.
3. **An open question added to a spec.** Spec notes have an "Open questions" section for a reason — populate it.
4. **A new playbook step.** If you discover that [[release-qualification]] or [[revoke-a-capability]] is missing or wrong, propose the change.
5. **An ADR proposal.** Only when you have something real to propose. Don't write ADRs to "show you're contributing" — write them when a decision is genuinely required.

## Where to ask questions

- **Code-shaped question:** Cursor / Claude Code with the chio-kb MCP enabled. The retrieval is calibrated for this.
- **Decision-shaped question:** Search ADRs in `decisions/`. If no ADR covers it, that's the signal that one needs to be written.
- **Spec-shaped question:** Start with [[../spec/_README]]. The implements-bridge in spec notes points you at executable proof.
- **Workflow question:** This playbook, then [[../AGENTS]], then ask the person on point.

## See also

- [[../PLAN]] — full design
- [[../AGENTS]] — the rules
- [[../decisions/ADR-0000-charter|ADR-0000]] — the charter
- [[release-qualification]], [[revoke-a-capability]] — the most opinionated playbooks
- [[adopt-chio-developer-base]] — for second-adopter teams (not for new individual devs)
