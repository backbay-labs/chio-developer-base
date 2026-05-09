"""Run-0 calibration harness for the cap-error-explanation eval (Eval 4).

Per RATERS.md "Calibration cadence": one shared scenario rated by all
three raters; scores discussed; full scoring resumes. Run-0 is the
inaugural calibration.

This module:
  - Loads a cap-error scenario YAML.
  - For each of 3 raters (A / B / C per ADR-0004), prompts the rater
    to score the four rubric dimensions (clarity, accuracy,
    actionability, brevity) on the `raw` augmentation.
  - Captures pre-discussion scores. Post-discussion scores are filled
    in manually via the second invocation `--phase post`.
  - Writes (or appends) to `vault/_meta/dashboards/rater-calibration.md`
    under the canonical history table format.

Three rater types, all wrapped in a single `Rater` Protocol:
  - HumanRater       interactive (stdin) — for rater-A
  - AnthropicRater   Anthropic SDK call with rubric system prompt
  - DeterministicRater  fake; for tests + dry-runs without API access

The Anthropic rater is the production form for rater-B (Sonnet 4.6,
canonical rubric) and rater-C (Haiku 4.5, accuracy-emphasis rubric).

Run-0 is the bar for ADR-0002 sign-off — without it, the inter-rater
calibration row in RATERS.md stays TBD and Phase 1 cannot start.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

try:
    import yaml
except ImportError:
    print("error: PyYAML required", file=sys.stderr)
    raise


DIMENSIONS = ("clarity", "accuracy", "actionability", "brevity")


# Default Anthropic model names for raters B and C. These can be
# overridden at runtime via the env vars `CHIO_KB_RATER_B_MODEL` and
# `CHIO_KB_RATER_C_MODEL` so that operators can pin a specific snapshot
# without editing source. See ADR-0004 for the rationale on rater pool
# composition; per ADR-0004a the sunset criterion for "B and C are the
# same Anthropic family" lives in the calibration harness.
_DEFAULT_RATER_B_MODEL = "claude-sonnet-4-6"
_DEFAULT_RATER_C_MODEL = "claude-haiku-4-5-20251001"
_RATER_B_MODEL_ENV = "CHIO_KB_RATER_B_MODEL"
_RATER_C_MODEL_ENV = "CHIO_KB_RATER_C_MODEL"


def rater_b_model() -> str:
    """Resolved Anthropic model name for rater-B (canonical rubric)."""
    return os.environ.get(_RATER_B_MODEL_ENV, _DEFAULT_RATER_B_MODEL)


def rater_c_model() -> str:
    """Resolved Anthropic model name for rater-C (accuracy-emphasis rubric)."""
    return os.environ.get(_RATER_C_MODEL_ENV, _DEFAULT_RATER_C_MODEL)


# === Rubric source ===


CANONICAL_RUBRIC_SYSTEM = """\
You are a Chio capability-error rater. Score the explanation on four
dimensions, each 1–5. Use the canonical rubric anchors:

CLARITY
  1: Jargon-only; would prompt "what is this saying?"
  3: Failure identifiable but engineer needs source dive to be sure.
  5: Failure named and framed; engineer can describe it back without source diving.

ACCURACY
  1: Contradicts the code path; misleads engineer toward wrong subsystem.
  3: Correct in spirit but contains inaccurate claims.
  5: Every claim grounded in code or spec, with citations the engineer can follow.

ACTIONABILITY
  1: No next step; engineer must invent one.
  3: General direction ("check the revocation list") but not a specific action.
  5: Specific next step: file path, command to run, or symbol to inspect.

BREVITY
  1: More than 2× the minimum necessary length; engineer skims and misses the point.
  3: Roughly the right length but with paragraphs that could be cut.
  5: As short as possible but no shorter; nothing skimmable is wasted.

