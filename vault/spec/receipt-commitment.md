---
id: spec.receipt.commitment
type: spec
status: accepted
chio-node: Receipt
crate: chio-core-types
supersedes: []
related-specs:
  - spec.capability.revocation
related-receipts:
  - receipt.checkpoint
related-guards: []
graphiti-episode: episode.receipt-compliance-evidence
related-diagrams:
  - "[[../_meta/diagrams/receipt-commitment-chain]]"
owners:
  - "@connor"
last-validated: 2026-05-07
---

# Receipt commitment

What gets signed, what gets hashed, what's in the Merkle tree, and how a Chio receipt is verified offline.

## Normative

> [!normative]
> Every Chio decision event (capability mint, delegation, exercise, revocation, guard verdict, policy evaluation) MUST produce a receipt as a Merkle leaf.

> [!normative]
> Receipts MUST be batched into blocks. Each block root MUST be signed by the kernel's signing key.

> [!normative]
> Block roots MUST accumulate into a checkpoint at issuer-defined cadence. The checkpoint root MUST be published to a public log.

> [!normative]
> An external verifier MUST be able to resolve a leaf to a published checkpoint root using only:
>
> 1. The receipt itself.
> 2. The Merkle path from leaf to block root.
> 3. The block root's kernel signature.
> 4. The path from block root to checkpoint root.
> 5. The published checkpoint root.
>
> No interaction with the originating kernel is required for verification.

> [!normative]
> Checkpoints MUST be **append-only**. A kernel that produces a checkpoint diverging from prior checkpoints in the same chain is a fork — the wire schema MUST flag this and external verifiers MUST reject the divergent chain.

## Why

> [!receipt]
> The point of the commitment chain is **offline verifiability**. Anyone holding a receipt and a published checkpoint should be able to verify the receipt without contacting the kernel that produced it. If verification requires the kernel, the kernel can lie.

The decision to use a Merkle commitment chain (rather than per-receipt signatures or a streaming log) is recorded in [[../episodes/receipt-compliance-evidence]] and reflects three constraints:

1. **Verification cost matters.** Per-receipt signatures don't aggregate; a verifier with N receipts pays O(N) signature checks. Merkle aggregation is O(log N) per receipt against a single signed root.
2. **Audit lag is bounded by checkpoint cadence.** The choice of cadence trades freshness for batch efficiency. The spec doesn't fix the cadence, but external verifiers SHOULD know what cadence the issuer they're verifying uses.
3. **Forks must be detectable.** Append-only is the property that makes auditing meaningful. A signed chain that allows rewriting is not a chain.

## Implements

- `chio_core_types::receipt::checkpoint` — checkpoint construction (`crates/core/chio-core-types/src/receipt/checkpoint.rs`)
- `chio_core_types::merkle` — Merkle path construction (`crates/core/chio-core-types/src/merkle.rs`)
- `chio_core_types::receipt::signing` — receipt signing (`crates/core/chio-core-types/src/receipt/signing.rs`)
- `chio_eval_receipt` — offline eval-report bundle verifier (`crates/sdk/chio-eval-receipt/`)
- Schema: `spec/schemas/chio-wire/v1/receipt/inclusion-proof.schema.json`
- Schema: `spec/schemas/chio-wire/v1/receipt/checkpoint.schema.json`
- Schema: `spec/schemas/chio-wire/v1/receipt/README.md`

## Tested by

- `crates/core/chio-core-types/src/receipt/tests.rs` — receipt unit tests
- `crates/sdk/chio-eval-receipt/` — eval-report bundle verification
- `tests/conformance/peers/python/test_receipts.py` — SDK conformance (Python)
- `tests/conformance/peers/js/test_receipts.test.ts` — SDK conformance (JS/TS)
- `docs/conformance/verdict-matrix.md` — cross-peer pass/fail snapshot

When changing the wire format under `spec/schemas/chio-wire/v1/receipt/`, **prefer the SDK conformance tests** over Rust unit tests — the conformance suite catches divergence between peers that internal tests can't see.

## Operations

- [[../playbooks/release-qualification#gate-4--receipt-compliance-evidence]] — how the release-qualification gate verifies receipts.
- [[../playbooks/revoke-a-capability#what-the-receipts-say]] — how revocation produces three receipts and what each commits.

## Open questions

- [ ] **Checkpoint publication transport.** The spec says checkpoint roots MUST be published; it doesn't say *where*. Today: kernel-internal log + REST endpoint. Future: a notary witness chain? Open for ADR.
- [ ] **Cadence as a per-issuer parameter.** Issuers configure cadence locally. Should checkpoints carry their cadence in their wire format so verifiers don't need out-of-band knowledge? Probably yes — pending an ADR.
- [ ] **Pruning.** Long-running issuers accumulate enormous receipt logs. The spec is silent on retention. Pending an ADR on what's lossy and what's preserved-forever.

## Staleness

> [!warning-staleness]
> Last validated 2026-07-08. The wire schemas under `spec/schemas/chio-wire/v1/receipt/` are the canonical surface — re-read this spec against them and against `crates/core/chio-core-types/src/receipt/` whenever the schema bumps.

The [[../_meta/queries/stale-specs|stale-specs query]] flags this when `last-validated:` is 90+ days behind today.

## Diagram

[[../_meta/diagrams/receipt-commitment-chain|See the receipt commitment chain diagram]] — the visual form of this spec.

## Graph context

%% kb_neighbors: spec.receipt.commitment depth=2 %%

## Lineage

Derived from the seed [[../episodes/receipt-compliance-evidence]] (migrated from arc PR #599's `seeds/graphiti/receipt-compliance-evidence.json` via `make kb-migrate-seeds`). The seed is the temporal-memory record of *why* the commitment chain looks like this; this note is the normative *what* it asserts.
