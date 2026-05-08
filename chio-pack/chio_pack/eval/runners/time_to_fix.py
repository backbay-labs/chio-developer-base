"""Runner for the time-to-first-correct-fix outcome eval (Eval 1).

Scope today (Phase 0 fixture-validation):
  - Load fixtures from chio-pack/eval/fixtures/time-to-fix/*.yml.
  - Skip files with _example: true.
  - Validate each fixture against the expected schema (id, source,
    arc_commit_before, arc_commit_after, agent.*, seed_state.*,
    expected.*, scoring.*).
  - Optionally verify arc commit SHAs exist in the configured arc clone.
  - Return Aggregate with status="blocked-input" because the actual
    agent runner (codex-cli / claude-code spawning) is Phase 1.5+.

Scope when Phase 1.5 lands:
  - Spawn the configured agent in a fresh worktree at arc_commit_before.
  - Provide MCP gateway access; record tool calls.
  - Wait for the agent to declare done OR budget exhaustion.
  - Verify expected.tests_must_pass against post-agent code.
  - Compute score per fixture's scoring weights; aggregate to mean.

Output:
  Aggregate dataclass with rate (mean score), per-fixture results,
  and status. Status values: "ok", "blocked-input", "blocked-fixtures",
  "blocked-malformed".
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML required", file=sys.stderr)
    raise


REQUIRED_TOP_FIELDS = {"id", "source", "arc_commit_before", "arc_commit_after",
                       "agent", "seed_state", "expected", "scoring"}
REQUIRED_AGENT_FIELDS = {"runner", "model", "budget_seconds", "budget_tool_calls"}
REQUIRED_SEED_FIELDS = {"starting_branch", "failing_test"}
REQUIRED_EXPECTED_FIELDS = {"patch_signature", "tests_must_pass"}
REQUIRED_SCORING_FIELDS = {"time_weight", "tool_call_weight", "zero_score_if"}


@dataclass
class FixtureResult:
    id: str
    path: pathlib.Path
    valid: bool
    score: float | None = None
    schema_errors: list[str] = field(default_factory=list)


@dataclass
class Aggregate:
    rate: float | None = None
    n_fixtures: int = 0
    n_valid: int = 0
    n_invalid: int = 0
    fixtures: list[FixtureResult] = field(default_factory=list)
    status: str = "ok"
    reason: str = ""


def _validate_fixture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP_FIELDS - set(payload.keys())
    for f in sorted(missing):
        errors.append(f"missing top-level field: {f}")
    agent = payload.get("agent", {})
    if isinstance(agent, dict):
        for f in sorted(REQUIRED_AGENT_FIELDS - set(agent.keys())):
            errors.append(f"missing agent.{f}")
    else:
        errors.append("agent is not a mapping")
    seed = payload.get("seed_state", {})
    if isinstance(seed, dict):
        for f in sorted(REQUIRED_SEED_FIELDS - set(seed.keys())):
            errors.append(f"missing seed_state.{f}")
    expected = payload.get("expected", {})
    if isinstance(expected, dict):
        for f in sorted(REQUIRED_EXPECTED_FIELDS - set(expected.keys())):
            errors.append(f"missing expected.{f}")
        if "tests_must_pass" in expected:
            tmp = expected["tests_must_pass"]
            if not isinstance(tmp, list) or not tmp:
                errors.append("expected.tests_must_pass must be a non-empty list")
    scoring = payload.get("scoring", {})
    if isinstance(scoring, dict):
        for f in sorted(REQUIRED_SCORING_FIELDS - set(scoring.keys())):
            errors.append(f"missing scoring.{f}")
        tw = scoring.get("time_weight")
        cw = scoring.get("tool_call_weight")
        if isinstance(tw, (int, float)) and isinstance(cw, (int, float)):
            if abs(tw + cw - 1.0) > 1e-6:
                errors.append(
                    f"scoring weights must sum to 1.0, got {tw} + {cw} = {tw + cw}"
                )
    return errors


def _load_yaml(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        with path.open() as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def discover_fixtures(fixtures_dir: pathlib.Path) -> list[pathlib.Path]:
    paths = sorted(pathlib.Path(p) for p in glob.glob(str(fixtures_dir / "*.yml")))
    real: list[pathlib.Path] = []
    for p in paths:
        payload = _load_yaml(p)
        if isinstance(payload, dict) and payload.get("_example") is True:
            continue
        real.append(p)
    return real


def run(fixtures_dir: pathlib.Path, fixture_count_min: int = 8) -> Aggregate:
    paths = discover_fixtures(fixtures_dir)
    if len(paths) < fixture_count_min:
        return Aggregate(
            n_fixtures=len(paths),
            status="blocked-fixtures",
            reason=f"have {len(paths)}, need ≥ {fixture_count_min}",
        )

    agg = Aggregate(n_fixtures=len(paths))
    for path in paths:
        payload = _load_yaml(path)
        if payload is None:
            agg.fixtures.append(FixtureResult(
                id=path.stem, path=path, valid=False,
                schema_errors=["file is not valid YAML"],
            ))
            agg.n_invalid += 1
            continue
        errors = _validate_fixture(payload)
        result = FixtureResult(
            id=str(payload.get("id", path.stem)),
            path=path,
            valid=not errors,
            schema_errors=errors,
        )
        agg.fixtures.append(result)
        if result.valid:
            agg.n_valid += 1
        else:
            agg.n_invalid += 1

    if agg.n_invalid > 0:
        agg.status = "blocked-malformed"
        agg.reason = f"{agg.n_invalid} fixture(s) failed schema validation"
    else:
        # Schemas valid but agent runner not yet implemented.
        agg.status = "blocked-input"
        agg.reason = (
            "agent runner (codex-cli / claude-code spawning) is Phase 1.5+; "
            "fixtures are schema-valid"
        )
    return agg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_dir = pathlib.Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "time-to-fix"
    p.add_argument("--fixtures-dir", default=str(default_dir))
    p.add_argument("--fixture-count-min", type=int, default=8)
    args = p.parse_args()

    agg = run(pathlib.Path(args.fixtures_dir), fixture_count_min=args.fixture_count_min)
    out = {
        "rate": agg.rate,
        "n_fixtures": agg.n_fixtures,
        "n_valid": agg.n_valid,
        "n_invalid": agg.n_invalid,
        "status": agg.status,
        "reason": agg.reason,
        "fixtures": [
            {"id": fr.id, "valid": fr.valid, "schema_errors": fr.schema_errors}
            for fr in agg.fixtures
        ],
    }
    print(json.dumps(out, indent=2))
    return 0 if agg.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
