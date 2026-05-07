---
id: playbooks.release-qualification
type: playbook
status: draft
owners: []
related-spec:
  - spec.protocol
  - spec.receipt.commitment
  - spec.release-truth-boundary
related-receipts:
  - receipt.release-qualification
related-diagrams:
  - "[[_meta/diagrams/release-qualification-flow]]"
last-validated: 2026-05-07
---

# Release qualification

> How a Chio release candidate moves from `main` to a signed release. Every gate produces a receipt; the release qualification record is itself a signed artifact.

## When to run this

Whenever a release candidate (`rc-N` tag) is cut. Not for normal merges to `main`.

## Pre-flight (before cutting `rc-N`)

- [ ] All `main` branch CI green for at least 24 hours.
- [ ] No open ADRs marked `proposed` whose owners include @release-shepherd.
- [ ] [[_meta/queries/stale-specs|Stale-specs]] dashboard shows zero specs >180 days unvalidated. (>90 is yellow; >180 blocks a release.)
- [ ] `make kb-eval` overall A on retrieval AND outcome evals not regressed.

## Gate 1 — Conformance suite

For each SDK peer (Python, JS, …):

```sh
cd ../arc
git checkout rc-N
cd tests/conformance/peers/python && make test
cd ../js && make test
```

Verdict matrix populates at `docs/conformance/verdict-matrix.md`. Every cell MUST be green or explicitly waived (with an ADR linking the waiver).

**Receipt produced:** `receipt.conformance.<peer>.rc-N`. Stored in arc's release artifacts directory.

If any cell fails: stop. Either the failure is a real regression (block the release) or a known waiver (file an ADR before continuing).

## Gate 2 — Guard pipeline

Run the production guard pipeline against the candidate kernel. Every guard in `crates/chio-guards/src/` must evaluate fail-closed under stress:

```sh
cd ../arc
cargo test -p chio-guards --release
cargo test -p chio-kernel --release --test guard_integration
```

**Receipt produced:** `receipt.guards.rc-N`.

The seed [[episodes/guard-policy-fail-closed]] is authoritative on what "fail-closed" means here. If you're not sure whether a behavior is fail-closed, the answer is no.

## Gate 3 — Policy compiler validation

The policy compiler must accept the candidate's policy schema with no fail-closed regressions:

```sh
cd ../arc
cargo test -p chio-policy --release -- --include-ignored
```

**Receipt produced:** `receipt.policy-compiler.rc-N`.

A fail-closed regression here is a hard block — fail-closed is the entire point of the policy compiler. See [[episodes/guard-policy-fail-closed]].

## Gate 4 — Receipt compliance evidence

Verify that all gate-produced receipts are inclusion-proof-checkable against a published checkpoint:

```sh
make kb-verify --receipts arc/release/rc-N/receipts/
```

> **Phase 2B:** this `make` target is currently a Phase 2B blocker. Until then, run the existing arc receipt-verify CLI directly: `cd ../arc && cargo run -p chio-receipts -- verify rc-N/receipts/*.json`.

**Receipt produced:** `receipt.evidence.rc-N`.

## Gate 5 — Sign-off

Two named owners (one platform, one cluster) sign the qualification record. The record is a manifest of the prior receipts plus a free-form risk summary.

```sh
cd ../arc
./scripts/release/sign-qualification --tag rc-N --signers @owner1,@owner2
```

**Receipt produced:** `receipt.qualification.rc-N`. This is the artifact that travels with the release.

## Roll-back path

If a gate fails AFTER sign-off (e.g., a downstream cluster reports a regression in the first 48 hours):

1. **Do not** delete or alter the existing receipts. They are append-only by design.
2. Cut a new candidate `rc-N+1` from `main` with the fix.
3. File `receipt.rollback.rc-N` documenting why `rc-N` is being abandoned. This is itself a signed artifact.
4. Re-run all gates against `rc-N+1`. There are no shortcuts; gate 1–5 run from scratch.

## The release-truth boundary (read this every time)

The seed [[episodes/release-truth-boundary]] establishes a hard rule:

> **Do not infer release truth from Graphiti memory.**

The release qualification record is built ONLY from CI artifacts, conformance test results, and signed receipts. The KB is a retrieval aid for finding the right specs and tests; it is never the authority for whether a gate passed.

If you find yourself reading a Graphiti episode to decide whether a gate passed: stop, go to the actual receipt or test result.

## Diagram

[[_meta/diagrams/release-qualification-flow|See the release qualification flow diagram]] for the visual version of this playbook. PMs will screenshot it; keep its gate labels readable when the diagram lands.

## Open questions

- [ ] At Phase 2B, does signed retrieval inside `kb-verify` replace the manual `cargo run -p chio-receipts -- verify` step? Likely yes.
- [ ] Should Gate 1 require the SDK conformance suite to also produce a `receipt.conformance.recall` outcome eval result above 0.85? Defer to ADR after Phase 0 baselines are in.
