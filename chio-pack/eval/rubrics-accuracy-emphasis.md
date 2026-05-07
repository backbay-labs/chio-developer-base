# Accuracy-emphasis rubric variant (rater-C)

Variant of [`rubrics.md`](rubrics.md) used by **rater-C** per [ADR-0004](../../decisions/ADR-0004-rater-pool.md). Tightens the accuracy dimension's "5" anchor to require **line-number-citable** ground truth, forcing rater-C to disagree with rater-B (canonical rubric) when an LLM has produced plausible-sounding but unverifiable claims.

Three of the four dimensions are **unchanged** from canonical. Only **accuracy** is altered.

## Clarity, Actionability, Brevity

Identical to [`rubrics.md`](rubrics.md). See that file's anchored 1/3/5 descriptions.

## Accuracy (variant)

> Does the explanation reflect what actually happened in the code path that produced the error?

| Score | Anchor (variant) |
| ----- | ---------------- |
| 1 | Explanation contradicts the code path; misleads the engineer toward the wrong file or wrong subsystem |
| 3 | Explanation is correct in spirit but contains one or more inaccurate or unverifiable claims |
| 5 | Every claim is ground-truth-checkable in the cited file at a specific line number. A claim like "X happens in `crates/foo/src/bar.rs::baz`" must be verifiable by opening that file at that symbol. Hand-waving citations like "see chio-kernel" or "this is handled by the policy compiler" without line-level grounding cap out at 4. |

### Why this variant exists

LLMs (rater-B in our pool) score accuracy generously when claims are *plausible*. The variant forces rater-C to over-penalize unverifiable claims — when both raters score accuracy "5", we have actual line-level agreement, not just stylistic agreement.

The variant is **only** applied when scoring accuracy. Other dimensions use the canonical anchors so the cross-rater comparison stays meaningful on dimensions where stylistic LLM agreement isn't a known failure mode.

### Operational note

When rater-C (Haiku 4.5) is invoked, the prompt explicitly cites the variant rubric. The model is told: "Use the accuracy anchors from `rubrics-accuracy-emphasis.md` (line-number citable). Use the canonical anchors from `rubrics.md` for clarity, actionability, and brevity."

If rater-C produces a score that suggests it didn't apply the variant (e.g., score 5 on accuracy where rater-B also gave 5 with non-line-number-citable evidence), that's a prompt-following failure logged for ADR-0004a follow-up.

## Aggregation

Identical to canonical:

```
scenario_score = mean(clarity, accuracy, actionability, brevity)
```

The variant changes anchor severity, not aggregation logic.

## See also

- [`rubrics.md`](rubrics.md) — canonical rubric (rater-A, rater-B, rater-D)
- [`RATERS.md`](RATERS.md) — roster, pseudonymization, rules of engagement
- [ADR-0004](../../decisions/ADR-0004-rater-pool.md) — why this variant exists
