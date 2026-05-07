---
id: queries.open-adrs
type: query
status: published
---

# Open ADRs

```dataview
TABLE WITHOUT ID
  file.link as ADR,
  status,
  owners,
  date as "Filed"
FROM "decisions"
WHERE status = "proposed"
SORT date ASC
```

## Why this exists

ADRs decide things. An ADR sitting in `proposed` for too long is either (a) an open question nobody owns, or (b) a decision that's already been made informally and should be flipped to `accepted` or filed as superseded.

This query is included in the morning brief (see `_meta/templates/daily-note.md`).

## Pending vs proposed

A note on status vocabulary used in this repo:

- `proposed` — drafted, awaiting review and acceptance.
- `accepted` — adopted; immutable except via supersession.
- `superseded` — replaced by a later ADR; kept for history. The replacing ADR's frontmatter `supersedes:` lists this one.
- `pending` — used by a few placeholder ADRs (e.g., [ADR-0002](../../decisions/ADR-0002-phase-0-baselines.md)) where the structure is filed but the content depends on future measurements. Not the same as `proposed`.

The query above filters for `proposed` only. Pending ADRs surface separately:

```dataview
TABLE WITHOUT ID
  file.link as ADR,
  date as "Filed",
  owners
FROM "decisions"
WHERE status = "pending"
SORT date ASC
```

## Stale-proposed (filed more than 14 days ago)

```dataview
TABLE WITHOUT ID
  file.link as ADR,
  date as "Filed",
  owners
FROM "decisions"
WHERE status = "proposed"
  AND date(date) < date(today) - dur(14 days)
SORT date ASC
```

A `proposed` ADR older than 14 days is a yellow flag — either the discussion has stalled or the decision happened informally and the ADR was never updated. Either is fixable; both deserve attention.
