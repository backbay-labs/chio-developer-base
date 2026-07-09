# Arc KB_DIR Cutover

Wave 3 prepares the Arc PR that switches Arc's knowledge-base backend from
`tools/knowledge-base` to this repository (`chio-developer-base`). The PR should
be thin: preserve Arc's `make kb-*` command surface, delegate execution to
chio-developer-base, and leave deletion of `tools/knowledge-base` to the
follow-up cleanup PR.

**Human one-shot checklist:** [`PR-CHECKLIST.md`](PR-CHECKLIST.md)

## Prepared Artifacts

- `Makefile.kb-wrapper` — drop-in Make fragment for Arc. Defines the existing
  `kb-*` targets and forwards them to this repo with `ARC_REPO=$(CURDIR)`.
- `patch-arc-makefile.diff` — shows the Arc Makefile change (also applied
  locally on branch `cutover/kb-dir-chio-developer-base`).
- `PR-CHECKLIST.md` — push/PR body/test plan for a human with arc write access.

## Local verification already run (2026-07-08 continuation)

```sh
cd /Users/connor/Medica/backbay/standalone/arc
git switch cutover/kb-dir-chio-developer-base
make -n kb-eval    # → make -C ../chio-developer-base ARC_REPO=... kb-eval
make -n kb-status
make kb-status     # live; healthy postgres/neo4j/mcp; no kb-reset
test -d tools/knowledge-base && echo kept
```

## Arc PR Steps

1. Confirm local branch + commit (already prepared; do not re-apply patch unless
   the branch was reset):

   ```sh
   cd /Users/connor/Medica/backbay/standalone/arc
   git switch cutover/kb-dir-chio-developer-base
   # If starting fresh instead:
   # git switch -c cutover/kb-dir-chio-developer-base
   # git apply ../chio-developer-base/ops/arc-cutover/patch-arc-makefile.diff
   ```

2. Confirm the Makefile target surface is unchanged:

   ```sh
   make -n kb-status
   make -n kb-eval
   make -n kb-dogfood
   ```

3. Run the cutover acceptance gate. Do not run `make kb-reset` unless Connor
   explicitly approves the data-destructive reset.

   ```sh
   make kb-status   # non-destructive
   # make kb-up && make kb-eval   # when ready for full gate
   ```

4. Open the Arc PR **without agent push**. Binary acceptance:

   - `make kb-up && make kb-eval` passes against chio-developer-base and keeps
     retrieval grade A.
   - Arc CI workflows that seed or query KB all pass.

5. After the cutover PR is merged and CI is green, open a follow-up cleanup PR
   that deletes `tools/knowledge-base/`.

## CI Notes

- The default sibling checkout path is `../chio-developer-base`. Override with
  `KB_DIR=/absolute/path/to/chio-developer-base` if Arc CI checks out repos in a
  different layout.
- `kb-lock-check` is implemented by the wrapper because chio-developer-base does
  not expose a top-level target with that name; it checks `chio-pack/uv.lock`.
- The wrapper forwards `PACK_SCHEMA`, `CHIO_KB_*`, and other environment
  variables naturally through Make and the shell.
