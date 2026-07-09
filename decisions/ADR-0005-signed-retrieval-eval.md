---
id: decisions.ADR-0005
type: adr
status: proposed
date: 2026-07-08
date-accepted: TBD
title: "Signed-retrieval outcome eval"
owners:
  - "@connor"
supersedes: []
related:
  - decisions.ADR-0000
  - decisions.ADR-0002
---

# ADR-0005 — Signed-retrieval outcome eval

- **Status:** Proposed
- **Date filed:** 2026-07-08
- **Date accepted:** TBD
- **Owners:** @connor
- **Related:** [ADR-0000](ADR-0000-charter.md), [ADR-0002](ADR-0002-phase-0-baselines.md), [`chio-pack/eval/outcomes.yml`](../chio-pack/eval/outcomes.yml)

## Context

Wave 4A makes retrieval self-evidencing: every retrieval-like `kb_*` response should be verifiable offline by `chio-dev verify`. This deserves an outcome eval because it is a user-visible trust claim, not just a unit-level signing helper.

The eval must stay pack-neutral at the engine layer. `kb-engine` defines `RetrievalReceipt`, `Signer`, `Verifier`, and the development self-signed implementation. `chio-pack` decides which tool responses are retrieval responses and wraps them at the registrar/gateway boundary.

## Decision

Add a `signed-retrieval` outcome eval after this ADR exists. The eval measures:

- `verifiable_fraction`: fraction of sampled retrieval responses for which `chio-dev verify <response.json>` exits 0.
- `tamper_rejection_fraction`: fraction of intentionally mutated sampled responses for which verification exits non-zero.

The target is 1.0 for both metrics before signed retrieval can be described as complete.

## Methodology

Fixtures are response JSON objects captured from retrieval-like tools (`kb_search_code`, `kb_search_docs`, `kb_find_tests`, `kb_find_docs`, `kb_neighbors`, `kb_context`, `kb_impact`, `kb_brief_feature`). Each fixture contains the signed response and one declared mutation path. The runner verifies the original response, applies the mutation, and verifies that the tampered response fails.

Development uses `DevSelfSignedSigner`. A production signer can supersede this ADR only if offline verification remains available and the engine still does not import `chio_*`.

## Consequences

- `make kb-verify RESPONSE=<path>` becomes the narrow manual gate for one response.
- `signed-retrieval` stays under `deferred:` in `outcomes.yml` until the runner + fixtures land (Wave 4 continuation P0: do not list it under active `evals:` without a runner — that would be dishonest green).
- Tamper rejection becomes part of regression testing, so receipt fields such as `parent_receipt_hash` cannot be silently excluded from the signed payload.

## Acceptance

- [ ] `signed-retrieval` runner lands and reports both metrics.
- [ ] At least two signed response fixtures are committed.
- [x] A tampered-response negative test fails verification (`kb-engine/tests/test_receipt.py`, `chio-pack/tests/test_cli.py` verify command).
- [ ] The ADR status is changed to `accepted` after the first passing measured run is recorded in `vault/_meta/dashboards/eval-outcomes.md`.

## Honesty note (2026-07-08 continuation)

Offline `chio-dev verify` + tamper-fail are proven by unit/CLI tests. The outcome eval remains **deferred** (`blocked_until: phase-2b-runner`) — do not invent a 1.0 score.