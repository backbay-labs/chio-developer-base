# chio-pr-gate/

> **Status:** placeholder. The gate lands in **Phase 2A** ([PLAN.md](../PLAN.md) Moonshot 1).

A GitHub Action that runs `kb_impact` and `kb_brief_feature` against every arc PR's diff and **fails the check** if downstream guards / conformance tests / policy compilers depend on the changed contract without being acknowledged in the PR body.

## Why this is Chio-specific

Chio's failure mode is contract drift across the protocol/standards split. The graph already encodes this. Not using it at PR time is malpractice — the diagnostic surface is there, it just isn't wired to the merge gate.

## Planned layout

```
chio-pr-gate/
├── action.yml                   GitHub Action entrypoint
├── src/
│   ├── gate.py                  diff → impacted-contract resolver
│   ├── render.py                PR-comment markdown renderer
│   └── policy.py                pass/fail rules (which edges fail; which warn)
├── tests/
│   ├── fixtures/                synthetic PRs for unit tests
│   └── backtest/                last-50-PRs harness
└── README.md
```

## MVP shape (PLAN.md Moonshot 1)

```
diff
  → changed files
  → kb_impact(file) for each high-risk file
  → kb_brief_feature(symbol_or_path) per impacted contract
  → render PR comment with: impacted suites, missing-test list, suggested ADRs
  → check run pass/fail based on:
       - any GUARDS / IMPLEMENTS edge crossed without test mention
       - any CANONICAL_DOC node touched without `last-validated` bump
```

## Eval target

A new outcome eval `pr-impact-gate-precision-recall`. Backtest against the last 50 merged Chio PRs:

- **Precision ≥ 0.7** — when the gate fires, the PR genuinely needed a follow-up within 14 days.
- **Recall ≥ 0.8** — for PRs that needed a follow-up within 14 days, the gate fired.

If the backtest falls below those thresholds, the gate ships **advisory-only** (warns, doesn't fail) until it earns its pass/fail authority. See PLAN.md "Open decisions / risks" item 5.

## Escape hatch

Authors can override the gate by adding a marker to the PR body:

```
kb-gate: ack
> reason: revocation-window guard intentionally relaxed; ADR-0073
```

The `kb-gate: ack` marker is recognized by `gate.py` and converts a fail into a pass. The reason is required and is captured in the PR comment.

## What does NOT belong here

- Generic GitHub Action utilities. If they're reusable, they live in `kb-engine/` once productized.
- Eval harness code. The backtest *fixtures* live here; the eval *runner* is `chio_pack.eval.runners.gate_backtest` per `outcomes.yml`.

## See also

- [PLAN.md](../PLAN.md#moonshot-1--pr-time-kb_impact-gate) — the moonshot design
- [`chio-pack/eval/outcomes.yml`](../chio-pack/eval/outcomes.yml) — the deferred `pr-impact-gate-precision-recall` eval entry
- [`chio-pack/eval/PHASE-0.md`](../chio-pack/eval/PHASE-0.md) — outcome eval framework
