---
id: meta.icons
type: meta
---

# Folder icon mapping

> Canonical folder-icon assignments. Configured in [`vault/.obsidian/plugins/obsidian-icon-folder/data.json`](../.obsidian/plugins/obsidian-icon-folder/data.json) and consumed by the **Iconize** community plugin (formerly "Obsidian Icon Folder").

## Why icons exist

Sounds frivolous, isn't. Folder icons reduce wrong-folder-clicks dramatically once a vault has ~10+ folders. The canonical set below is opinionated on purpose — bikeshedding individual icons is wasted energy.

If a folder doesn't appear here, it has no canonical icon. Don't add one without an ADR-light comment in the plugin's data.json.

## Top-level

| Folder        | Icon              | Lucide name         | Why this icon |
| ------------- | ----------------- | ------------------- | ------------- |
| `_meta/`      | gear              | `LiSettings`        | Configuration / meta. |
| `spec/`       | open book         | `LiBookOpenText`    | Normative reading material. |
| `decisions/`  | gavel             | `LiGavel`           | Decisions, judgment, finality. |
| `episodes/`   | clock-arrow       | `LiHistory`         | Temporal memory. |
| `playbooks/`  | book              | `LiBookText`        | Operational handbook. |
| `daily/`      | calendar          | `LiCalendarDays`    | Daily notes, periodic. |
| `crates/`     | package           | `LiPackage`         | Rust crates. (Phase 1+) |

## `_meta/` subfolders

| Folder                     | Icon         | Lucide name      | Why |
| -------------------------- | ------------ | ---------------- | --- |
| `_meta/templates/`         | document     | `LiFileText`     | Document templates. |
| `_meta/queries/`           | magnifier    | `LiSearch`       | Saved Dataview queries. |
| `_meta/diagrams/`          | pen tool     | `LiPenTool`      | Excalidraw drawings. |
| `_meta/dashboards/`        | bar chart    | `LiBarChart`     | Generated reports. |
| `_meta/templater-scripts/` | code         | `LiCode`         | JS user-functions for Templater. |

## Color

All icons share the Backbay accent (`#6054A7`, see [`vault/.obsidian/appearance.json`](../.obsidian/appearance.json)). The iconize setting `iconsInLinks: true` extends the icon to wikilinks too, so when a daily note links to a spec, the spec link carries the open-book icon inline.

## Adding a new folder

If you create a top-level folder (which requires an ADR per [PLAN.md](../../PLAN.md)), add its icon mapping to:

1. The plugin data.json:
   ```json
   "<folder>": "Li<IconName>"
   ```
2. The relevant table in this doc.

Pick from the [Lucide icon set](https://lucide.dev/icons/). Don't install other icon sets (FontAwesome, Remix, etc.) — Lucide is built into Obsidian and ships zero install.
