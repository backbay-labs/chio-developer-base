---
id: spec.capability.revocation
type: spec
status: accepted
chio-node: Capability
crate: chio-kernel
supersedes: []
related-receipts:
  - receipt.revoke-v1
related-guards:
  - guard.revocation-window
graphiti-episode: episode.capability-revocation-architecture
owners:
  - "@connor"
last-validated: 2026-05-07
---

# Capability revocation

A canonical worked example for the spec layout. Mirrors the structure [PLAN.md](../../PLAN.md#example-vaultspeccapability-revocationmd) cites and exercises every chio-callout the snippet ships.

## Normative

> [!normative]
> A capability MUST be revocable by its issuer at any time before its expiration.

> [!normative]
> The revocation MUST take effect within the **revocation window** (default 5 seconds; configurable per issuer in `crates/chio-kernel/src/revocation_store.rs`).

> [!normative]
> Every revocation MUST emit three receipts:
> - `receipt.revoke-v1.<CAP_ID>.write` — issuer-signed entry in the revocation list
> - `receipt.revoke-v1.<CAP_ID>.guard` — first post-revocation exercise rejected
> - `receipt.revoke-v1.<CAP_ID>.audit` — entry included in the next checkpoint
>
> See [[../playbooks/revoke-a-capability#what-the-receipts-say]] for the full table.

> [!normative]
> A delegated capability MAY be revoked by the original issuer regardless of delegation chain depth, provided the revocation entry is signed by the issuer's key.

> [!normative]
> Cross-issuer revocation (issuer C revoking a capability minted by issuer A) is NOT supported in v1. See [Open questions](#open-questions).

## Why

> [!receipt]
> The receipt obligation is what makes revocation auditable. Without the three-receipt rule, a kernel could silently drop revocations and no external verifier would notice. This is also why revocation lives inside capability validation, not in a separate code path.

The decision to make revocation a first-class part of capability validation (rather than an isolated product feature) is recorded in [[../episodes/capability-revocation-architecture]] and reflects three constraints from that seed:

1. **Revocation is part of capability validation.** Treating it as a separate code path led to fail-open bugs in pre-1.0 sketches.
2. **Receipt evidence is non-optional.** Revocation that doesn't emit auditable receipts is a covert channel for kernel misbehavior.
3. **The revocation oracle owns the test surface.** Property tests in `crates/chio-revocation-oracle/` are the authoritative behavioral spec; this document captures what they're testing for.

## Implements

The normative claims above are realized in:

- `chio_kernel::kernel::delegation` — delegation-and-revocation entry points
- `chio_kernel::revocation_store` — the revocation list (RVL) writer
- `chio_core_types::capability` — capability + grant types
- `chio_kernel_core::capability_verify` — the validation path that consults the RVL

> [!guard]
> `guard.revocation-window` enforces the 5-second window. It evaluates **fail-closed under partition**: if the kernel can't reach the latest RVL version, it rejects the exercise rather than allowing a stale view. Implementation in `crates/chio-guards/src/revocation_window.rs`.

## Tested by

- `crates/chio-revocation-oracle/tests/swarm_revocation_e2e.rs` — end-to-end multi-kernel propagation
- `crates/chio-revocation-oracle/tests/receipt_chain_proof.rs` — three-receipt obligation
- `crates/chio-revocation-oracle/tests/property_oracle.rs` — property tests for fail-closed under partition
- `crates/chio-kernel-core/tests/revocation_view_concurrency.rs` — concurrent reader/writer

When changing this spec or the implementing code, **prefer the revocation-oracle test set** over broad semantic searches. The seed [[../episodes/capability-revocation-architecture]] makes this explicit as a constraint:

> Prefer revocation-oracle tests before broad semantic test matches when the query includes revocation.

## Operations

- [[../playbooks/revoke-a-capability]] — how an operator actually performs a revocation, step by step.

## Open questions

- [ ] **Cross-issuer revocation.** When issuer A delegates a capability to grantee B, can issuer C (who has trust-graph standing) revoke it? Today: no. Pending an ADR on whether the trust graph should resolve this. Tracked in [[../episodes/capability-revocation-architecture]] under "constraints".
- [ ] **Revocation propagation under partition.** What's the SLA for RVL propagation across kernel replicas? `property_oracle.rs` exercises behavior but no published bound. A future amendment to this spec should fix this.
- [ ] **Lightweight revocation for short-TTL capabilities.** Is the three-receipt obligation overkill for capabilities with TTL < revocation window? Probably yes. Open for an ADR.

## Staleness

> [!warning-staleness]
> Last validated 2026-05-07. Owners must re-read this spec against `crates/chio-kernel/` and `crates/chio-revocation-oracle/` and bump `last-validated:` when they confirm it still matches reality.

The [[../_meta/queries/stale-specs|stale-specs query]] flags this note when `last-validated:` falls 90+ days behind today. The release-qualification playbook ([[../playbooks/release-qualification#pre-flight-before-cutting-rc-n]]) treats >180 days as a release blocker.

## Graph context

The KB graph traversal will surface structurally adjacent code, specs, and tests. Live in Phase 1+:

%% kb_neighbors: spec.capability.revocation depth=2 %%

Until the bridge plugin renders this inline, equivalent CLI:

```sh
curl -s http://localhost:8111/mcp/ \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"kb_neighbors",
                 "arguments":{"entity":"spec.capability.revocation","depth":2,"limit":20}}}' \
  | jq '.result.content'
```

## Lineage

This spec is derived from the seed [[../episodes/capability-revocation-architecture]] (migrated from arc PR #599's `seeds/graphiti/capability-revocation-architecture.json` via `make kb-migrate-seeds`). The seed is the temporal-memory record of *why this spec exists*; this note is the normative *what it asserts*.
