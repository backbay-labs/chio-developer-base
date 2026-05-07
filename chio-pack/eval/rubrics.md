# Outcome eval rubrics

Detailed scoring rubrics for outcome evals defined in [`PHASE-0.md`](PHASE-0.md).

## Capability-error-explanation rubric (Eval 4)

Four dimensions, each 1–5. Anchored descriptions at 1, 3, 5; raters interpolate to 2 and 4. Raters score *each dimension independently*; the per-scenario score is the mean of the four dimensions.

### Clarity

> Would a Chio engineer with one month of experience understand what failed and what *kind* of failure it is?

| Score | Anchor |
| ----- | ------ |
| 1 | Jargon-only; no narrative. The engineer would ask "what is this saying?" |
| 3 | The failure is identifiable but the engineer needs to read source to be sure of the failure mode |
| 5 | The failure is named, framed, and the engineer can describe it back without source diving |

### Accuracy

> Does the explanation reflect what actually happened in the code path that produced the error?

| Score | Anchor |
| ----- | ------ |
| 1 | Explanation contradicts the code path; misleads the engineer toward the wrong file or wrong subsystem |
| 3 | Explanation is correct in spirit but contains one or more inaccurate claims |
| 5 | Every claim is grounded in code or spec, with citations the engineer can follow directly |

### Actionability

> Does it suggest a concrete next step?

| Score | Anchor |
| ----- | ------ |
| 1 | No next step; the engineer must invent one from scratch |
| 3 | A general direction ("check the revocation list") but not a specific action |
| 5 | A specific next step: file path, command to run, symbol to inspect, or PR / spec to read |

### Brevity

> Is the message efficient or padded?

| Score | Anchor |
| ----- | ------ |
| 1 | More than 2× the minimum necessary length; the engineer skims and misses the point |
| 3 | Roughly the right length but with a paragraph or sentence that could be cut without loss |
| 5 | As short as possible but no shorter; nothing skimmable is wasted |

### Aggregate

```
scenario_score = mean(clarity, accuracy, actionability, brevity)
augmentation_score = mean(scenario_score across raters)
final_score = mean(augmentation_score across scenarios)
```

### Disagreement flag

Fires per-dimension when `max_rater - min_rater > 1`. A flagged dimension is re-rated by a 4th rater. The original ratings are **kept** for variance tracking — the 4th rater's score is added, not used as a tiebreaker.

A scenario is "controversial" if 2+ of its 4 dimensions trigger the flag. Controversial scenarios are reviewed in the Phase 4 retrospective; if the same scenario is controversial in 3+ runs, the rubric is the problem, not the scenario.

---

## Mistake taxonomy (Eval 2)

Each `mistake` event is tagged with exactly one `kind` by the heuristic classifier. Categories below are exhaustive — `other` exists as a manual-review escape hatch.

| Kind | Trigger | Notes |
| ---- | ------- | ----- |
| `reverted_edit` | An edit's effect is undone (line-level) within 30 minutes by the same agent in the same file | Counts only if the revert restores the prior content; "reorganizing" doesn't count |
| `failed_then_re_edited` | A test run exits non-zero and the agent edits the same file again within 10 min without first re-running the failing test | Captures debug-by-flailing |
| `superseded_quickly` | An ADR draft transitions `proposed → superseded` within 7 days of being filed | Captures premature commitment |
| `wrong_capability_scope` | An edit grants or requests a capability scope that is later narrowed in the same session | Chio-specific. The most valuable kind to catch — a documented "narrow scope first" episode would have prevented it |
| `bypassed_guard` | A test or feature is added that disables / mocks a guard the spec says is required | Chio-specific. Usually a knowledge gap about why the guard is required |
| `other` | None of the above; manually classified during weekly review | Should stay below 20% of total mistakes — a higher rate signals the taxonomy is incomplete |

### LLM-judge prompt skeleton

The judge (Sonnet 4.6) receives, for each candidate mistake:

- The agent's last 4k tokens of context window prior to the mistake
- The list of candidate vault notes / ADRs / episodes that were in retrieval-top-3 for that context
- The mistake event itself (kind + minimal description)

Output schema:

```json
{
  "was_documented": true,
  "evidence": ["spec.capability.revocation", "decisions/ADR-0042-revocation-window"],
  "confidence": 0.84,
  "rationale": "ADR-0042 explicitly warns against returning a 30-day-old revocation list..."
}
```

Confidence below 0.5 → re-judge with a second pass. Confidence below 0.3 on second pass → flag for manual review.

---

## Time-to-fix scoring tiebreakers (Eval 1)

If two runs produce the same numeric score (within 0.001):

1. The run with **fewer `kb_search_*` retries on the same query** wins (proxy for retrieval quality).
2. If still tied, the run with **fewer total bytes of context consumed** wins.
3. If still tied, declare a tie and report both. Do not invent a tiebreaker.

---

## Conformance-harness-recall edge cases (Eval 3)

- **Multi-fix fixtures.** When `canonical_fix` lists more than 3 files, recall@3 caps at 3/N. This is intentional — it pressures retrieval to surface the *most authoritative* file first, not all of them.
- **Spec-only fixes.** Some conformance failures are fixed by spec/docs changes only (no code). These count as fixtures; retrieval must still surface the canonical doc in top-3.
- **Inconclusive PRs.** If the harvested PR doesn't clearly identify the canonical fix file (e.g., a sweeping refactor), drop the fixture rather than guess.

---

## Rater protocol notes (Eval 4)

- Raters are instructed to **avoid context contamination**: they do not see the raw error message before rating an augmentation, except when explicitly rating the `raw` augmentation.
- A scenario's four augmentations are rated in shuffled order, never consecutively for the same scenario across the rater's session — minimum 2 unrelated scenarios between augmentations of the same scenario.
- Rater fatigue: max 30 ratings per session per rater. Sessions ≥ 2 hours apart.
- Inter-rater calibration: every 4th eval run, one shared scenario is rated by all 3 raters and discussed before scoring resumes. Calibration adjustments are recorded in `vault/_meta/dashboards/rater-calibration.md`.