Reply with ONLY a JSON object:
{
  "clarity": <int 1-5>,
  "accuracy": <int 1-5>,
  "actionability": <int 1-5>,
  "brevity": <int 1-5>,
  "rationale": "<one sentence>"
}
"""


ACCURACY_EMPHASIS_SYSTEM = CANONICAL_RUBRIC_SYSTEM.replace(
    "ACCURACY\n"
    "  1: Contradicts the code path; misleads engineer toward wrong subsystem.\n"
    "  3: Correct in spirit but contains inaccurate claims.\n"
    "  5: Every claim grounded in code or spec, with citations the engineer can follow.",
    "ACCURACY (variant — line-number citable)\n"
    "  1: Contradicts the code path; misleads engineer toward wrong subsystem.\n"
    "  3: Correct in spirit but contains inaccurate or unverifiable claims.\n"
    "  5: Every claim is verifiable via line-number citation in the cited file. "
    "Hand-waving citations like 'see chio-kernel' without line-level grounding cap at 4.",
)


# === Rater protocols ===


@dataclass
class RaterScore:
    rater_id: str
    dimensions: dict[str, int] = field(default_factory=dict)
    rationale: str = ""

    def mean(self) -> float:
        if not self.dimensions:
            return 0.0
        return sum(self.dimensions.values()) / len(self.dimensions)


class Rater(Protocol):
    rater_id: str

    def score(self, scenario: dict[str, Any], augmentation_body: str) -> RaterScore: ...


# === Concrete rater impls ===


@dataclass
class DeterministicRater:
    """Fake rater. Returns deterministic scores derived from the
    scenario id + augmentation body. For dry-runs and tests.
    """

    rater_id: str
    base_scores: dict[str, int] = field(default_factory=lambda: {
        "clarity": 3, "accuracy": 3, "actionability": 3, "brevity": 4,
    })

    def score(self, scenario: dict[str, Any], augmentation_body: str) -> RaterScore:
        return RaterScore(
            rater_id=self.rater_id,
            dimensions=dict(self.base_scores),
            rationale=f"deterministic stub for {self.rater_id}",
        )


@dataclass
class HumanRater:
    """Interactive rater. Prompts the user via stdin for each dimension.

    Useful when a human (rater-A = @connor in our pool) is available.
    Skips with `--skip-human` flag in the CLI.
    """

    rater_id: str
    rubric_system: str = CANONICAL_RUBRIC_SYSTEM

    def score(self, scenario: dict[str, Any], augmentation_body: str) -> RaterScore:
        print(f"\n=== Rating as {self.rater_id} ===")
        print(f"Scenario id: {scenario.get('id')}")
        print(f"Scenario:\n{scenario.get('scenario', '')}")
        print(f"\nAugmentation body to rate:\n{augmentation_body}\n")
        scores: dict[str, int] = {}
        for d in DIMENSIONS:
            while True:
                raw = input(f"  {d} (1-5): ").strip()
                try:
                    v = int(raw)
                    if 1 <= v <= 5:
                        scores[d] = v
                        break
                except ValueError:
                    pass
                print("    enter an integer 1-5")
        rationale = input("  rationale (one line, optional): ").strip()
        return RaterScore(rater_id=self.rater_id, dimensions=scores, rationale=rationale)


@dataclass
class AnthropicRater:
    """Production LLM rater. Lazy-imports anthropic; falls back to
    raising RuntimeError with a clear message if the SDK is missing or
    ANTHROPIC_API_KEY is unset.
    """

    rater_id: str
    model: str
    rubric_system: str = CANONICAL_RUBRIC_SYSTEM

    def score(self, scenario: dict[str, Any], augmentation_body: str) -> RaterScore:
        try:
            import anthropic  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed. "
                "`uv pip install anthropic` or use --dry-run."
            ) from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Export it or use --dry-run."
            )
        client = anthropic.Anthropic()
        user = (
            f"Scenario id: {scenario.get('id')}\n\n"
            f"Scenario:\n{scenario.get('scenario', '')}\n\n"
            f"Augmentation body to rate:\n{augmentation_body}\n"
        )
        msg = client.messages.create(
            model=self.model,
            max_tokens=512,
            system=self.rubric_system,
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text  # type: ignore[attr-defined]
        return _parse_score(self.rater_id, text)


def _parse_score(rater_id: str, text: str) -> RaterScore:
    """Best-effort JSON extraction from the model's response."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return RaterScore(rater_id=rater_id, rationale=f"unparseable: {text[:200]}")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return RaterScore(rater_id=rater_id, rationale=f"json parse failed: {text[:200]}")
    dims = {d: int(data.get(d, 0)) for d in DIMENSIONS if d in data}
    return RaterScore(
        rater_id=rater_id,
        dimensions=dims,
        rationale=str(data.get("rationale", "")),
    )


