---
id: dashboards.rater-calibration
type: dashboard
status: open
last-validated: 2026-05-07
---

# Rater calibration

Per-rater drift over time on the `capability-error-explanation` Eval (Eval 4). Updated after every calibration round (every 4th eval run, per [`chio-pack/eval/PHASE-0.md`](../../../chio-pack/eval/PHASE-0.md)).

> **Status:** placeholder. The Run-0 baseline calibration MUST land here before [ADR-0002](../../../decisions/ADR-0002-phase-0-baselines.md) can be Accepted.

## What this dashboard answers

Three questions per rater:

1. **Are they drifting?** A rater whose pre-discussion scores trend systematically high or low over runs has miscalibrated; the rubric anchors aren't landing.
2. **Are they converging?** Post-discussion scores should be closer to the inter-rater median than pre-discussion. If not, discussion isn't doing its job.
3. **Are they consistent?** A rater whose disagreement-flag rate (`max - min > 1` with the others) climbs across runs is either acquiring a personal interpretation or burning out. Either is fixable.

The roster + pseudonymization rules live in [`chio-pack/eval/RATERS.md`](../../../chio-pack/eval/RATERS.md). This dashboard refers to raters by **pseudonym only**.

## Calibration history

Append a block per run. Each block has 4 rows per rater (one per dimension: clarity / accuracy / actionability / brevity).

| Run # | Date | Rater   | Dimension     | Pre-disc | Post-disc | Δ   | Notes    |
| ----- | ---- | ------- | ------------- | -------- | --------- | --- | -------- |
| 0     | TBD  | rater-A | clarity       | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-A | accuracy      | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-A | actionability | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-A | brevity       | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-B | clarity       | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-B | accuracy      | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-B | actionability | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-B | brevity       | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-C | clarity       | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-C | accuracy      | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-C | actionability | TBD      | TBD       | TBD | baseline |
| 0     | TBD  | rater-C | brevity       | TBD      | TBD       | TBD | baseline |

## Drift summary (per rater)

Filled in once Run 0+ data exists. Each rater gets a section with rolling stats and observed patterns.

### rater-A

- **Mean pre-discussion (across runs):** TBD
- **Mean post-discussion:** TBD
- **Trend (last 4 runs):** TBD
- **Disagreement-flag rate (last 4 runs):** TBD
- **Notes:** _(observed patterns: e.g., "tends to score brevity high", "shifted on actionability between Runs 4 and 8 after rubric clarification")._

### rater-B

- **Mean pre-discussion:** TBD
- **Mean post-discussion:** TBD
- **Trend:** TBD
- **Disagreement-flag rate:** TBD
- **Notes:**

### rater-C

- **Mean pre-discussion:** TBD
- **Mean post-discussion:** TBD
- **Trend:** TBD
- **Disagreement-flag rate:** TBD
- **Notes:**

### rater-D (alternate)

- **Used in N flagged-rerate cases:** TBD
- **Notes:**

## How to use this dashboard

- **After every calibration round** (every 4th eval run): append rows for each rater × dimension to the history table.
- **After every controversial scenario** (per [`RATERS.md`](../../../chio-pack/eval/RATERS.md), 2+ flagged dimensions in one scenario): append a free-form note in the relevant rater's drift summary.
- **Quarterly:** review the drift summaries and decide whether to retire / replace any rater. A rater whose drift can't be brought back into alignment by discussion is signal that the **rubric anchors** need work — file an ADR before retiring the rater.

## CI gate

The eval-runner ([`chio-pack/chio_pack/eval/runner.py`](../../../chio-pack/chio_pack/eval/runner.py), Phase 1+) emits a regression error when the disagreement-flag rate across the last 4 runs exceeds **30%**. That threshold is set in [`outcomes.yml`](../../../chio-pack/eval/outcomes.yml) and is per [`PHASE-0.md` "Regression policy"](../../../chio-pack/eval/PHASE-0.md#regression-policy).

## See also

- [`chio-pack/eval/PHASE-0.md`](../../../chio-pack/eval/PHASE-0.md) — Eval 4 definition
- [`chio-pack/eval/rubrics.md`](../../../chio-pack/eval/rubrics.md) — the 4-dimension rubric raters apply
- [`chio-pack/eval/RATERS.md`](../../../chio-pack/eval/RATERS.md) — roster, pseudonymization, rules of engagement
- [ADR-0002](../../../decisions/ADR-0002-phase-0-baselines.md) — baseline acceptance ADR
- [eval-outcomes.md](eval-outcomes.md) — the auto-generated eval status report
