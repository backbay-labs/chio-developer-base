# Eval 4 raters — `capability-error-explanation`

Sister doc to [`PHASE-0.md`](PHASE-0.md). Records the three raters who score the `capability-error-explanation` outcome eval, their pseudonymous IDs for stored output, and their calibration history.

> **Status:** placeholder. Concrete rater identities and calibration scores fill in during Phase 0 baseline measurement (see [ADR-0002](../../decisions/ADR-0002-phase-0-baselines.md)).

## Roster

The `capability-error-explanation` eval requires exactly three raters per scenario per run.

| Rater | Pseudonym | Role | Joined | Calibration last passed |
| ----- | --------- | ---- | ------ | ----------------------- |
| @connor | rater-A | Chio author / maintainer | 2026-05-07 | TBD (Run-0 pending) |
| TBD | rater-B | Pending: Chio-familiar engineer (target: 1 internal Backbay engineer) | TBD | — |
| TBD | rater-C | Pending: external rater OR LLM-judge fallback (see "Solo-maintainer fallback" below) | TBD | — |

A fourth (alternate) is named for tiebreak when the disagreement flag fires (`max - min > 1` on any dimension).

| Alternate | Pseudonym | Joined | Available |
| --------- | --------- | ------ | --------- |
| TBD | rater-D | TBD | flagged-rerate only |

## Solo-maintainer fallback (Phase 0 reality)

The original PHASE-0.md spec assumed three named human raters at Phase 0 baseline time. As of v0.0.1-vault-complete the maintainer pool is **single-human** (@connor). Two paths to unblock:

1. **Recruit two humans.** Identify two Chio-familiar engineers (one internal, one external if open-source community grows) who can commit to ~30 minutes per eval run, ~4 runs in the first six months. Preferred path. RATERS.md table fills in; Run-0 calibration proceeds normally.

2. **LLM-judge fallback.** Document an explicit Phase-0-only configuration where rater-B and rater-C are LLM judges using **distinct prompt strategies** (e.g., rater-B = Claude Sonnet 4.6 with the rubric verbatim; rater-C = Claude Haiku 4.5 with a rubric variant emphasizing accuracy). Disagreement-flag rate becomes the sanity check rather than human-vs-human variance. **Costs:** rubric drift goes undetected if both LLMs share blind spots; subjective dimensions (clarity especially) drift toward LLM stylistic preferences. **Mitigation:** rater-A (human) catches LLM-stylistic bias by re-rating any flagged scenario.

The current state is "**Path 1 preferred, Path 2 documented.**" An ADR (proposed `ADR-0004-rater-pool`) should record which path the project commits to before ADR-0002 sign-off.

## Pseudonymization rule

Stored output uses the pseudonym (`rater-A`, `rater-B`, `rater-C`, `rater-D`) — **never the handle**. The mapping above is the only place the bridge is recorded; it lives only in this committed file (no DB, no env var, no log line).

When a rater leaves, their row moves to `## Past raters` and their pseudonym is **retired** — never re-used for a new rater. This keeps historical scores attributable across rater turnover.

## Calibration cadence

Per [`PHASE-0.md` "Rater protocol notes"](PHASE-0.md#rater-protocol-notes-eval-4): every 4th eval run begins with an inter-rater calibration round. One shared scenario is rated by all three raters, scores discussed, then full scoring resumes.

| Run # | Date | Scenario | Pre-discussion scores | Post-discussion scores | Δ |
| ----- | ---- | -------- | --------------------- | ---------------------- | - |
| 0 (baseline) | TBD | TBD | TBD | TBD | TBD |

**The Run-0 baseline calibration MUST be recorded before any baseline scoring begins.** [ADR-0002](../../decisions/ADR-0002-phase-0-baselines.md) sign-off requires this row to be filled.

Subsequent calibration rows are appended (newest at bottom). Calibration adjustments per-rater are recorded in `vault/_meta/dashboards/rater-calibration.md`.

## Rules of engagement

Per `PHASE-0.md`, raters are bound by:

- **Blind rating.** Raters do not see which augmentation they're rating, except when the augmentation IS `raw` (the control).
- **Shuffle protocol.** Scenarios shuffled per-rater; augmentations within a scenario shuffled; minimum 2 unrelated scenarios between augmentations of the same scenario.
- **Fatigue cap.** Max 30 ratings per session per rater. Sessions ≥ 2 hours apart.
- **Confidentiality.** Don't discuss specific scenarios or scores with other raters except during scheduled calibration rounds.
- **Disagreement-flag handling.** When a flag fires (any dimension `max - min > 1`), the alternate (rater-D) re-rates ONLY that dimension. The original three ratings are KEPT for variance tracking; the 4th is appended, never substituted.
- **Recusal.** If a rater authored the Chio component being scored, they recuse from that scenario — record recusal in the run log; redistribute to the alternate.

## Past raters

| Rater | Pseudonym (retired) | Joined | Departed | Reason |
| ----- | ------------------- | ------ | -------- | ------ |
| (none yet) | | | | |

## Open questions

- [ ] **Honorarium / compensation.** Out of scope for v0. Document policy here if raters are external.
- [ ] **What if only two raters are available for a run?** Default: postpone the run rather than score with two. Deferred runs are noted in `vault/_meta/dashboards/eval-outcomes.md` so the gap is visible.
- [ ] **Calibration scenario rotation.** Should the calibration scenario rotate across runs (different scenario each time) or stay fixed (same scenario, tracking rater drift)? Default: rotate every 4 runs to balance drift-tracking with variety.

## See also

- [`PHASE-0.md`](PHASE-0.md) — eval definition (Eval 4)
- [`rubrics.md`](rubrics.md) — the scoring rubric raters apply
- [`outcomes.yml`](outcomes.yml) — machine-readable spec; references `RATERS.md` indirectly via the `raters: 3` field
- [ADR-0002](../../decisions/ADR-0002-phase-0-baselines.md) — baseline acceptance ADR; sign-off rows reference these raters by pseudonym
