/**
 * tp.user.handle() — return the user's GitHub / team handle.
 *
 * Usage in a Templater template:
 *
 *     <% tp.user.handle() %>
 *
 * EDIT THE LINE BELOW on first checkout. The file is committed, so any
 * change appears in `git status` — by design. Two patterns:
 *
 *   (a) Solo maintainer: commit your handle as the canonical default for
 *       the vault. Other contributors will see it; that's fine for a single-
 *       maintainer setup.
 *
 *   (b) Shared vault: each contributor sets their handle locally and runs
 *           git update-index --skip-worktree _meta/templater-scripts/handle.js
 *       so their local change doesn't fight commits from other contributors.
 *       Reverse with `--no-skip-worktree` when intentional updates are needed.
 *
 * The handle is baked into Dataview queries at note-creation time by
 * Templater. It's used by the daily-note morning brief to filter "things I
 * own" — stale specs, my proposed ADRs, etc. See
 * `_meta/templates/daily-note.md` for the consumers.
 */

module.exports = async () => "@connor";
