# Phase 0 — Outcome evals

Phase 0 is "evals before code." The carve-out's value is unfalsifiable without measurement; this document defines the four outcome evals that gate Phases 1–4.

> **Status:** spec. Phase 0 is unblocked when this document is reviewed and signed off on the [ADR-0000](../../decisions/ADR-0000-charter.md) acceptance PR.

## Why evals first

PR #599 already gets an A on retrieval (p@5 ≥ 0.99, MRR ≥ 0.97). The carve-out's claimed value lives *downstream* of retrieval — does the agent reach a correct fix faster, repeat fewer documented mistakes, recover from conformance failures more reliably, produce error explanations a human rates as clear? Those are the questions outcome evals answer. Without them, every Phase 1+ claim ("the vault helps", "the gate prevents drift", "signed retrieval matters") is vibes.

## The four evals at a glance

| # | Eval | What it measures | Format | Phase 0 deliverable |
| - | ---- | ---------------- | ------ | ------------------- |
| 1 | `time-to-first-correct-fix` | Wall-clock + tool-call count for an agent to reach a passing test on a fixture bug | Behavioral | ≥ 8 fixtures + runner spec + baseline |
| 2 | `repeated-mistake-rate` | Fraction of agent mistakes that the KB had documented at the time | Behavioral | Mistake taxonomy + classifier + baseline (≥ 20 sessions logged) |
| 3 | `conformance-harness-recall` | Top-3 recall of canonical fix on SDK conformance failure | Retrieval-augmented | 20 historical failures harvested + scoring + baseline |
| 4 | `capability-error-explanation` | Human-rated quality of retrieval-augmented Chio capability error messages | Subjective | 10 scenarios + 4-dim rubric + 3-rater protocol + baseline |

