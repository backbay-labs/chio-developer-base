---
id: meta.issue.m1-cutover-arc
type: issue
status: open
title: "M1 Phase 1.6 — arc cutover from in-tree KB to chio-developer-base"
opened: 2026-05-08
opened_by: w2-cutover-agent
owners:
  - connor
labels:
  - milestone:M1
  - blocker:wave-2-cutover
  - cross-repo:arc
related:
  - "[[../../../PLAN.md|PLAN.md Phase 1.6]]"
  - "[[../../decisions/_README|decisions/]]"
  - "PR #599 (arc): codex/chio-kb-a-grade-dogfood"
---

# M1 Phase 1.6 — arc cutover from in-tree KB to chio-developer-base

## Why this exists

Wave 2 in this repo (branch `m1/cutover`) implements
`chio_tool_registrar` (the 10 `kb_*` tools wired through the plugin
protocol). That side is now done — see commit
`M1-Cutover.1: implement chio_tool_registrar with 10 kb_* tools`.

The other half of Phase 1.6 — **deleting `arc/ops/knowledge-base/` and
pointing arc CI at chio-developer-base as its KB backend** — has to
land as a PR against `bb-connor/arc`. That PR cannot be authored by an
agent on this side because:

1. arc and chio-developer-base are separate repos with separate
   review/merge gates.
2. arc CI changes are owned by arc maintainers; the chio-developer-base
   side cannot validate that chio-developer-base-as-backend keeps arc
   CI green.

So this issue is the hand-off doc. A person picking this up should be
able to act on it without reading the Wave 2 conversation.

## What needs to happen on the arc side

### 1. Delete the in-tree KB stack

Remove `arc/ops/knowledge-base/` in its entirety. Concretely:

- `arc/ops/knowledge-base/chio_kb/` — Python package (mcp_server, query,
  index, seed_memory, eval_runner, smoke, repo_model, maintenance,
  graph_seed). Everything that was published in PR #599
  `codex/chio-kb-a-grade-dogfood`.
- `arc/ops/knowledge-base/Dockerfile.kb-mcp`
- `arc/ops/knowledge-base/docker-compose.yml`
- `arc/ops/knowledge-base/postgres/`, `seeds/`, `config/`, `eval/`
- `arc/ops/knowledge-base/tests/`
- `arc/ops/knowledge-base/pyproject.toml`, `uv.lock`
- `arc/ops/knowledge-base/DOGFOOD-REVIEW.md`, `README.md`

### 2. Replace `KB_DIR` Make targets with thin wrappers

`arc/Makefile` currently has 12 `kb-*` targets (`kb-up`, `kb-down`,
`kb-reset`, `kb-reseed`, `kb-update`, `kb-live`, `kb-status`,
`kb-smoke`, `kb-eval`, `kb-seed-memory`, `kb-dogfood`,
`kb-lock-check`) and a `KB_DIR ?= ops/knowledge-base` variable. After
cutover, each target should shell into the chio-developer-base
repo's equivalent target. Two options:

