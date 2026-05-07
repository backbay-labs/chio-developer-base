"""LLM-judge for repeated-mistake-rate (Eval 2).

For each candidate mistake produced by heuristic.py, decide whether a
vault note / ADR / episode that would have prevented it was already
present at retrieval-top-3 for the agent's pre-mistake context.

Output schema per chio-pack/eval/rubrics.md "LLM-judge prompt skeleton":

    {
      "was_documented": bool,
      "evidence": [note_ids],
      "confidence": float,
      "rationale": "..."
    }

Confidence < 0.5 → re-judge with a second pass.
Confidence < 0.3 on second pass → flag for manual review.

This module deliberately keeps the API small: one entry point
`judge_documented(mistake, context, candidates)` that returns a Verdict.
The Anthropic SDK call is isolated so the runner can mock it for tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable


# Default model for the judge. ADR-0004 names Sonnet 4.6 as rater-B; this
# module is shared infrastructure (not the cap-error rater) but uses the
# same default model for consistency.
DEFAULT_MODEL = "claude-sonnet-4-6"

CONFIDENCE_RE_JUDGE_THRESHOLD = 0.5
CONFIDENCE_MANUAL_REVIEW_THRESHOLD = 0.3


@dataclass
class Verdict:
    was_documented: bool
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""
    needs_manual_review: bool = False


SYSTEM_PROMPT = """\
You are a judge for the Chio repeated-mistake-rate eval. Given a mistake
the agent made and a list of candidate vault notes that were in retrieval
top-3 for the agent's pre-mistake context, decide:

1. Was the relevant prevention documented in those notes?
2. Which note(s) document it (cite by `id`).
3. Confidence (0.0 to 1.0).
4. One-sentence rationale.

Reply with ONLY a JSON object matching this schema:

{
  "was_documented": <bool>,
  "evidence": [<note_id>, ...],
  "confidence": <float 0.0-1.0>,
  "rationale": "<one sentence>"
}
"""


def _build_user_prompt(
    mistake_kind: str,
    mistake_reason: str,
    pre_context: str,
    candidates: list[dict[str, Any]],
) -> str:
    cand_lines = []
    for c in candidates:
        cand_lines.append(f"- id: {c.get('id', '?')}\n  title: {c.get('title', '?')}\n  excerpt: {c.get('excerpt', '?')[:300]}")
    return (
        f"Mistake kind: {mistake_kind}\n"
        f"Mistake reason: {mistake_reason}\n\n"
        f"Agent's pre-mistake context (last 4k chars):\n{pre_context[:4000]}\n\n"
        f"Candidate vault notes that were in retrieval top-3 for that context:\n"
        + "\n".join(cand_lines)
    )


def _parse_response(text: str) -> Verdict | None:
    """Best-effort JSON extraction from the model output."""
    # Trim to the first {...} block.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return Verdict(
        was_documented=bool(data.get("was_documented", False)),
        evidence=list(data.get("evidence", []) or []),
        confidence=float(data.get("confidence", 0.0) or 0.0),
        rationale=str(data.get("rationale", "") or ""),
    )


# Type for the model-call callable. Allows tests to inject a fake.
ModelCallable = Callable[[str, str], str]


def _default_model_call(system_prompt: str, user_prompt: str) -> str:
    """Anthropic SDK call. Lazily imported so the module loads without the SDK."""
    try:
        import anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "anthropic SDK not installed. `pip install anthropic` or set "
            "CHIO_KB_LLM_JUDGE_BACKEND=mock for tests."
        ) from e
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=os.environ.get("CHIO_KB_LLM_JUDGE_MODEL", DEFAULT_MODEL),
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text  # type: ignore[attr-defined]


def judge_documented(
    mistake_kind: str,
    mistake_reason: str,
    pre_context: str,
    candidates: list[dict[str, Any]],
    *,
    model_call: ModelCallable | None = None,
    max_passes: int = 2,
) -> Verdict:
    """Run the judge with up-to-max_passes retries on low confidence.

    Args:
        mistake_kind, mistake_reason: from the heuristic classifier.
        pre_context: agent's last 4k chars before the mistake.
        candidates: vault notes in retrieval top-3 for that context.
            Each: {"id": str, "title": str, "excerpt": str}.
        model_call: override the model invocation (for tests).
        max_passes: re-judge attempts on low confidence.

    Returns:
        Verdict; if confidence < 0.3 after max_passes,
        needs_manual_review=True.
    """
    call = model_call or _default_model_call
    user_prompt = _build_user_prompt(mistake_kind, mistake_reason, pre_context, candidates)

    last_verdict: Verdict | None = None
    for _pass in range(max_passes):
        try:
            text = call(SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            return Verdict(
                was_documented=False,
                rationale=f"model call failed: {e}",
                needs_manual_review=True,
            )
        v = _parse_response(text)
        if v is None:
            last_verdict = Verdict(
                was_documented=False,
                rationale="model produced unparseable response",
            )
            continue
        last_verdict = v
        if v.confidence >= CONFIDENCE_RE_JUDGE_THRESHOLD:
            return v

    # Out of retries.
    if last_verdict is None:
        return Verdict(was_documented=False, needs_manual_review=True)
    if last_verdict.confidence < CONFIDENCE_MANUAL_REVIEW_THRESHOLD:
        last_verdict.needs_manual_review = True
    return last_verdict
