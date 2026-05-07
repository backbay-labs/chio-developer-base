---
id: spec.policy.compiler
type: spec
status: accepted
chio-node: Policy
crate: chio-policy
supersedes: []
related-specs:
  - spec.guard.pipeline
related-receipts:
  - receipt.policy-compile
  - receipt.policy-eval
related-guards: []
graphiti-episode: episode.guard-policy-fail-closed
related-diagrams: []
owners:
  - "@connor"
last-validated: 2026-05-07
---

# Policy compiler

The deterministic compile-and-evaluate pipeline that turns Chio policy text into the rules each guard runs.

## Normative

> [!normative]
> Policy text MUST compile to a deterministic evaluator before any policy is enforced. There is no interpretation at exercise time.

> [!normative]
> Compilation MUST validate the policy against `spec/schemas/chio-policy/v1/policy.schema.json` before producing an evaluator. Schema-invalid policies fail compilation; **partial compilation is forbidden**.

> [!normative]
> Compilation errors MUST be treated as kernel errors (not policy-author errors): the kernel REFUSES to use a policy that didn't compile cleanly. The kernel does NOT fall back to a previous policy automatically — operators MUST explicitly roll back.

> [!normative]
> The compiled evaluator MUST be **pure**: no I/O, no clock reads, no random, no network. All inputs to a verdict are explicit arguments. (Replayability follows from purity.)

> [!normative]
> Every successful compile MUST emit `receipt.policy-compile.<policy-id>` recording: source content hash, compiled artifact hash, kernel version, and the validation verdict.

> [!normative]
> Every policy evaluation MUST emit `receipt.policy-eval.<exercise-id>` recording: matched rule id, verdict, the inputs the verdict depended on (hashed), and the timestamp.

## Why

> [!guard]
> Fail-closed extends across the compile boundary. A policy that won't compile is treated like a kernel that won't boot — the system refuses to run rather than degrade silently.

The decision to make compilation a hard kernel-level failure (rather than a soft "use a fallback policy" graceful degrade) is recorded in [[../episodes/guard-policy-fail-closed]] and reflects three constraints:

1. **Policies are kernel-loaded artifacts.** Treating compile errors as kernel errors keeps the failure mode crisp: the kernel can refuse to boot with a broken policy file, the same way it refuses to boot with a broken config. The alternative ("use the last good policy") creates a covert channel for misbehavior — a kernel could intentionally publish a broken policy to revert to a stale one.
2. **Evaluator purity is the foundation of audit.** A policy that consults the clock or network for its verdict can't be replayed; "the policy said deny at time X" becomes unfalsifiable. Every input to a verdict must be in the receipt.
3. **Two receipt classes (compile + eval) keep the audit trail orthogonal.** Compile-time receipts prove **what policy was loaded**. Eval-time receipts prove **how it ruled**. Mixing them would conflate "the policy" with "the policy's decisions," and both audit questions are needed.

## Implements

- `chio_policy::compiler` — `crates/chio-policy/src/compiler.rs` (the compiler entry point)
- `chio_policy::validate` — `crates/chio-policy/src/validate.rs` (schema validation)
- `chio_policy::evaluate::engine` — `crates/chio-policy/src/evaluate/engine.rs` (the runtime evaluator)
- `chio_policy::evaluate::matchers` — `crates/chio-policy/src/evaluate/matchers.rs` (predicate implementations consumed by the guard pipeline)
- `chio_policy::models` — `crates/chio-policy/src/models.rs` (policy AST types)
- `chio_policy::lib` — `crates/chio-policy/src/lib.rs` (public API)
- Schema: `spec/schemas/chio-policy/v1/policy.schema.json`

## Tested by

- `crates/chio-policy/tests/compiler_validate.rs` — schema validation
- `crates/chio-policy/tests/compiler_purity.rs` — evaluator purity (no I/O, no clock, no random)
- `crates/chio-policy/tests/evaluator_e2e.rs` — full compile → evaluate flow
- `tests/conformance/peers/*/test_policies.*` — SDK conformance

When changing the wire format under `spec/schemas/chio-policy/v1/`, prefer the SDK conformance tests over Rust unit tests.

## Operations

- [[../playbooks/release-qualification#gate-3--policy-compiler-validation]] — release-time validation that the candidate's policy schema accepts cleanly.
- [[guard-pipeline]] — the **consumer** of compiled policies. The relationship is one-way: the policy compiler produces evaluators; the guard pipeline runs them. Compiled artifacts are immutable across guard executions.

## Open questions

- [ ] **Hot reload vs. kernel restart.** Today policy reloads require a kernel restart (so receipt streams cleanly cut over). Hot-reload would reduce latency but complicates the receipt chain — what's the precise compile receipt boundary if the kernel didn't restart? Pending an ADR.
- [ ] **Policy versioning and rollback.** Operators can roll back to a previous policy by re-pointing the kernel at an earlier compiled artifact. Should the rollback itself be receipted? Likely yes — `receipt.policy-rollback` is a candidate. Open for ADR.
- [ ] **Cross-issuer policy composition.** Mirror of cross-issuer revocation: if issuer A delegates to issuer B, can B's policies layer on top of A's? Today: no. Pending ADR alongside the cross-issuer revocation question.

## Staleness

> [!warning-staleness]
> Last validated 2026-05-07. Re-validate against `crates/chio-policy/src/` and the `spec/schemas/chio-policy/v1/` schemas when those crates' major versions bump or when the schema changes.

The [[../_meta/queries/stale-specs|stale-specs query]] flags this when `last-validated:` is 90+ days behind today.

## Graph context

%% kb_neighbors: spec.policy.compiler depth=2 %%

## Lineage

Derived from the seed [[../episodes/guard-policy-fail-closed]] (migrated from arc PR #599's `seeds/graphiti/guard-policy-fail-closed.json` via `make kb-migrate-seeds`). The seed is shared with [[guard-pipeline]] — both specs are Chio-side surfaces of the same architectural commitment to fail-closed everywhere.
