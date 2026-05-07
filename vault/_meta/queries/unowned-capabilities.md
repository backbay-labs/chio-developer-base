---
id: queries.unowned-capabilities
type: query
status: published
---

# Unowned capabilities (and other unowned spec nodes)

```dataview
TABLE WITHOUT ID
  file.link as Spec,
  chio-node,
  status,
  last-validated
FROM "spec"
WHERE chio-node = "Capability"
  AND (owners = null OR length(owners) = 0)
SORT last-validated ASC
```

## Why this exists

Every Chio capability concept should have a named human owner. An unowned capability spec is a contract nobody is on the hook for — exactly the place where drift happens silently.

This query is included in the morning brief (see `_meta/templates/daily-note.md`) but generalized to any unowned spec node, not just capabilities. The widened version:

```dataview
TABLE WITHOUT ID
  file.link as Spec,
  chio-node,
  status,
  last-validated
FROM "spec"
WHERE status = "accepted"
  AND (owners = null OR length(owners) = 0)
SORT chio-node ASC, last-validated ASC
```

## Resolution paths

When this dashboard is non-empty, exactly one of these happens:

1. **Adopt** — a willing owner adds their handle to `owners:` and bumps `last-validated:` to today.
2. **Retire** — if the spec is no longer authoritative, mark `status: superseded` and write the replacement (or just remove if it was a draft).
3. **Defer** — if neither, file an ADR explaining why this concept is currently un-owned. An ADR is preferable to silent drift.

A spec that sits unowned for >30 days without an ADR explanation is a release blocker, same as the 180-day staleness rule.

## Counts at a glance

```dataview
TABLE WITHOUT ID
  rows.chio-node as "Node type",
  length(rows) as Count
FROM "spec"
WHERE (owners = null OR length(owners) = 0) AND status = "accepted"
GROUP BY chio-node
SORT Count DESC
```

## See also

- [[stale-specs]] — orthogonal axis: specs with stale `last-validated:`
- [[../../spec/_README]] — spec authoring rules
