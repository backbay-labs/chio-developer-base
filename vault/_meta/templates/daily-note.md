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

### ADRs awaiting review
```dataview
TABLE status, owners
FROM "decisions"
WHERE status = "proposed"
SORT file.name ASC
```

### Stale specs (>60 days since last-validated)
```dataview
TABLE last-validated, owners
FROM "spec"
WHERE last-validated = null OR date(last-validated) < date(today) - dur(60 days)
SORT last-validated ASC
LIMIT 5
```

### Conformance failures (live)
%% kb_impact: HEAD~1..HEAD %%

## Working log
- 

## What I learned
> If non-empty, the `episode-promoter` plugin (Phase 3) will offer to convert this section into a Graphiti episode with a confirmation modal.

