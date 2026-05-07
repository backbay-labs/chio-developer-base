# KB Staleness Badge

Custom Obsidian plugin for chio-developer-base. Shows a colored badge in the active note's title bar based on the `last-validated:` frontmatter field.

## What it does

- Reads `last-validated:` from the active note's frontmatter (parsed as YYYY-MM-DD).
- Computes age in days against today's date.
- Renders a small colored pill in the view-header title container:

| Age (days) | Color | Meaning |
| ---------- | ----- | ------- |
| `< 30` | green | fresh |
| `30–89` | yellow | gentle nudge — daily-note morning brief flags at 60d |
| `90–179` | orange | stale-specs query flags it |
| `≥ 180` | red | release blocker per [release-qualification playbook](../../../vault/playbooks/release-qualification.md) |

Hover the badge for the exact day-count and threshold reminder.

## What it does NOT do

- It does not modify the note. Read-only.
- It does not write to Graphiti. Per [AGENTS.md](../../../AGENTS.md) hard rule #1, only the vault-sync daemon is permitted to write Graphiti.
- It does not auto-bump `last-validated:`. That's a deliberate human action — bumping the date asserts "I re-read this against current code."
- It does not parse non-YYYY-MM-DD date formats. The plugin is best-effort; ambiguous dates get no badge.

## Develop

```sh
cd .obsidian/plugins/kb-staleness-badge
npm install
npm run dev          # watches src/main.ts → main.js
```

Production build:

```sh
npm run build
```

The compiled `main.js` is **not committed** (see this directory's `.gitignore`). Obsidian users build it themselves on first install.

## File layout

```
kb-staleness-badge/
├── manifest.json         Obsidian plugin metadata (committed)
├── package.json          npm config (committed)
├── tsconfig.json         TypeScript config (committed)
├── esbuild.config.mjs    build script (committed)
├── src/main.ts           plugin source (committed)
├── README.md             this file (committed)
├── versions.json         plugin version → minAppVersion map (committed)
├── version-bump.mjs      npm version helper (committed)
├── .gitignore            (committed)
├── main.js               built artifact (gitignored)
├── node_modules/         (gitignored)
└── data.json             per-vault settings (gitignored — user state)
```

## Settings (Phase 3+)

Today the thresholds are hard-coded as `DEFAULT_SETTINGS`:

```ts
yellowDays: 30,
orangeDays: 90,
redDays: 180,
```

A future settings tab will let users tune these per-vault. For now, edit `src/main.ts` and rebuild.

## Phase awareness

This is a **Phase 3** deliverable per [PLAN.md](../../../PLAN.md). Listed in [`.obsidian/community-plugins.json`](../../community-plugins.json) so Obsidian recognizes it; will fail to load until `main.js` is built.

## See also

- [AGENTS.md](../../../AGENTS.md)
- [PLAN.md](../../../PLAN.md)
- [`vault/_meta/queries/stale-specs.md`](../../../vault/_meta/queries/stale-specs.md) — the org-wide staleness dashboard this badge complements
- [`vault/playbooks/release-qualification.md`](../../../vault/playbooks/release-qualification.md) — the release blocker rule (≥180 days)
- [`vault/_meta/templates/spec.md`](../../../vault/_meta/templates/spec.md) — the spec template that pre-fills `last-validated:`
- [`episode-promoter/`](../episode-promoter/) — sibling custom plugin