- **Option A (preferred): submodule.** Add chio-developer-base as a git
  submodule at `arc/third_party/chio-developer-base/` (read-only;
  don't commit changes from inside arc). Re-point `KB_DIR` to
  `third_party/chio-developer-base/` and delegate each `kb-*` target
  to the matching `chio-developer-base/Makefile` target.
- **Option B: thin Make wrapper.** Drop the submodule entirely; keep
  a single `KB_REPO ?= ../chio-developer-base` variable and shell out:
  `kb-up: ; $(MAKE) -C $(KB_REPO) kb-up`. Faster to land but couples
  arc CI to a sibling-checkout convention.

PLAN.md "Linked work in arc" says PR #599's stack
"Will be replaced by a thin Make wrapper or submodule reference once
Phase 1 lands." — so either option is sanctioned. ADR-0001
(graduation criteria) should be checked before choosing; a submodule
freezes a SHA, a wrapper doesn't.

### 3. Repoint env / config

The MCP gateway lives on `:8111` either way. Audit arc for hardcoded
references to:

- `ops/knowledge-base/` paths (grep arc for the literal string).
- `chio_kb` Python imports — none should remain after step 1, but
  confirm with `grep -rn "import chio_kb\|from chio_kb" arc/` post-delete.
- `chio-kb-mcp` docker service name in any compose file outside
  `ops/knowledge-base/` — re-point or drop.
- `CHIO_KB_*` environment variables (CHIO_KB_MCP_BEARER_TOKEN,
  CHIO_KB_MCP_HOST, CHIO_KB_MCP_PORT, CHIO_KB_MAX_INFLIGHT_COMPONENTS,
  COCOINDEX_SOURCE_MAX_INFLIGHT_ROWS) — chio-developer-base will
  honour the same names; document the dependency.

### 4. Conformance harness coupling

`arc/tests/conformance/` is the source of truth for the
`conformance-harness-recall` outcome eval (PHASE-0.md fixtures: 20).
The cutover MUST NOT change the conformance fixture format. If
chio-developer-base needs different paths it should adapt; arc's tree
is the contract. Confirm by running `chio-pack-eval --eval
conformance-harness-recall` against the new backend before merging
the arc PR.

### 5. Receipts (Phase 2 forward dependency)

`arc/crates/chio-receipts/` will be consumed by chio-developer-base
in Phase 2B (M2 in scratchpad). Don't move or rename the crate as
part of this cutover; that's a separate ADR.

## Arc CI signal that proves cutover landed

Acceptance is **two checks both green on the arc PR**:

1. **`make kb-up && make kb-eval`** runs to completion against
   chio-developer-base-as-backend and reports retrieval grade A
   (matching PR #599 baseline). The `kb-eval` target's
   `--fail-below-a` flag is the regression floor — no grade
   regression is allowed at cutover time.
2. **arc's existing CI workflows that depend on KB seeding**
   (verify with `grep -l 'kb-up\|kb-update\|kb-reseed'
   arc/.github/workflows/`) all turn green on the PR. Today the
   visible candidates are `nightly.yml`, `release-qualification.yml`,
   `verdict-matrix.yml`. **Confirm the actual list at PR-open time
   and paste it into the PR body** — the 12 May 2026 list might not
   match.

If either fails:
- Fail #1 (retrieval below A): roll back, re-open this issue with
  what regressed. Don't paper over with a PR-only retrieval suite.
- Fail #2 (downstream CI red): roll back, file a new issue per
  workflow that broke; do not skip workflows to land the cutover.

## Rollback plan

If the cutover PR has to be reverted after merge:

1. `git revert` the cutover commit on arc `main`.
2. Re-run `make kb-up && make kb-eval` on arc — should restore
   baseline because `ops/knowledge-base/` files come back.
3. On the chio-developer-base side, no rollback is needed: the
   plugin-protocol implementation in `chio_pack/plugin.py` is
   independent of whether arc has cut over yet. The 10 tools register
   against any ``Server`` exposing ``register_tool``; arc cutting
   over later just means arc's gateway is the consumer instead of a
   FakeServer or a Phase 1.3+ MCP framework.

## Path-level grep evidence collected on this side

Run from `/Users/connor/Medica/backbay/standalone/arc/` at cutover
time to confirm the surface area hasn't shifted from May 2026:

```sh
# Files that import chio_kb (must be 0 after step 1):
grep -rln "import chio_kb\|from chio_kb" --include="*.py" .

# Make targets that reference KB_DIR (12 today):
grep -n "KB_DIR\|kb-up\|kb-down\|kb-reset\|kb-reseed\|kb-update\
|kb-live\|kb-status\|kb-smoke\|kb-eval\|kb-seed-memory\|kb-dogfood\
|kb-lock-check" Makefile

# CI workflows referencing kb targets:
grep -rln "kb-up\|kb-update\|kb-reseed\|kb-eval" .github/workflows/

# Docker compose services:
grep -n "chio-kb-mcp\|graphiti-mcp\|kb-postgres\|kb-neo4j" \
    ops/knowledge-base/docker-compose.yml
```

## Out of scope for this PR

- The `chio_tool_registrar` implementation. Already shipped on the
  chio-developer-base side, branch `m1/cutover`, commit
  `M1-Cutover.1` — see `chio-pack/chio_pack/plugin.py` and
  `chio-pack/chio_pack/tools/`.
- Phase 2 receipt-signing (M2 in `.cursor/scratchpad.md`). Don't
  bundle.
- Vault-sync daemon (Phase 1.4 / T1.8). Don't bundle — daemon work
  belongs in the chio-developer-base repo, not arc.

## Status / next action

Open. Hand off to a person with arc commit access. ETA per scratchpad
risk note: "Budget 3 days if [PR #599 bypassed plugin protocol]."
The `chio_tool_registrar` work in chio-developer-base proves the
plugin contract works end-to-end; PR #599's monolith should drop in
behind the registrar without further engine changes.
