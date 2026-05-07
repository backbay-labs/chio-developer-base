---
id: spec.protocol.wire-format
type: spec
status: accepted
chio-node: Protocol
crate: chio-wire
supersedes: []
related-specs:
  - spec.receipt.commitment
  - spec.sdk.conformance
related-receipts: []
related-guards: []
graphiti-episode: episode.chio-architecture-summary
related-diagrams: []
owners:
  - "@connor"
last-validated: 2026-05-07
---

# Chio protocol wire format

The schema vocabulary, version policy, and breaking-change rules for Chio's wire payloads. The bytes-on-the-wire layer the rest of the protocol stack agrees on.

## Normative

> [!normative]
> All Chio wire payloads MUST validate against a schema under `spec/schemas/chio-wire/v1/<category>/<message>.schema.json`. No payload outside the schema's coverage is permitted.

> [!normative]
> Wire-format schema versions are linear. **`v1` is the current major.** A breaking change requires bumping to `v2` and supporting both during a transition window (window length set by ADR per release cycle).

> [!normative]
> Within a major version, schemas MAY add OPTIONAL fields. **Adding REQUIRED fields, removing or renaming any field, and field-type changes are all breaking** and require a major bump.

> [!normative]
> Every schema file MUST be JSON Schema draft 2020-12. Earlier drafts are not permitted; cross-draft mixing is not permitted.

> [!normative]
> Peers MUST IGNORE unknown OPTIONAL fields gracefully. A peer that errors on an unknown optional field is non-conformant; this is part of [[sdk-conformance|SDK conformance]] (verdict-matrix cell).

> [!normative]
> Vendor-specific extensions MUST use the `x-` field-name prefix. Fields without the prefix are reserved for the standard.

## Why

> [!normative]
> The wire format is the **lowest common denominator** between every Chio peer. If peers disagree about what bytes mean, every higher-level guarantee (capabilities, receipts, guards) becomes meaningless. Schema-validated payloads with explicit versioning are how the protocol stays portable.

The decision to ground the wire format in JSON Schema (rather than Protobuf, Cap'n Proto, or a custom binary format) is recorded in [[../episodes/chio-architecture-summary]] (`spec/PROTOCOL.md` is the cited authoritative source). It reflects three constraints:

1. **Human-readable payloads matter for audit.** Receipts must be inspectable by external verifiers without a special toolchain. JSON satisfies this; binary schemas don't (without an extra decode step that becomes a trust boundary).
2. **Schema-as-data is the audit substrate.** A JSON Schema file IS the spec. Future verifiers can validate against the schema directly without consulting peer code, which closes a class of "the spec says X but the peer does Y" divergence.
3. **Optional-field forward compatibility is the only viable evolution path.** A protocol that breaks every peer on every minor change is unshippable. Optional-fields-only-within-a-major is the discipline that keeps long-tail peers (older SDKs, embedded peers) alive.

## Implements

- `spec/PROTOCOL.md` — the prose protocol document
- `spec/schemas/chio-wire/v1/` — the schema dir (canonical)
- `spec/schemas/chio-wire/v1/receipt/` — receipt-category schemas (see [[receipt-commitment]])
- `spec/schemas/chio-wire/v1/receipt/inclusion-proof.schema.json` — inclusion-proof schema
- `spec/schemas/chio-wire/v1/receipt/checkpoint.schema.json` — checkpoint schema
- `spec/schemas/chio-wire/v1/receipt/README.md` — receipt-category overview

Other categories (capability, exercise, policy, etc.) live as siblings under `v1/`. The schema-dir layout is itself part of the spec — adding a new top-level category requires an ADR.

## Tested by

- `crates/chio-mcp-adapter/tests/integration_smoke.rs` — exercises wire format end-to-end
- `integrations/mcp-adapter/tests/transport_round_trip.rs` — round-trip every category
- `crates/chio-conformance/verdict_matrix/tests/verdict_matrix_cross_language.rs` — cross-language wire agreement
- `tests/conformance/peers/python/` and `tests/conformance/peers/js/` — peer-level wire compliance

When changing schemas under `spec/schemas/chio-wire/v1/`, the cross-language verdict-matrix tests are the only ones that catch peer-to-peer divergence. Single-language unit tests are insufficient.

## Operations

- [[../playbooks/release-qualification#gate-1--conformance-suite]] — release-time wire-format validation
- [[../playbooks/release-qualification#gate-4--receipt-compliance-evidence]] — wire-format receipts must be inclusion-proof checkable

## Open questions

- [ ] **v2 transition policy.** When does the project plan its first major bump? Whatever the answer, the transition window length and the dual-support cost should be ADR-defined before v2 is announced.
- [ ] **Schema-validation enforcement at the kernel boundary.** Do kernels validate inbound payloads against the schemas, or trust the adapter? Today: trust the adapter. Open whether kernels should re-validate as defense-in-depth.
- [ ] **Vendor-extension governance.** The `x-` prefix lets peers add fields without coordination. What's the policy when an `x-` field becomes broadly adopted? Promote to a standard field in the next major? Pending an ADR.

## Staleness

> [!warning-staleness]
> Last validated 2026-05-07. Re-validate against `spec/PROTOCOL.md` and the actual schemas under `spec/schemas/chio-wire/v1/` whenever the schema dir adds or modifies a category.

The [[../_meta/queries/stale-specs|stale-specs query]] flags this when `last-validated:` is 90+ days behind today.

## Graph context

%% kb_neighbors: spec.protocol.wire-format depth=2 %%

## Lineage

Derived from the architecture-summary seed [[../episodes/chio-architecture-summary]], which lists `spec/PROTOCOL.md` as authoritative. This spec captures the wire-format slice of that broader protocol surface — the bytes layer that every other Chio spec ([[capability-revocation]], [[receipt-commitment]], [[guard-pipeline]], [[policy-compiler]], [[sdk-conformance]]) ultimately serializes through.
