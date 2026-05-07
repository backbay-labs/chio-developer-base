---
id: daily.<% tp.date.now("YYYY-MM-DD") %>
type: daily
date: <% tp.date.now("YYYY-MM-DD") %>
status: open
---

# <% tp.date.now("dddd, MMMM D, YYYY") %>

## Morning brief

### Episodes promoted in last 24h
```dataview
TABLE file.mtime as "Promoted"
FROM "episodes"
WHERE date(file.mtime) >= date(today) - dur(1 day)
SORT file.mtime DESC
```

### My open ADRs
```dataview
TABLE status, date as "Filed"
FROM "decisions"
WHERE status = "proposed" AND contains(owners, "<% tp.user.handle() %>")
SORT date ASC
```

### Stale specs I own (>60 days since last-validated)
```dataview
TABLE last-validated
FROM "spec"
WHERE contains(owners, "<% tp.user.handle() %>")
  AND (last-validated = null OR date(last-validated) < date(today) - dur(60 days))
SORT last-validated ASC
```

> Org-wide views (not filtered to me): [[../_meta/queries/open-adrs]], [[../_meta/queries/stale-specs]], [[../_meta/queries/unowned-capabilities]].

### Conformance failures (live)
%% kb_impact: HEAD~1..HEAD %%

## Working log
- 

## What I learned
> If non-empty, the `episode-promoter` plugin (Phase 3) will offer to convert this section into a Graphiti episode with a confirmation modal.

