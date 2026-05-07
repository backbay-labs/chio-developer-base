"""Runner for the repeated-mistake-rate outcome eval (Eval 2).

Loads recent session logs, runs the heuristic classifier, queries the
LLM-judge for each candidate mistake, and computes:

    repeated_mistake_rate = sum(was_documented) / sum(mistakes)

over the rolling window (default 50 sessions).

Per chio-pack/eval/PHASE-0.md "Eval 2 — Scoring", a fresh-checkout run
needs ≥ 20 logged sessions to produce a baseline. Until that threshold
is met, the runner returns a "blocked-input" status and exits non-zero
so make kb-eval-outcomes flags the gap.

CLI surface (invoked from chio_pack.eval.runner via outcomes.yml):

    python -m chio_pack.eval.runners.repeated_mistake \\
        --inputs ~/.chio-dev/sessions/ \\
        --window 50 \\
        --baseline-min-sessions 20

Returns JSON to stdout:

    {
      "rate": <float | null>,
      "n_sessions": <int>,
      "n_mistakes": <int>,
      "n_documented": <int>,
      "by_kind": {<kind>: {"count": int, "documented": int}, ...},
      "needs_manual_review": <int>,
      "status": "ok" | "blocked-input"
    }
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .. import session_log
from ..classifiers import heuristic, llm_judge


@dataclass
class Aggregate:
    rate: float | None = None
    n_sessions: int = 0
    n_mistakes: int = 0
    n_documented: int = 0
    by_kind: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"count": 0, "documented": 0}))
    needs_manual_review: int = 0
    status: str = "ok"


def _candidate_notes_stub(pre_context: str) -> list[dict[str, Any]]:
    """Placeholder for "what was in retrieval top-3 for this context."

    The real implementation calls kb_search_code / kb_search_docs against
    a snapshot of the KB's index AT THE TIME of the mistake. That requires
    the Phase 1 stack to be running. Until then, return [] so the LLM-judge
    decides "not documented" by default.

    A future enhancement: replay session tool_call events to recover the
    actual results the agent saw.
    """
    return []


def _build_pre_context(events: list[dict[str, Any]], up_to_idx: int, max_chars: int = 4000) -> str:
    """Concatenate events[0:up_to_idx] into a context string, truncating from the start."""
    parts: list[str] = []
    for ev in events[:up_to_idx]:
        parts.append(json.dumps(ev, ensure_ascii=False))
    text = "\n".join(parts)
    if len(text) > max_chars:
        return text[-max_chars:]
    return text


def run(
    inputs_dir: pathlib.Path,
    rolling_window: int = 50,
    baseline_min_sessions: int = 20,
    *,
    model_call: llm_judge.ModelCallable | None = None,
) -> Aggregate:
    paths = sorted(pathlib.Path(p) for p in glob.glob(str(inputs_dir / "*.jsonl")))
    if not paths:
        return Aggregate(status="blocked-input")

    # Window: most recent N sessions
    paths = paths[-rolling_window:]

    if len(paths) < baseline_min_sessions:
        # Below baseline — return aggregate with status flagged
        agg = Aggregate(n_sessions=len(paths), status="blocked-input")
        return agg

    agg = Aggregate(n_sessions=len(paths))

    for path in paths:
        events = session_log.load_session(path)
        mistakes = heuristic.classify(events)
        for m in mistakes:
            agg.n_mistakes += 1
            agg.by_kind[m.kind]["count"] += 1
            pre_context = _build_pre_context(events, m.pre_event_idx or 0)
            verdict = llm_judge.judge_documented(
                mistake_kind=m.kind,
                mistake_reason=m.reason or "",
                pre_context=pre_context,
                candidates=_candidate_notes_stub(pre_context),
                model_call=model_call,
            )
            if verdict.was_documented:
                agg.n_documented += 1
                agg.by_kind[m.kind]["documented"] += 1
            if verdict.needs_manual_review:
                agg.needs_manual_review += 1

    if agg.n_mistakes > 0:
        agg.rate = agg.n_documented / agg.n_mistakes
    else:
        agg.rate = 0.0  # zero mistakes is a valid (and great) outcome

    return agg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inputs", default=str(session_log._home() / "sessions"),
                   help="dir of session JSONL files")
    p.add_argument("--window", type=int, default=50, help="rolling window size in sessions")
    p.add_argument("--baseline-min-sessions", type=int, default=20)
    args = p.parse_args()

    agg = run(
        inputs_dir=pathlib.Path(args.inputs),
        rolling_window=args.window,
        baseline_min_sessions=args.baseline_min_sessions,
    )
    out = {
        "rate": agg.rate,
        "n_sessions": agg.n_sessions,
        "n_mistakes": agg.n_mistakes,
        "n_documented": agg.n_documented,
        "by_kind": dict(agg.by_kind),
        "needs_manual_review": agg.needs_manual_review,
        "status": agg.status,
    }
    print(json.dumps(out, indent=2))
    return 0 if agg.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
