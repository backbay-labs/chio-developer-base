---
id: decisions.ADR-0002
type: adr
status: pending
date: 2026-05-07
date-accepted: TBD
title: "Phase 0 outcome-eval baselines"
owners:
  - "@connor"
supersedes: []
related:
  - decisions.ADR-0000
---

# ADR-0002 — Phase 0 outcome-eval baselines

- **Status:** Pending baselines (Phase 0 incomplete)
- **Date filed:** 2026-05-07
- **Date accepted:** TBD (when all four baselines are committed)
- **Owners:** @connor
- **Related:** [ADR-0000](ADR-0000-charter.md), [`chio-pack/eval/PHASE-0.md`](../chio-pack/eval/PHASE-0.md)

> **This ADR is a placeholder.** Its purpose is to make the structure of the eventual baseline acceptance visible *now*, so when the four outcome evals produce their baselines, the ADR is filled in rather than authored under time pressure. Phase 1 cannot start until this ADR is `Accepted`.

## Context

[ADR-0000](ADR-0000-charter.md) commits to evals-first phasing: outcome evals (`time-to-first-correct-fix`, `repeated-mistake-rate`, `conformance-harness-recall`, `capability-error-explanation`) must have baselines committed *before* any Phase 1 feature ships. The eval framework is defined in [`chio-pack/eval/PHASE-0.md`](../chio-pack/eval/PHASE-0.md).

This ADR records those baselines as the official starting line. Improvement targets in PHASE-0.md (e.g., +30% on time-to-fix, < 0.10 on repeated-mistake-rate) are computed against these numbers.

## Decision

> Filled in when baselines land. Placeholder values (`TBD`) below.

The baselines for the four Phase 0 outcome evals, measured against the unmodified arc PR #599 stack on commit `<TBD>` of `codex/chio-kb-a-grade-dogfood`, are:

| Eval | Metric | Baseline | Sample size | Date measured |
| ---- | ------ | -------- | ----------- | ------------- |
| `time-to-first-correct-fix`     | mean score (0–1)    | TBD | TBD fixtures | TBD |
| `repeated-mistake-rate`         | rate (0–1)          | TBD | TBD sessions | TBD |
| `conformance-harness-recall`    | mean recall@3 (0–1) | TBD | TBD fixtures | TBD |
| `capability-error-explanation`  | mean score (1–5) for `raw` augmentation | TBD | TBD scenarios × 3 raters | TBD |

## Methodology deltas from PHASE-0.md

> Filled in if measurement surfaces issues that required adjusting the methodology. PHASE-0.md is the spec; this section records *deviations* and their justifications.

- **`time-to-first-correct-fix`:** [TBD — record any fixtures that were dropped during baseline measurement, and why]
- **`repeated-mistake-rate`:** [TBD — record the LLM-judge model used and any prompt deltas]
- **`conformance-harness-recall`:** [TBD — note the `--search-limit` value used by `harvest-conformance-fixtures.py` and how many fixtures were dropped at the `confidence=low` cut]
- **`capability-error-explanation`:** [TBD — name the three raters; record any rubric calibration adjustments from the inter-rater session]

### M0 (Harden v0.1) — Phase 0 outcome-eval correctness debt (2026-05-08)

The Skeptic's audit on the M0 milestone surfaced three silent-failure paths in the Phase 0 outcome-eval runners. They are not bugs in the rubric or the spec — they are gaps between what the runners *measure* and what the rubric *defines*. Each is now visible in the runner's JSON output (so a downstream consumer cannot quietly accept the placeholder values as a real signal) and is recorded here so that the eventual baseline numbers can be interpreted correctly.

When the corresponding silent-failure path is closed, the JSON-output surface (e.g. `stub_warning`, `stubbed_kinds`, `llm_independence_warning`) falls off automatically; this section can then be amended with a successor delta noting the date the gap closed.

- **`repeated-mistake-rate` — candidate-notes stub.** The runner's `_candidate_notes_stub(pre_context)` returns `[]`. The real implementation must call `kb_search_code` / `kb_search_docs` against a snapshot of the KB index AT THE TIME of the mistake (Phase 1 deliverable). Until that lands, the LLM-judge has no candidate notes to consider, defaults to `was_documented = False`, and the metric is biased toward 0%. The runner now emits a `stub_warning` field listing this gap so the JSON output can never be silently mistaken for a real measurement. See `chio_pack/eval/runners/repeated_mistake.py::_candidate_notes_stub`. Sunset: when the Phase 1 KB stack is wired into the candidate-recovery path, remove the `_is_stub` markers and the warning falls off automatically.

- **`repeated-mistake-rate` — three stubbed mistake-kind classifiers.** `superseded_quickly`, `wrong_capability_scope`, and `bypassed_guard` always return `[]` from `chio_pack/eval/classifiers/heuristic.py`. They require, respectively, the vault-sync ADR-transition log and arc-aware static analysis of capability literals / guard call sites — all Phase 1+ work. The runner now emits a `stubbed_kinds` field naming these three so the metric's per-kind breakdown is honestly under-counted. Successor work should remove the relevant entries from `_STUBBED_KIND_INFO` in the same change that lands the real implementation.

