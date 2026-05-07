---
id: meta.hotkeys
type: meta
---

# Canonical hotkeys

Configured in [`.obsidian/hotkeys.json`](../../.obsidian/hotkeys.json) (committed, not gitignored). Obsidian's Settings → Hotkeys panel writes overrides to the same file; users can rebind freely without breaking the canonical defaults for the next fresh checkout.

## Bindings

| Combo | Command | Why |
| ----- | ------- | --- |
| `Cmd+Shift+E` | `episode-promoter:promote-to-episode` | The "What I learned" → episode flow is the highest-leverage daily action. Worth a top-row binding. |
| `Cmd+Shift+T` | `periodic-notes:open-daily-note` | Open today's daily note. Combined with auto-creation from the [Periodic Notes plugin](../../.obsidian/plugins/periodic-notes/data.json), Cmd+Shift+T = "morning brief, now". |
| `Cmd+Shift+G` | `obsidian-git:open-source-control-view` | Open the Git source control panel. Daily commit cadence is part of the vault's contract (auto-save every 60s, auto-pull every 30 min); Cmd+Shift+G is the deliberate "stage and commit now" gesture. |

`Mod` resolves to `Cmd` on macOS and `Ctrl` on Windows/Linux. The bindings are cross-platform.

## Adding more

Edit `.obsidian/hotkeys.json` directly OR use Obsidian's Hotkeys settings UI. The file format is one entry per command:

```json
{
  "<plugin-id>:<command-id>": [
    { "modifiers": ["Mod", "Shift"], "key": "X" }
  ]
}
```

Modifier keys: `Mod`, `Ctrl`, `Shift`, `Alt`, `Meta`. Multiple bindings per command are allowed (the value is an array).

## Conflict policy

If a contributor wants a different default, they have three options:

1. **Override in Obsidian's UI.** This writes to `.obsidian/hotkeys.json` and shows up in `git status`. Don't commit unless the team has agreed to flip the canonical default.
2. **Local-only opt-out.** `git update-index --skip-worktree .obsidian/hotkeys.json` keeps a local hotkey file without git tracking changes. Reverse with `--no-skip-worktree`.
3. **Propose a new default.** Open a PR updating both `.obsidian/hotkeys.json` and this table. Hotkey changes are not load-bearing but they affect everyone's muscle memory; review accordingly.

## See also

- [`.obsidian/hotkeys.json`](../../.obsidian/hotkeys.json) — the actual file
- [`AGENTS.md`](../../AGENTS.md) — project-wide conventions
- [`onboard-a-chio-developer.md`](../playbooks/onboard-a-chio-developer.md) — Day 1, where these hotkeys first show up
