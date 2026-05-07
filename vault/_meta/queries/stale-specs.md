---
id: queries.stale-specs
type: query
status: published
---

# Stale specs (no `last-validated` bump in 90+ days)

```dataview
TABLE last-validated, owners, file.mtime as "Edited"
FROM "spec"
WHERE status = "accepted"
  AND (last-validated = null OR date(last-validated) < date(today) - dur(90 days))
SORT last-validated ASC
```

## Why this exists

The skeptic's biggest objection to the vault is rot. A spec that hasn't had its `last-validated` field bumped in 90+ days is presumed stale until re-validated against the current code path. This query is the primary defense.

A spec is "validated" when its owner re-reads it against the current code, confirms it's still accurate, and bumps `last-validated` to today's date. If the spec is no longer accurate, the owner either updates it or marks `status: superseded` and writes the replacement spec.

## Daily-note integration

This query also runs (with a 60-day window and `LIMIT 5`) in the morning brief inside `_meta/templates/daily-note.md`. Any owned stale spec shows up first thing in the morning, before the dev opens any other tool.

## Other useful spec dashboards

```dataview
TABLE WITHOUT ID
  file.link as Spec,
  status,
  owners,
  length(filter(file.outlinks, (l) => contains(string(l), "decisions/"))) as "Linked ADRs"
FROM "spec"
WHERE status != "superseded"
SORT file.name ASC
```

```dataview
LIST file.link
FROM "spec"
WHERE status = "accepted" AND length(file.outlinks) = 0
```

The second query catches accepted specs with no outgoing links — usually a sign the spec is documenting in isolation rather than as part of the protocol/standards/conformance graph.
