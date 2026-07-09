# Arc cutover PR — one-shot human checklist

Open this when you are ready to push `cutover/kb-dir-chio-developer-base` and file the PR.
Agents must **not** push. Do **not** delete `tools/knowledge-base` in this PR.

## Preconditions (already done locally)

- [x] Branch: `cutover/kb-dir-chio-developer-base` on `standalone/arc`
- [x] Commit: `KB_DIR ?= ../chio-developer-base` + `include $(KB_DIR)/ops/arc-cutover/Makefile.kb-wrapper`
- [x] `tools/knowledge-base/` still present (deletion is follow-up only)
- [x] Dry-run: `make -n kb-eval` / `make -n kb-status` delegate to chio-developer-base
- [x] Live non-destructive: `make kb-status` reports Phase 0/1 deps + healthy compose stack

## Human steps (copy/paste)

```bash
export PATH="/Users/connor/.local/bin:/opt/homebrew/bin:$PATH"

# 1. Confirm sibling layout
cd /Users/connor/Medica/backbay/standalone/arc
test -d ../chio-developer-base/ops/arc-cutover
git branch --show-current   # expect: cutover/kb-dir-chio-developer-base
git log -1 --oneline        # expect cutover commit

# 2. Dry-run surface (must print make -C ../chio-developer-base ...)
make -n kb-status
make -n kb-eval
make -n kb-dogfood
make -n kb-lock-check

# 3. Non-destructive live status (safe; no kb-reset)
make kb-status

# 4. Optional acceptance when stack is warm (do NOT run kb-reset without Connor OK)
# make kb-eval

# 5. Push + open PR (human only)
git push -u origin HEAD
gh pr create --title "chore(kb): cutover KB_DIR to chio-developer-base" --body "$(cat <<'EOF'
## Summary
- Point `KB_DIR` at sibling `../chio-developer-base` via `ops/arc-cutover/Makefile.kb-wrapper`.
- Preserve `make kb-*` surface; leave `tools/knowledge-base` in tree until CI is green.

## Test plan
- [ ] `make -n kb-status` / `kb-eval` / `kb-dogfood` delegate to chio-developer-base
- [ ] `make kb-status` healthy against local stack
- [ ] Arc CI workflows that seed/query KB are green
- [ ] Follow-up issue filed to delete `tools/knowledge-base` after merge

## Notes
- Override path in CI with `KB_DIR=/absolute/path/to/chio-developer-base` if sibling checkout differs.
- Do not delete `tools/knowledge-base` in this PR.
EOF
)"
```

## CI path override

If Arc CI checks out repos side-by-side under a different name, set:

```bash
make kb-status KB_DIR=/path/to/chio-developer-base
```

## Follow-up (separate PR, after CI green)

1. Delete `arc/tools/knowledge-base/`.
2. Grep for leftover `tools/knowledge-base` / `import chio_kb` references.
3. Close [`vault/_meta/issues/m1-cutover-arc.md`](../../vault/_meta/issues/m1-cutover-arc.md).

## Rollback

`git revert` the cutover commit on arc; in-tree `tools/knowledge-base` recipes return because they were never deleted.
