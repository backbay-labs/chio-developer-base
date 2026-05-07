---
id: meta.spec-readme
type: meta
---

# `vault/spec/`

Normative protocol notes. One file per Chio concept.

## What goes here

- Specs for Chio protocol concepts: capabilities, receipts, guards, policies, protocol, standards.
- Each spec note states what MUST / SHOULD / MAY be true in RFC 2119 vocabulary.
- Each spec links to the ADR(s) that motivate it and to the implementation symbols in `crates/`.

## What does NOT go here

- Implementation notes — those go in [[../episodes|episodes]] if architectural, or in the relevant crate's `docs/` if implementation-detail.
- Drafts of RFCs to upstream projects — those are in arc.
- API reference — generated from rustdoc; link out, don't duplicate.

## How to add a spec

1. Use the [[../_meta/templates/spec|spec template]].
2. Set the `chio-node:` frontmatter to one of: `Capability` | `Receipt` | `Guard` | `Policy` | `Protocol` | `Standard`.
3. Pre-fill `last-validated:` with today's date; bump it whenever you re-validate against current code.
4. Link to at least one ADR under `## Why`. A spec without an ADR motivating it has no constituency.

## Staleness

The [[../_meta/queries/stale-specs|stale-specs query]] flags any spec whose `last-validated` is more than 90 days old. Owners get their stale specs in the morning brief.

A spec that hasn't been re-validated in **180+ days** is a release blocker per [[../playbooks/release-qualification]] pre-flight.

## The implements bridge

The `## Implements` section in a spec note is the bridge from normative prose to executable code. Conventions:

- Link to symbols by stable identifier: `chio-core::cap::revoke` (crate path + symbol), not file path.
- Link to conformance tests under `tests/conformance/` so the SDK suite is the executable proof.
- The `kb_neighbors` MCP call inside the spec template is a live retrieval that surfaces structurally adjacent code; keep it as documentation that the spec is grounded.

## All worked specs

```dataview
TABLE WITHOUT ID
  file.link as Spec,
  chio-node,
  status,
  crate,
  last-validated
FROM "vault/spec"
WHERE type = "spec"
SORT chio-node ASC
```

## By chio-node label

```dataview
TABLE WITHOUT ID
  rows.file.link as Specs,
  length(rows) as Count
FROM "vault/spec"
WHERE type = "spec"
GROUP BY chio-node
SORT chio-node ASC
```

## Stale specs (>90 days unvalidated)

```dataview
LIST file.link
FROM "vault/spec"
WHERE type = "spec"
  AND status = "accepted"
  AND (last-validated = null OR date(last-validated) < date(today) - dur(90 days))
SORT last-validated ASC
```

> See [[../_meta/queries/stale-specs]] for the canonical org-wide stale dashboard, [[../_meta/queries/unowned-capabilities]] for unowned spec nodes, and individual spec note headers for per-note staleness via the [`kb-staleness-badge`](../../.obsidian/plugins/kb-staleness-badge/) plugin.
