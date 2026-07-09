---
id: meta.conformance.kb-mcp
type: spec
status: draft
title: "KB MCP Conformance Peer"
owners:
  - "@connor"
---

# KB MCP Conformance Peer

## Wire Contract

The KB peer is an MCP peer whose device under test is the Chio KB gateway. A conforming response:

- is a JSON object,
- includes `status`, `tool`, and tool-specific payload fields,
- includes `receipt` for retrieval-like tools,
- verifies offline with `chio-dev verify <response.json>`,
- rejects a semantically mutated response with the original receipt.

## Initial Verdict Cell

`receipt-checkpoint-inclusion.yml` defines the first cell: a retrieval response must include a receipt with `index_snapshot`, `response_hash`, `signature`, and `parent_receipt_hash` support. The cell passes only when the original response verifies and the tampered response fails.

## Runnable locally (this repo)

```bash
# Script
python3 ops/ci/run_kb_peer_cell.py

# Pytest
cd /Users/connor/Medica/backbay/standalone/chio-developer-base
PYTHONPATH=kb-engine:ops/ci python3 -m pytest vault/_meta/conformance/kb-mcp/test_receipt_checkpoint_cell.py -q
```

## Arc dual-CI (follow-up — human / arc PR)

Mirror this fixture under `arc/tests/conformance/peers/kb-mcp/` and wire a
shared red-test so a wire-format break fails both repos on the same commit.
That cannot complete without an arc PR; local cell green is the Wave 6 floor
on this side.
