---
id: playbooks.governed-agent-memory
type: playbook
status: active
title: "Governed Agent Memory"
owners:
  - "@connor"
---

# Governed Agent Memory

## Purpose

Governed memory captures durable, high-signal agent lessons without letting an agent write directly to Graphiti. The only durable write is a vault episode under `vault/episodes/session-<id>.md`; vault-sync remains the only writer to derived graph stores.

## Tools

- `kb_memory_add` appends a signed memory entry to the current session episode.
- `kb_memory_query` searches session episodes.
- `kb_memory_revoke` appends a strikethrough revocation entry instead of deleting history.

Every entry includes a signed receipt and `receipt_hash`. If a prior receipt exists, pass `parent_receipt_hash` to preserve the chain.

## Hook

`ops/hooks/session-memory.sh <scratchpad>` mirrors a scratchpad snapshot into governed memory. It is intentionally explicit: run it from the repo root or set `CHIO_DEV_REPO` so the tool writes to this vault.

## Kill Criterion

Run this as an 8-week experiment. Kill or redesign governed memory if, after 8 weeks, either:

- fewer than three retrieved memories materially improve a real fix/review, or
- more than 10% of queried memories are stale enough to require revocation before use.

If the experiment is killed, keep existing episodes as historical audit records and disable the hook rather than deleting memory files.
