# Episode Promoter

Custom Obsidian plugin for chio-developer-base. Promotes a daily note's `## What I learned` section into a Graphiti episode candidate.

## What it does

1. Adds a command **"Promote 'What I learned' to episode"** to the command palette.
2. Available only when the active file lives under `vault/daily/`.
3. Parses the `## What I learned` heading and the section under it.
4. Opens a confirmation modal with editable: title, slug, type (dropdown), and body preview.
5. On **Confirm**, writes `vault/episodes/<slug>.md` with frontmatter that the vault-sync daemon (Phase 1) will use to derive a Graphiti episode.
6. On **Cancel** or empty section: no-op.

## What it does NOT do

- **It does not call Graphiti directly.** Per [AGENTS.md](../../../../AGENTS.md) hard rule #1, the vault-sync daemon is the only writer to Graphiti. This plugin writes the markdown file; the daemon picks it up.
- **It does not auto-promote.** The modal's confirmation step is mandatory by design — auto-promotion would poison the graph within a week (per the Obsidian-UX brainstorm).
- **It does not extract entities or graph edges yet.** Phase 1+ feature: parse the body for symbol references and propose edges. Today, the plugin writes a simple frontmatter shell.

## Develop

```sh
cd vault/.obsidian/plugins/episode-promoter
npm install
npm run dev          # watches src/main.ts → main.js
```

For a production build:

```sh
npm run build        # one-shot, minified, no source map
```

The compiled `main.js` is **not committed** (see this directory's `.gitignore`). Obsidian users build it themselves on first install or pull a release artifact once we tag plugin versions.

## File layout

```
episode-promoter/
├── manifest.json         Obsidian plugin metadata (committed)
├── package.json          npm config (committed)
├── tsconfig.json         TypeScript config (committed)
├── esbuild.config.mjs    build script (committed)
├── src/main.ts           plugin source (committed)
├── README.md             this file (committed)
├── .gitignore            (committed)
├── main.js               built artifact (gitignored)
├── node_modules/         (gitignored)
└── data.json             per-vault settings (gitignored — user state)
```

## Versioning

Bump `version` in `manifest.json` AND `package.json` together. Plugin versions are independent of the parent repo's git tags.

## Phase awareness

This is a **Phase 3** deliverable per [PLAN.md](../../../../PLAN.md). Listed in [`vault/.obsidian/community-plugins.json`](../../community-plugins.json) so Obsidian recognizes it; will fail to load until `main.js` is built. That's fine — the vault works without Obsidian.

## See also

- [AGENTS.md](../../../../AGENTS.md) — hard rule on no-direct-Graphiti-writes
- [PLAN.md](../../../../PLAN.md) — Phase 3 vault UX layer
- [`vault/_meta/templates/daily-note.md`](../../../_meta/templates/daily-note.md) — what a "What I learned" section looks like
- [`vault/episodes/_README.md`](../../../episodes/_README.md) — what a real episode looks like
- [`migrate-seeds.py`](../../../../ops/scripts/migrate-seeds.py) — a sibling: writes the same shape of frontmatter from JSON seeds. The two should converge on identical schemas.