# === Calibration runner ===


def default_pool() -> list[Rater]:
    """Three raters per ADR-0004 (Phase 0 pool). Construct fresh each
    time to keep state isolated across runs. Rater-B and rater-C model
    names resolve from env vars (`CHIO_KB_RATER_B_MODEL`,
    `CHIO_KB_RATER_C_MODEL`); see `rater_b_model` / `rater_c_model`.
    """
    return [
        HumanRater(rater_id="rater-A", rubric_system=CANONICAL_RUBRIC_SYSTEM),
        AnthropicRater(
            rater_id="rater-B",
            model=rater_b_model(),
            rubric_system=CANONICAL_RUBRIC_SYSTEM,
        ),
        AnthropicRater(
            rater_id="rater-C",
            model=rater_c_model(),
            rubric_system=ACCURACY_EMPHASIS_SYSTEM,
        ),
    ]


def dry_run_pool() -> list[Rater]:
    """Three deterministic raters for dry-run + tests."""
    return [
        DeterministicRater(rater_id="rater-A", base_scores={
            "clarity": 3, "accuracy": 4, "actionability": 4, "brevity": 4,
        }),
        DeterministicRater(rater_id="rater-B", base_scores={
            "clarity": 4, "accuracy": 4, "actionability": 3, "brevity": 5,
        }),
        DeterministicRater(rater_id="rater-C", base_scores={
            "clarity": 3, "accuracy": 3, "actionability": 4, "brevity": 4,
        }),
    ]


# LLM-LLM independence tripwire threshold. ADR-0004 admits rater-B and
# rater-C are within the same Anthropic family; a low disagreement-flag
# rate between them is *expected* but it also makes inter-rater agreement
# statistics optimistic. The tripwire fires at 5%: below that, treat
# disagreement statistics as suspect and reference ADR-0004a sunset
# criterion.
LLM_DISAGREEMENT_TRIPWIRE_RATE = 0.05
LLM_RATER_IDS = ("rater-B", "rater-C")
LLM_INDEPENDENCE_WARNING = (
    "rater-B / rater-C disagreement-flag rate {rate:.1%} is below the "
    "{threshold:.0%} tripwire ({flagged}/{total} dimensions flagged). "
    "Both raters are Anthropic-family LLMs (ADR-0004); inter-rater "
    "agreement statistics from this run may be optimistically biased. "
    "Treat the disagreement-flag rate as a lower bound; track the "
    "ADR-0004a sunset criterion (12 weeks from 2026-05-07; recruit "
    "non-Anthropic raters or re-affirm LLM-judge choice with cost data)."
)


