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
