---
id: meta.templater-scripts-readme
type: meta
---

# `_meta/templater-scripts/`

User-defined JavaScript functions for the [Templater](https://silentvoid13.github.io/Templater/) plugin. Templater calls files in this folder as `<% tp.user.<filename>() %>` from any template.

## Wired up by

The Templater plugin's `user_scripts_folder` is set to this directory. See [`vault/.obsidian/plugins/templater-obsidian/data.json`](../../.obsidian/plugins/templater-obsidian/data.json).

## What's here

| File | Used by | Purpose |
| ---- | ------- | ------- |
| [`handle.js`](handle.js) | [[../templates/daily-note]] morning brief | Returns the user's `@handle`. Filters Dataview queries to "things I own". |

## Authoring rules

- **Each script is one function.** Filename = function name. `tp.user.foo()` calls `foo.js`.
- **Scripts receive `tp` as their argument** if they need vault access (`tp.app.vault.read(...)`, etc.). Pure functions can ignore it.
- **Async by convention.** Templater awaits the result. `module.exports = async (tp) => ...`.
- **No side effects on the vault** unless documented. A user-script that writes files surprises every reader of every template that calls it.
- **No network calls.** Templates render synchronously from the user's perspective; a script that does `fetch()` will stall the editor.

## Why scripts vs. inline Templater logic

Templater's `<% ... %>` blocks support arbitrary JS, but inline blocks are:

- Hard to test (you'd run them by creating a note and inspecting the output).
- Hard to share across templates (copy-paste).
- Invisible to the rest of the vault (no Dataview / search visibility).

A user-script in this folder is debuggable, reusable, and visible.

## Common patterns

### Reading from a vault note

```javascript
module.exports = async (tp) => {
  const file = tp.app.vault.getAbstractFileByPath("some/path.md");
  if (!file) return "";
  const text = await tp.app.vault.read(file);
  return text.split("\n")[0];   // first line, etc.
};
```

### Conditional based on date

```javascript
module.exports = async () => {
  const day = new Date().getDay();
  return day === 5 ? "Friday review" : "Daily note";
};
```

## Adding a script

1. Create `<name>.js` in this folder.
2. Reference as `<% tp.user.<name>() %>` in any template.
3. Add a row to the table above.
4. If the script changes daily-note semantics, also update [[../templates/daily-note]].
