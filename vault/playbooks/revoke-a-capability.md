---
id: playbooks.revoke-a-capability
type: playbook
status: draft
owners: []
related-spec:
  - spec.capability.revocation
  - spec.capability.lifecycle
related-receipts:
  - receipt.revoke-v1
related-guards:
  - guard.revocation-window
related-diagrams:
  - "[[_meta/diagrams/capability-lifecycle]]"
last-validated: 2026-05-07
---

# Revoke a capability

> How to revoke a Chio capability and prove the revocation was honored. Covers single-issuer revocation today; cross-issuer revocation is open (see "Open questions" at bottom).

## When to revoke

A capability MUST be revoked when:

- Its private key is suspected compromised.
- The grantee's authorization has changed (off-boarding, scope reduction, breach).
- An expiration was set too long and a tighter bound is required.

A capability SHOULD NOT be revoked merely because:

- A new version of the same scope is being issued. Issue the new one with attenuation; let the old one expire naturally.
- A holder is "probably done with it." Revocation has cost (RVL writes, agent retries); don't revoke speculatively.

## Pre-flight checks

- [ ] You have the issuer's signing key OR you are the named delegate authorized to revoke for this issuer.
- [ ] You know the capability ID (the stable, publicly-quotable identifier from its receipt — not the holder's local handle).
- [ ] You know the *reason* (compromise / scope change / expiry-tightening). Goes into the revocation record.

## The revocation flow

The authoritative code path lives in arc:

- `crates/chio-kernel/src/kernel/delegation.rs` — delegation/revocation entry points
- `crates/chio-kernel/src/revocation_store.rs` — the revocation list (RVL) writer
- `crates/chio-core-types/src/capability.rs` — capability + grant types
- `crates/chio-kernel-core/src/capability_verify.rs` — the validation path that consults the RVL

See [[episodes/capability-revocation-architecture]] for the architectural rationale.

### Step 1 — Record the revocation

```sh
cd ../arc
cargo run -p chio-cli -- capability revoke \
    --capability-id <CAP_ID> \
    --reason <COMPROMISE|SCOPE_CHANGE|EXPIRY_TIGHTEN> \
    --signing-key <KEY_PATH>
```

This writes a new entry to the revocation_store and bumps the RVL version. The kernel emits `receipt.revoke-v1`.

> The signing key MUST be the issuer's. Delegated revocation requires `--delegate-grant` pointing to a capability that was minted with `revoke:*` scope. If you don't have that grant, this command is the wrong path — see "Cross-issuer revocation" below.

### Step 2 — Verify the RVL update propagated

```sh
cd ../arc
cargo run -p chio-cli -- capability status --capability-id <CAP_ID>
```

Expected output: `revoked: true, rvl_version: <NEW>, revoked_at: <ISO8601>`.

If `revoked: false`: the revocation_store write failed (check kernel logs) or you're querying a kernel that hasn't picked up the new RVL version yet.

### Step 3 — Confirm the guard rejects on next exercise

The `guard.revocation-window` guard consults the RVL on every capability exercise. To confirm rejection with a real receipt:

```sh
cd ../arc
cargo test -p chio-revocation-oracle --test swarm_revocation_e2e
```

This produces `receipt.revoke-v1.<CAP_ID>` showing the kernel rejected the next exercise attempt against this capability.

## What the receipts say

A successful revocation produces three receipts:

| Receipt | Emitted by | Says |
| ------- | ---------- | ---- |
| `receipt.revoke-v1.<CAP_ID>.write` | revocation_store | The issuer signed a revocation entry at RVL version N. |
| `receipt.revoke-v1.<CAP_ID>.guard` | guard.revocation-window | The first post-revocation exercise was rejected. |
| `receipt.revoke-v1.<CAP_ID>.audit` | kernel evaluator | The revocation entry was included in the next checkpoint. |

All three should appear in the receipt log within the revocation window (default 5s, configurable per issuer). If any is missing after 60s: file an incident; the RVL may have lost an entry.

## Test coverage

Authoritative tests for revocation behavior (run these when changing the revocation flow):

- `crates/chio-revocation-oracle/tests/swarm_revocation_e2e.rs`
- `crates/chio-revocation-oracle/tests/receipt_chain_proof.rs`
- `crates/chio-revocation-oracle/tests/property_oracle.rs`
- `crates/chio-kernel-core/tests/revocation_view_concurrency.rs`

Per [[episodes/capability-revocation-architecture]]: prefer `revocation-oracle` tests before broad semantic test matches when the query includes "revocation."

## Common mistakes

- **Treating revocation as an isolated feature.** It's part of capability validation and receipt evidence. A revocation without its three receipts is incomplete, not partial.
- **Inferring revocation status from Graphiti memory.** The seed [[episodes/release-truth-boundary]] is explicit: do not infer release/state truth from Graphiti. Query the RVL directly via `chio-cli capability status`.
- **Revoking a capability when narrowing was the right tool.** If the grantee should still have *some* access at lower scope, mint a narrowed capability and let the old one expire — don't revoke and re-issue.
- **Forgetting that revocation is signed by the issuer.** A revocation written without a valid signing key fails at `revocation_store::write`; the receipt is never emitted. If you don't see the receipt, you may not have actually revoked anything.

## Diagram

[[_meta/diagrams/capability-lifecycle|See the capability lifecycle diagram]] for where revocation fits in the state machine.

## Open questions

- [ ] **Cross-issuer revocation.** When issuer A delegates a capability to grantee B, can issuer C (who has trust-graph standing) revoke it? Today: no. Pending ADR on whether the trust graph should resolve this. Tracked in [[episodes/capability-revocation-architecture]] under "constraints."
- [ ] **Revocation propagation under partition.** What's the SLA for RVL propagation across kernel replicas? Property test exists (`property_oracle.rs`) but no published bound. Consider a spec note.