@dataclass
class CalibrationRun:
    run_number: int
    date: str
    scenario_id: str
    augmentation_name: str
    scores: list[RaterScore] = field(default_factory=list)

    def disagreement_flags(self) -> dict[str, tuple[int, int]]:
        """For each dimension, return (max-rater, min-rater) where
        max - min > 1. Empty if no disagreement.
        """
        flags: dict[str, tuple[int, int]] = {}
        for d in DIMENSIONS:
            vals = [s.dimensions.get(d) for s in self.scores if d in s.dimensions]
            vals = [v for v in vals if v is not None]
            if len(vals) < 2:
                continue
            mx, mn = max(vals), min(vals)
            if mx - mn > 1:
                flags[d] = (mx, mn)
        return flags

    def llm_pair_disagreement_rate(self) -> tuple[int, int, float | None]:
        """Disagreement rate between the two LLM raters (B and C).

        Returns `(flagged, total, rate)` where:
          - `flagged` is the count of dimensions where
            |rater-B − rater-C| > 1.
          - `total` is the count of dimensions for which both raters
            produced a numeric score.
          - `rate` is `flagged / total`, or `None` if `total == 0`
            (e.g. both LLM raters errored out on this scenario).

        ADR-0004 rationale: rater-B (Sonnet) and rater-C (Haiku) are
        within the same Anthropic family. Low disagreement is expected;
        we surface the rate so a downstream check can fire when it's
        suspiciously low (see `LLM_DISAGREEMENT_TRIPWIRE_RATE`).
        """
        by_id = {s.rater_id: s for s in self.scores}
        b = by_id.get(LLM_RATER_IDS[0])
        c = by_id.get(LLM_RATER_IDS[1])
        if b is None or c is None:
            return (0, 0, None)
        flagged = 0
        total = 0
        for d in DIMENSIONS:
            bv = b.dimensions.get(d)
            cv = c.dimensions.get(d)
            if bv is None or cv is None:
                continue
            total += 1
            if abs(bv - cv) > 1:
                flagged += 1
        if total == 0:
            return (0, 0, None)
        return (flagged, total, flagged / total)

    def llm_independence_warning(
        self,
        *,
        threshold: float = LLM_DISAGREEMENT_TRIPWIRE_RATE,
    ) -> str | None:
        """Return a warning string if the LLM-LLM disagreement-flag
        rate is below `threshold`. None otherwise (or if both LLM
        raters failed to score this run).

        Threshold is exposed for testability; the production tripwire
        uses `LLM_DISAGREEMENT_TRIPWIRE_RATE` (5%).
        """
        flagged, total, rate = self.llm_pair_disagreement_rate()
        if rate is None:
            return None
        if rate >= threshold:
            return None
        return LLM_INDEPENDENCE_WARNING.format(
            rate=rate, threshold=threshold,
            flagged=flagged, total=total,
        )


def calibrate(
    scenario_path: Path,
    pool: list[Rater],
    *,
    augmentation_name: str = "raw",
    run_number: int = 0,
) -> CalibrationRun:
    """Run one calibration round on one scenario × one augmentation."""
    with scenario_path.open() as f:
        scenario = yaml.safe_load(f)
    augs = scenario.get("augmentations_under_test", [])
    aug = next((a for a in augs if a.get("name") == augmentation_name), None)
    if aug is None:
        raise ValueError(
            f"scenario {scenario_path} has no augmentation named "
            f"{augmentation_name!r}. Choices: {[a.get('name') for a in augs]}"
        )
    body = aug.get("body") or json.dumps(aug.get("body_source", {}), indent=2)

    run = CalibrationRun(
        run_number=run_number,
        date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
        scenario_id=scenario.get("id", scenario_path.stem),
        augmentation_name=augmentation_name,
    )
    for rater in pool:
        try:
            score = rater.score(scenario, body)
        except Exception as e:
            score = RaterScore(rater_id=rater.rater_id, rationale=f"error: {e}")
        run.scores.append(score)
    return run


def render_calibration_md(run: CalibrationRun) -> str:
    """Render a calibration run as a markdown rows-block."""
    lines = []
    for s in run.scores:
        for d in DIMENSIONS:
            val = s.dimensions.get(d, "TBD")
            lines.append(
                f"| {run.run_number} | {run.date} | {s.rater_id} | {d} | "
                f"{val} | TBD | TBD | {s.rationale[:60]} |"
            )
    return "\n".join(lines)


@dataclass
class ModelValidationResult:
    rater_id: str
    model: str
    ok: bool
    error: str | None = None


