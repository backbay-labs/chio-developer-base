---
id: decisions.ADR-0004
type: adr
status: accepted
date: 2026-05-07
title: "Phase 0 rater pool"
owners:
  - "@connor"
supersedes: []
related:
  - decisions.ADR-0002
---

# ADR-0004 — Phase 0 rater pool

- **Status:** Accepted
- **Date:** 2026-05-07
- **Owners:** @connor
- **Supersedes:** —
- **Related:** [PHASE-0.md Eval 4](../chio-pack/eval/PHASE-0.md#eval-4--capability-error-explanation), [RATERS.md](../chio-pack/eval/RATERS.md), [ADR-0002 (baselines)](ADR-0002-phase-0-baselines.md)

## Context

PHASE-0.md Eval 4 (`capability-error-explanation`) requires three named raters per scenario per run, plus an alternate for disagreement-flag tiebreak. The original spec assumed three Chio-familiar humans. As of [v0.0.1-vault-complete](https://github.com/backbay-labs/chio-developer-base/releases/tag/v0.0.1-vault-complete), the maintainer pool is **single-human** (@connor).

Two paths surfaced in [RATERS.md](../chio-pack/eval/RATERS.md):

1. **Recruit two more humans** — preserves cross-rater variance and the original "would a Chio engineer find this confusing" signal.
2. **LLM-judge fallback** — rater-B = Sonnet 4.6, rater-C = Haiku 4.5 with rubric variants.

[ADR-0002](ADR-0002-phase-0-baselines.md) sign-off requires the Run-0 inter-rater calibration, which can't proceed without three named raters. Without a path commitment, Phase 0 is blocked indefinitely.

## Decision

**Adopt the LLM-judge fallback (Path 2) for Phase 0 only**, with explicit sunset criteria.

| Rater | Identity | Rubric |
| ----- | -------- | ------ |
| rater-A | @connor (human) | canonical (`rubrics.md`) |
| rater-B | `claude-sonnet-4-6` | canonical |
| rater-C | `claude-haiku-4-5-20251001` | accuracy-emphasis variant (`rubrics-accuracy-emphasis.md`) |
| rater-D (alternate) | `claude-opus-4-7` | canonical |

The alternate fires only on disagreement-flag (`max - min > 1` on any dimension), per RATERS.md "Rules of engagement."

## Why LLM-judge for Phase 0

1. **Unblocks ADR-0002 sign-off.** Recruiting two named, committed human raters is a multi-week social process. The Phase 0 baseline measurement is a scheduling dependency on Phase 1 carve-out work that's already specified.
2. **Costs are documented in RATERS.md.** Rubric drift goes undetected if both LLMs share blind spots; subjective dimensions drift toward LLM stylistic preferences.
3. **rater-A (human) catches LLM-stylistic bias.** A flagged scenario gets re-rated by rater-D (different model size); rater-A reviews the disagreement.
4. **Cross-family model diversity preserved (partially).** Sonnet 4.6 and Haiku 4.5 are different model sizes within the same family. Worse than truly cross-family but better than a single-model setup. Cross-family (e.g., GPT-5) considered as Alternative 3 below; deferred.

## Rubric variant for rater-C

rater-C uses an "accuracy-emphasis" variant of the canonical rubric:

- Dimensions and 1–5 scale **unchanged** — clarity, accuracy, actionability, brevity.
- For the **accuracy** dimension only: anchor "5" requires every claim to be ground-truth-checkable in the cited file via line number. The canonical rubric accepts "grounded in code or spec," which a stylistic LLM can over-credit. The variant tightens to "verifiable via line-number citation."
- Other three dimensions identical to canonical.

This forces rater-C to disagree more often with rater-B on accuracy specifically — exactly where overclaim bias would otherwise hide under inter-LLM agreement. The variant rubric is committed at [`chio-pack/eval/rubrics-accuracy-emphasis.md`](../chio-pack/eval/rubrics-accuracy-emphasis.md) alongside this ADR.

## Sunset criteria

ADR-0004 is **superseded** when **either** of these occurs:

- Two human raters (filling rater-B and rater-C) are recruited and complete their Run-0 calibration. File a successor ADR confirming the human-rater pool.
- 12 weeks elapse from this ADR's date (target: **2026-07-30**) without a recruited human rater. File a follow-up ADR (`ADR-0004a`) re-affirming the LLM-judge choice with updated cost data from observed eval runs (specifically: rater-B vs rater-C disagreement-flag rate, rater-A re-rate frequency, any patterns in Δ between human and LLM scores on shared scenarios).

## Consequences

**Positive**

- Phase 0 baseline measurement can proceed.
- ADR-0002 sign-off is unblocked once the Run-0 calibration completes (with LLM raters).
- The cost trade-off is explicit and reviewable; future work can quantify the cost from observed run data.

**Negative**

- LLM raters can't measure "would a real engineer find this confusing." That's the signal Eval 4 was originally designed to capture; LLM judges produce a strictly different signal — closer to "would a model find this clear."
- Cross-family model diversity is absent (both Anthropic). A truly distinct second-rater would be a non-Anthropic model.
- Inter-rater agreement statistics will be **optimistic** — the disagreement-flag rate is likely to UNDER-report calibration drift compared to a real human panel.

These are real costs. The mitigation is rater-A (human review of all flagged scenarios) and the sunset criteria.

## Alternatives considered

1. **Wait for human raters (Path 1).** Rejected: schedules ADR-0002 sign-off out months. Phase 1 carve-out work would idle on a social blocker.
2. **Single-rater configuration (rater-A only).** Rejected: violates Eval 4's three-rater requirement; the disagreement-flag protocol is meaningless with one rater. Variance signal is eliminated.
3. **Cross-family LLM raters (e.g., GPT-5 + Sonnet).** Better diversity than this ADR's choice. Deferred: adds OpenAI API dependency to a project that otherwise avoids it. Could be revisited when filing ADR-0004a.
4. **Defer Eval 4 entirely.** Rejected: would leave a documented gap in PHASE-0.md and silently shrink the Phase 0 baseline surface from four evals to three. The capability-error-explanation signal is one of the four reasons Phase 0 evals exist.

## References

- [PHASE-0.md Eval 4](../chio-pack/eval/PHASE-0.md#eval-4--capability-error-explanation)
- [RATERS.md](../chio-pack/eval/RATERS.md) — solo-maintainer fallback section
- [rubrics.md](../chio-pack/eval/rubrics.md) — canonical rubric
- [rubrics-accuracy-emphasis.md](../chio-pack/eval/rubrics-accuracy-emphasis.md) — variant for rater-C (lands with this ADR)
- [ADR-0002](ADR-0002-phase-0-baselines.md) — Phase 0 baseline acceptance (this ADR is a precondition)
