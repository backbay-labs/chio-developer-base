---
id: spec.guard.pipeline
type: spec
status: accepted
chio-node: Guard
crate: chio-guards
supersedes: []
related-specs:
  - spec.capability.revocation
related-receipts:
  - receipt.guard-verdict
related-guards: []
graphiti-episode: episode.guard-policy-fail-closed
related-diagrams: []
owners:
  - "@connor"
last-validated: 2026-05-07
---

# Guard pipeline

The deterministic, fail-closed pipeline every Chio capability exercise passes through before crossing a trust boundary.

## Normative

> [!normative]
> Every capability exercise MUST pass through the guard pipeline before the kernel performs the requested action. There is **no "trusted path"** that bypasses guards.

> [!normative]
> Each guard in the pipeline MUST evaluate to one of three outcomes: `allow`, `deny`, or `error`. There is no `unknown` or `defer` verdict.

> [!normative]
> Any `error` outcome MUST be treated as `deny`. **Fail-closed is the entire point.** A guard that crashes, times out, or returns malformed input rejects the exercise.

> [!normative]
> Guard outcomes MUST be evaluated in declaration order, and a `deny` MUST short-circuit the remaining guards. The verdict receipt records the first denying guard.

> [!normative]
> Every guard verdict (regardless of outcome) MUST emit `receipt.guard-verdict.<exercise-id>` recording: which guards ran, in what order, with what verdicts, and which (if any) denied.

## Why

> [!guard]
> Fail-closed under partition is the load-bearing property. A pipeline that fails *open* under network partition is no pipeline at all — every Chio guarantee depends on this.

The decision to make the pipeline fully deterministic (rather than allowing concurrent guard evaluation, or `unknown`/`defer` verdicts) is recorded in [[../episodes/guard-policy-fail-closed]] and reflects three constraints:

1. **Determinism is replayability.** A pipeline you can't replay deterministically can't be audited. Concurrency violates that.
2. **Three-valued logic explodes.** `unknown` or `defer` verdicts force every downstream consumer to handle an "I don't know" case. In practice, those handlers default to either always-allow (insecure) or always-deny (functionally identical to a 2-valued `error → deny`). Pick the second from the start.
3. **Order matters because reasons matter.** The denying guard is the most important fact in the verdict receipt. Hiding it under reordering or parallel evaluation makes audits ambiguous.

## Implements

- `chio_guards::pipeline` — `crates/chio-guards/src/pipeline.rs` (the executor)
- `chio_guards::lib` — `crates/chio-guards/src/lib.rs` (the `Guard` trait)
- `chio_kernel::evaluator` — `crates/chio-kernel/src/kernel/evaluator.rs` (kernel-side caller)
- `chio_policy::evaluate::matchers` — `crates/chio-policy/src/evaluate/matchers.rs` (the policy-driven guard implementations)
- `chio_guards::mcp_tool` — `crates/chio-guards/src/mcp_tool.rs` (the MCP-call adapter)

## Tested by

- `crates/chio-guards/tests/pipeline_order.rs` — declaration-order short-circuiting
- `crates/chio-guards/tests/fail_closed_under_partition.rs` — error → deny under network failure
- `crates/chio-guards/tests/verdict_receipt.rs` — receipt content matches verdict
- `crates/chio-policy/tests/evaluator_e2e.rs` — policy → guards integration
- `tests/conformance/peers/*/test_guards.*` — SDK conformance

## Operations

- [[../playbooks/release-qualification#gate-2--guard-pipeline]] — release-time guard validation.
- Individual guard playbooks reference back here for shared semantics.

## Specific guards built on this pipeline

These specs describe individual guards that execute *within* the pipeline. They inherit the fail-closed and verdict-receipt obligations from this spec:

- [[capability-revocation]] — `guard.revocation-window`, the 5-second revocation enforcement guard.
- _(Future) Rate-limit guards, scope-narrowing guards, etc._

## Open questions

- [ ] **Guard composition.** Today the pipeline is a flat list. Should we support `all-of` / `any-of` composite guards, or is composition pushed into individual `Guard` implementations? The "any-of" case in particular is dangerous (it weakens fail-closed). Pending an ADR.
- [ ] **Guard timeouts.** Today guards run synchronously with no explicit timeout — slow guards can DOS the pipeline. Should the spec mandate per-guard wall-clock budgets? Probably yes.
- [ ] **Verdict-receipt size.** A pipeline with 20 guards produces a verdict receipt with 20 entries. For high-throughput exercises that's wasteful. Open whether allow-cases can collapse to a "summary verdict" (with the deny case still expanding to full detail).

## Staleness

> [!warning-staleness]
> Last validated 2026-05-07. Re-validate against `crates/chio-guards/src/pipeline.rs` and the chio-policy evaluator paths whenever those crates' major version bumps. Re-validate sooner if a new individual guard spec is added.

## Graph context

%% kb_neighbors: spec.guard.pipeline depth=2 %%

## Lineage

Derived from the seed [[../episodes/guard-policy-fail-closed]] (migrated from arc PR #599's `seeds/graphiti/guard-policy-fail-closed.json` via `make kb-migrate-seeds`). The seed records the *why* (fail-closed everywhere); this note is the normative *what*.