(Two more evals — `signed-retrieval` and `pr-impact-gate-precision-recall` — are deferred to Phase 2 because they require those features to exist. They are listed as `deferred:` in [`outcomes.yml`](outcomes.yml) so Phase 1 contributors can't quietly skip them.)

---

## Eval 1 — `time-to-first-correct-fix`

### Definition

Given a fixture bug — a real, historical Chio bug with a known correct fix — measure how long an agent takes to produce a passing test/patch and how many tool calls it spends getting there.

### Fixture format

`chio-pack/eval/fixtures/time-to-fix/<bug-id>.yml`:

```yaml
id: revoke-cross-issuer-2026-03-12
title: Revocation across issuers fails closed instead of consulting trust graph
source: "arc#PR-431"
arc_commit_before: a16cd3d3
arc_commit_after:  f02c87bd
agent:
  runner: codex-cli            # codex-cli | claude-code | cursor
  model:  claude-opus-4-7
  budget_seconds:    1800
  budget_tool_calls:  100
seed_state:
  starting_branch: main@a16cd3d3
  failing_test:    tests/conformance/peers/python/test_revocation.py::test_cross_issuer
expected:
  patch_signature: "docs/standards/CHIO_RECEIPTS_PROFILE.md MUST contain cross-issuer trust resolution"
  tests_must_pass:
    - tests/conformance/peers/python/test_revocation.py::test_cross_issuer
    - tests/conformance/peers/js/test_revocation.test.ts:test_cross_issuer_basic
scoring:
  time_weight:      0.6
  tool_call_weight: 0.4
  zero_score_if:
    - "any expected test still failing"
    - "patch deletes any existing test"
```

### Runner

`chio-pack/chio_pack/eval/runners/time_to_fix.py`:

1. Spawns the configured agent in a fresh worktree at `arc_commit_before`.
2. Provides MCP gateway access (chio-developer-base running) but nothing else from the eventual chio-developer-base feature set — i.e., for the *baseline* run, only PR #599's tools.
3. Records every tool call (timestamp + tool + args hash + result hash) to `~/.chio-dev/eval-runs/<run-id>/trace.jsonl`.
4. Stops when (a) all `tests_must_pass` pass, (b) budget exhausted, or (c) agent declares done.
5. Re-runs the test suite; verifies `expected.tests_must_pass`.

### Scoring

For each fixture:

```
score = 1.0
      - (time_used / budget_seconds)       * time_weight
      - (calls_used / budget_tool_calls)   * tool_call_weight

score = 0.0  if any zero_score_if condition triggered
```

Aggregate: mean score over fixtures. Ties broken per [`rubrics.md` "Time-to-fix scoring tiebreakers"](rubrics.md).

### Baseline and target

- **Phase 0 deliverable:** ≥ 8 fixtures harvested from arc git history (PRs that fixed real bugs); baseline measured against the current PR #599 stack unmodified.
- **Phase 4 target:** mean score improves by ≥ 30% vs. baseline.

### Fixture harvesting heuristic

Walk arc PRs merged in last 12 months. Keep PRs where:
- exactly one bug is named in the title or description,
- a test file changed AND a non-test file changed,
- the test file was edited to remove a `#[ignore]` / `xfail` / `.skip` marker, OR a new test was added that fails on the parent commit.

Manually accept ~12 candidates; pick the 8 most diverse by crate / subsystem.

---

## Eval 2 — `repeated-mistake-rate`

### Definition

Across a rolling 50-session window of agent activity, what fraction of recorded mistakes had already been documented in the KB (vault episodes, ADRs, or graphiti) at the time the agent made them?

A mistake is "documented" if a retrieval at the moment of the mistake — using the agent's actual prompt context — would have surfaced the relevant note in the top-3 results.

### Session log format

Each `chio-dev` session writes a log to `~/.chio-dev/sessions/<session-id>.jsonl`:

```json
{"t":"2026-05-07T10:14:22Z","event":"tool_call","tool":"kb_search_code","args":{"query":"..."},"result_ids":["..."]}
{"t":"2026-05-07T10:15:11Z","event":"edit","file":"crates/chio-kernel/src/kernel/mod.rs","sha_before":"...","sha_after":"..."}
{"t":"2026-05-07T10:18:30Z","event":"test_run","cmd":"cargo test","exit":1,"failures":["..."]}
{"t":"2026-05-07T10:25:09Z","event":"mistake","kind":"reverted_edit","file":"...","reverted_at":"2026-05-07T10:24:55Z","reason":"reintroduced cap unwrap"}
```

### Mistake classifier

Two stages:

1. **Heuristic.** A `mistake` event is auto-emitted on:
   - An edit reverted within 30 minutes (`reverted_edit`)
   - A test run exit ≠ 0 followed by another edit to the same file within 10 min without first running the test (`failed_then_re_edited`)
   - An ADR draft transitioning `proposed → superseded` within 7 days (`superseded_quickly`)
2. **LLM-judge** (Sonnet 4.6) decides for each candidate mistake: was a vault note / ADR / episode in retrieval-top-3 for the agent's pre-mistake context that would have prevented it? Output: `was_documented: bool` + `evidence: [note_ids]`. The judge sees only the agent's pre-mistake context window plus the candidate notes; it does not see the post-mistake outcome.

### Mistake taxonomy

Defined in [`rubrics.md` "Mistake taxonomy"](rubrics.md). Categories: `reverted_edit`, `failed_then_re_edited`, `superseded_quickly`, `wrong_capability_scope`, `bypassed_guard`, `other`. Used to slice the rate for diagnostics; aggregate is mean across all kinds.

### Scoring

```
repeated_mistake_rate = sum(was_documented) / sum(mistakes)
```

over the rolling 50 sessions.

### Baseline and target

- **Phase 0 deliverable:** classifier built; ≥ 20 sessions logged from current arc workflow as baseline.
- **Phase 4 target:** repeated-mistake-rate < 0.10 (i.e., fewer than 10% of mistakes are repeats of documented ones).

---

## Eval 3 — `conformance-harness-recall`

### Definition

Given a failing SDK conformance test, does retrieval surface the canonical fix in top-3 results?

### Fixture set

20 historical conformance failures harvested from arc git history. Each fixture:

`chio-pack/eval/fixtures/conformance-recall/<failure-id>.yml`:

```yaml
id: js-peer-revoke-checkpoint-2026-02-18
failing_test: tests/conformance/peers/js/test_receipts.test.ts:checkpoint_inclusion_proof
failure_message: |
  Expected receipt to include checkpoint root, got undefined.
  At RevokeReceipt.serialize() line 47.
canonical_fix:
  - file: docs/standards/CHIO_RECEIPTS_PROFILE.md
    section: "Checkpoint inclusion"
  - file: spec/schemas/chio-wire/v1/receipt/inclusion-proof.schema.json
    section: full
  - file: crates/core/chio-core-types/src/receipt/checkpoint.rs
    section: "checkpoint_root"
relevant_arc_pr: arc#412
```

Harvest method: `ops/scripts/harvest-conformance-fixtures.py` walks merged arc PRs that touched `tests/conformance/`, finds the failing-test signature in the PR description or commit message, and extracts the actual fix files from the diff.

### Scoring

For each fixture:

1. Run `kb_search_code(query=failure_message, limit=10)` and `kb_search_docs(query=failure_message, limit=10)`.
2. Take union of top-10, ranked by combined `rank_components` score.
3. Compute `recall_at_3 = |canonical_fix_files ∩ top_3| / |canonical_fix_files|`.

Aggregate: mean recall@3 across 20 fixtures.

### Baseline and target

- **Phase 0 deliverable:** 20 fixtures harvested; baseline measured against current PR #599 stack.
- **Phase 4 target:** ≥ 0.85 mean recall@3.

---

## Eval 4 — `capability-error-explanation`

### Definition

A subjective human-rated eval. Given a Chio capability error scenario, does retrieval-augmented explanation reduce confusion compared to the raw error?

### Scenarios

10 scenarios, each in `chio-pack/eval/fixtures/cap-error-explanation/<scenario-id>.yml`:

```yaml
id: revoked-cap-still-presented
scenario: |
  Agent presents a delegated capability that was revoked 2 minutes ago.
  Kernel returns: "RevocationCheck: capability rejected (revocation list version 47)"
context_query: "RevocationCheck capability rejected revocation list"
augmentations_under_test:
  - name: raw
    body: "RevocationCheck: capability rejected (revocation list version 47)"
  - name: kb_brief_feature
    body_source: |
      kb_brief_feature(
        feature="capability revocation",
        focus_paths=["crates/chio-kernel/src/kernel/delegation.rs"]
      )
  - name: kb_brief_feature + signed_receipt
    body_source: |
      above + signed retrieval receipt rendering
  - name: kb_brief_feature + episode_link
    body_source: |
      above + linked vault/episodes/ep-revoke-cross-issuer-2026-03-12.md
```

The four augmentations span the matrix from "no KB help" through "full Phase-2 surface."

### Rubric

See [`rubrics.md` "Capability-error-explanation rubric"](rubrics.md). Four dimensions, each scored 1–5:

- **Clarity** — would a new Chio dev understand what failed?
- **Accuracy** — does the explanation reflect what actually happened in code?
- **Actionability** — does it suggest a concrete next step?
- **Brevity** — is the message efficient or padded?

Each dimension has anchored descriptions at 1, 3, 5; raters interpolate to 2 and 4.

### Protocol

- 3 raters per scenario, blind to which augmentation they're rating.
- Scenarios shuffled, augmentations within scenario shuffled.
- Per-scenario score: mean of 4 dimensions, then mean across raters.
- **Disagreement flag:** any dimension where `max_rater - min_rater > 1`. Flagged scenarios get a 4th rater; the original ratings are kept for variance tracking.

### Baseline and target

- **Phase 0 deliverable:** 10 scenarios drafted, 3 raters identified, rubric finalized, baseline measured for `raw` augmentation only (since `kb_brief_feature` may improve in Phase 1+).
- **Phase 4 target:** mean score for `kb_brief_feature`-based augmentations ≥ 4.0; `raw` augmentation baseline must remain unchanged (it's a control).

### Rater pool

Three raters from {@connor, @aria, two TBD Chio-familiar engineers}. Raters log their identity for variance tracking but ratings are pseudonymized in stored output.

---

## Reporting

`make kb-eval-outcomes` outputs `vault/_meta/dashboards/eval-outcomes.md`:

```markdown
# Outcome evals — 2026-05-14

| Eval | Baseline | Current | Δ | Target | Status |
| ---- | -------- | ------- | - | ------ | ------ |
| time-to-first-correct-fix    | 0.41 | 0.52 | +0.11 | 0.53 (-30%)  | yellow |
| repeated-mistake-rate        | 0.23 | 0.15 | -0.08 | < 0.10       | yellow |
| conformance-harness-recall   | 0.61 | 0.78 | +0.17 | ≥ 0.85       | yellow |
| capability-error-explanation | 3.1  | 3.9  | +0.8  | ≥ 4.0        | green  |
```

Reports written into the vault (`vault/_meta/dashboards/`) so they show up in Obsidian and are git-versioned. A history line is appended to `vault/_meta/dashboards/eval-outcomes-history.jsonl` for every run.

## Regression policy

`make kb-eval` is the regression gate. CI fails when:

1. Retrieval eval drops below A on any of the 9 PR #599 categories. **Floor — non-negotiable.**
2. Any outcome eval regresses by more than its `regression_threshold` (defined per-eval in [`outcomes.yml`](outcomes.yml)) from its rolling 30-day mean.
3. Disagreement flag rate (Eval 4) exceeds 30% — signals rubric quality issues that must be addressed before further outcome-eval results are trusted.

A regression aborts the merge. Patches that knowingly trade outcome-eval performance for engineering wins must include an ADR.

## Phase 0 done

Phase 0 ends when **all** of the following are true:

- [ ] All four evals have **baseline numbers** committed at `vault/_meta/dashboards/eval-outcomes.md`.
- [ ] Fixture sets exist and are reproducible (`make kb-eval-outcomes` runs against fresh-cloned data).
- [ ] An intentional regression triggers `make kb-eval` red — verifying the gate works (negative test).
- [ ] [`outcomes.yml`](outcomes.yml) is committed with all `baseline_required: true` entries showing baselines.
- [ ] **ADR-0002** confirms the baselines and unblocks Phase 1.

If Phase 0 takes longer than 7 working days, the carve-out is signaled as premature — fall back to incubating inside arc per [ADR-0001](../../decisions/ADR-0001-repo-graduation.md) Decision-B.