def validate_models(
    *,
    client_factory: Callable[[], Any] | None = None,
) -> list[ModelValidationResult]:
    """Smoke-check that rater-B and rater-C model names are live by
    issuing a 1-token dummy call to each.

    `client_factory` is injectable so tests can substitute a fake
    Anthropic client without monkey-patching the SDK; production
    callers leave it None and the real `anthropic.Anthropic()`
    client is constructed lazily.

    Returns one result per rater. The harness never raises; errors
    are captured per-rater so the operator can see both at once.
    """
    if client_factory is None:
        try:
            import anthropic  # type: ignore
        except ImportError:
            err = (
                "anthropic SDK not installed. "
                "`uv pip install anthropic` (or `--dry-run` for tests) "
                "to validate model names."
            )
            return [
                ModelValidationResult("rater-B", rater_b_model(), False, err),
                ModelValidationResult("rater-C", rater_c_model(), False, err),
            ]
        if not os.environ.get("ANTHROPIC_API_KEY"):
            err = "ANTHROPIC_API_KEY not set; cannot validate model names."
            return [
                ModelValidationResult("rater-B", rater_b_model(), False, err),
                ModelValidationResult("rater-C", rater_c_model(), False, err),
            ]
        client_factory = lambda: anthropic.Anthropic()  # noqa: E731

    client = client_factory()
    results: list[ModelValidationResult] = []
    for rater_id, model in (
        ("rater-B", rater_b_model()),
        ("rater-C", rater_c_model()),
    ):
        try:
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            results.append(ModelValidationResult(rater_id, model, True))
        except Exception as e:  # noqa: BLE001 — we want to surface every error
            results.append(ModelValidationResult(rater_id, model, False, str(e)))
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_scenario = (
        Path(__file__).resolve().parents[2]
        / "eval" / "fixtures" / "cap-error-explanation"
        / "revoked-cap-still-presented.yml"
    )
    p.add_argument("--scenario", default=str(default_scenario))
    p.add_argument("--augmentation", default="raw")
    p.add_argument("--run-number", type=int, default=0)
    p.add_argument("--dry-run", action="store_true",
                   help="Use deterministic raters; no API calls / no human input.")
    p.add_argument("--report", default=None,
                   help="Append rendered rows to this rater-calibration.md.")
    p.add_argument(
        "--validate-models",
        action="store_true",
        help=(
            "Issue a 1-token dummy call to the rater-B and rater-C "
            "models (resolved via CHIO_KB_RATER_B_MODEL and "
            "CHIO_KB_RATER_C_MODEL) and exit. Useful for catching "
            "bad model names before a real calibration run."
        ),
    )
    args = p.parse_args()

    if args.validate_models:
        results = validate_models()
        for r in results:
            tag = "ok" if r.ok else "FAIL"
            print(f"[{tag}] {r.rater_id} model={r.model}"
                  + (f" — {r.error}" if r.error else ""))
        if any(not r.ok for r in results):
            print(
                "error: one or more rater models did not validate. "
                "Set CHIO_KB_RATER_B_MODEL / CHIO_KB_RATER_C_MODEL or "
                "fix ANTHROPIC_API_KEY before running calibration.",
                file=sys.stderr,
            )
            return 2
        return 0

    pool = dry_run_pool() if args.dry_run else default_pool()
    run = calibrate(
        Path(args.scenario), pool,
        augmentation_name=args.augmentation,
        run_number=args.run_number,
    )

    out = {
        "run_number": run.run_number,
        "date": run.date,
        "scenario_id": run.scenario_id,
        "augmentation": run.augmentation_name,
        "scores": [
            {
                "rater_id": s.rater_id,
                "dimensions": s.dimensions,
                "mean": s.mean(),
                "rationale": s.rationale,
            }
            for s in run.scores
        ],
        "disagreement_flags": run.disagreement_flags(),
    }
    flagged, total, rate = run.llm_pair_disagreement_rate()
    out["llm_pair_disagreement"] = {
        "flagged": flagged,
        "total": total,
        "rate": rate,
        "threshold": LLM_DISAGREEMENT_TRIPWIRE_RATE,
    }
    indep_warning = run.llm_independence_warning()
    if indep_warning is not None:
        out["llm_independence_warning"] = indep_warning
        # Also surface to stderr so a CI log captures it independent of
        # how the JSON gets consumed.
        print(f"warning: {indep_warning}", file=sys.stderr)
    print(json.dumps(out, indent=2))

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        with Path(args.report).open("a") as f:
            f.write("\n<!-- calibration appended " + run.date + " -->\n")
            f.write(render_calibration_md(run))
            f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