- **`capability-error-explanation` — rater-B and rater-C are same Anthropic family.** Per [ADR-0004](ADR-0004-rater-pool.md), rater-B is `claude-sonnet-4-6` and rater-C is `claude-haiku-4-5-20251001`. Both are within the Anthropic family; cross-family diversity is absent. Inter-rater agreement statistics from the Run-0 calibration are therefore expected to be **optimistic** — the LLM raters share blind spots and tend to agree more than two genuinely independent raters would. The calibration harness now (a) resolves the model names from the `CHIO_KB_RATER_B_MODEL` and `CHIO_KB_RATER_C_MODEL` env vars (so an operator can pin a snapshot or substitute a non-Anthropic model without editing source) and (b) emits an `llm_independence_warning` whenever the rater-B/rater-C disagreement-flag rate falls below 5% on a calibration run, with a reference to the ADR-0004a sunset criterion (12 weeks from 2026-05-07; recruit a non-Anthropic rater or re-affirm the choice with cost data). Treat the disagreement-flag rate as a lower bound until cross-family raters are added.

These deltas do not change the *spec* in PHASE-0.md or invalidate the Run-0 calibration. They make the existing methodology gaps machine-readable so that:
- the eventual baseline numbers in the table above are interpreted correctly when they land, and
- a green CI run cannot quietly mask the structural under-counting until Phase 1 closes the gaps.

## Fixture provenance

> Filled in when fixtures are committed. Each commit-SHA pin makes the baseline reproducible.

- `chio-pack/eval/fixtures/time-to-fix/` — committed at `<TBD-sha>` with `<N>` fixtures.
- `chio-pack/eval/fixtures/conformance-recall/` — committed at `<TBD-sha>` with `<N>` fixtures (harvested by `harvest-conformance-fixtures.py` and curated to drop `confidence=low`).
- `chio-pack/eval/fixtures/cap-error-explanation/` — committed at `<TBD-sha>` with `<N>` scenarios.
- Session logs for `repeated-mistake-rate` baseline — `~/.chio-dev/sessions/baseline/<TBD>.jsonl` (not committed; archived separately for confidentiality).

## Sign-off

> Filled in when baselines land. Required signers per PHASE-0.md "Phase 0 done":

- [ ] @connor — confirms fixture sets exist and are reproducible (`make kb-eval-outcomes` runs against fresh-cloned data and produces the table above).
- [ ] @connor — confirms negative-test passes (an intentional regression triggers `make kb-eval` red).
- [ ] @rater-1, @rater-2, @rater-3 — three raters confirm they completed `capability-error-explanation` baseline rating per the `rubrics.md` protocol.

## Consequences

### When this ADR is Accepted

- Phase 1 (carve-out + vault as canonical) is unblocked.
- The numbers in the table above become the immutable starting line. Future regressions are measured against them, not against rolling means.
- PHASE-0.md targets (improvement %s, absolute thresholds) are interpreted in terms of these baselines.

### Risks if this ADR slips past 7 working days

PHASE-0.md is explicit:

> If Phase 0 takes longer than 7 working days, the carve-out is signaled as premature — fall back to incubating inside arc per [ADR-0001](ADR-0001-repo-graduation.md) Decision-B.

If `Date accepted` is more than 7 working days after `Date filed`, file a follow-up ADR explaining the slip and decide explicitly whether to continue or roll back.

## Open questions

> To be resolved during baseline measurement.

- [ ] **Inter-rater calibration round.** PHASE-0.md says every 4th eval run does a calibration round. Should the baseline run *itself* be preceded by a calibration round, or does the first calibration happen at run 4? Default: precede with calibration; record the calibration scores in `vault/_meta/dashboards/rater-calibration.md`.
- [ ] **Baseline immutability.** If a baseline turns out to be miscomputed (e.g., a fixture had a typo), how do we correct it without losing the historical record? Default: file a successor ADR (`ADR-0002a`) that supersedes this one and pins the corrected baseline; do NOT edit this ADR's table in place.
- [ ] **Phase 2 outcome eval baselines** (`signed-retrieval`, `pr-impact-gate-precision-recall`). These are deferred per `outcomes.yml`. Will they get their own ADR or amend this one? Default: separate ADR (`ADR-00XX`) at the time their features land.

## References

- [ADR-0000](ADR-0000-charter.md) — charter; commits to evals-first phasing
- [`chio-pack/eval/PHASE-0.md`](../chio-pack/eval/PHASE-0.md) — eval definitions
- [`chio-pack/eval/rubrics.md`](../chio-pack/eval/rubrics.md) — scoring rubrics
- [`chio-pack/eval/outcomes.yml`](../chio-pack/eval/outcomes.yml) — machine-readable spec
- [`vault/_meta/dashboards/eval-outcomes.md`](../vault/_meta/dashboards/eval-outcomes.md) — current report (will show baseline values once accepted)
