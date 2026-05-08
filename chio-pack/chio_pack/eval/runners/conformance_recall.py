"""Runner for the conformance-harness-recall outcome eval (Eval 3).

Scope today (Phase 0 fixture-validation):
  - Load fixtures from chio-pack/eval/fixtures/conformance-recall/*.yml.
  - Skip _example: true files.
  - Validate schema (id, failing_test, failure_message, canonical_fix[]).
  - Return Aggregate with status="blocked-input" — actual recall@3
    computation requires kb_search_code/kb_search_docs against a live
    KB stack (Phase 1.x).

Scope when Phase 1.x lands:
  - For each fixture, run kb_search_code(failure_message) and
    kb_search_docs(failure_message), each limit=10.
  - Take union of top-10, ranked by combined rank_components score.
  - Compute recall_at_3 = |canonical_fix_files ∩ top_3| / |canonical_fix_files|.
  - Aggregate: mean recall@3 across fixtures.

Edge cases per PHASE-0.md "Conformance-harness-recall edge cases":
  - Multi-fix fixtures: recall@3 caps at 3/N.
  - Spec-only fixes: same recall logic; count docs/spec files.
  - Inconclusive PRs: should already be dropped at curation time
    (per PHASE-0.md "drop-don't-guess"); validator flags fixtures with
    `_review:` field still present.
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


REQUIRED_FIELDS = {"id", "failing_test", "failure_message", "canonical_fix"}


@dataclass
class FixtureResult:
    id: str
    path: pathlib.Path
    valid: bool
    recall_at_3: float | None = None
    n_canonical: int = 0
    schema_errors: list[str] = field(default_factory=list)
    has_review_marker: bool = False  # uncurated fixture per PHASE-0.md


@dataclass
class Aggregate:
    rate: float | None = None  # mean recall@3
    n_fixtures: int = 0
    n_valid: int = 0
    n_invalid: int = 0
    n_uncurated: int = 0
    fixtures: list[FixtureResult] = field(default_factory=list)
    status: str = "ok"
    reason: str = ""


def _load_yaml(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        with path.open() as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def _validate_fixture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for f in sorted(REQUIRED_FIELDS - set(payload.keys())):
        errors.append(f"missing top-level field: {f}")
    cf = payload.get("canonical_fix", [])
    if not isinstance(cf, list) or not cf:
        errors.append("canonical_fix must be a non-empty list")
    else:
        for i, entry in enumerate(cf):
            if not isinstance(entry, dict):
                errors.append(f"canonical_fix[{i}] must be a mapping")
                continue
            if "file" not in entry:
                errors.append(f"canonical_fix[{i}].file missing")
            if "section" not in entry:
                errors.append(f"canonical_fix[{i}].section missing")
            elif "TODO: human-curated" in str(entry.get("section", "")):
                errors.append(
                    f"canonical_fix[{i}].section still has TODO placeholder — "
                    f"replace with a real anchor before use"
                )
    return errors


def discover_fixtures(fixtures_dir: pathlib.Path) -> list[pathlib.Path]:
    paths = sorted(pathlib.Path(p) for p in glob.glob(str(fixtures_dir / "*.yml")))
    real: list[pathlib.Path] = []
    for p in paths:
        payload = _load_yaml(p)
        if isinstance(payload, dict) and payload.get("_example") is True:
            continue
        real.append(p)
    return real


def run(fixtures_dir: pathlib.Path, fixture_count_min: int = 20) -> Aggregate:
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
        cf = payload.get("canonical_fix", [])
        n_canonical = len(cf) if isinstance(cf, list) else 0
        has_review = "_review" in payload
        result = FixtureResult(
            id=str(payload.get("id", path.stem)),
            path=path,
            valid=not errors,
            n_canonical=n_canonical,
            schema_errors=errors,
            has_review_marker=has_review,
        )
        agg.fixtures.append(result)
        if result.valid:
            agg.n_valid += 1
        else:
            agg.n_invalid += 1
        if has_review:
            agg.n_uncurated += 1

    if agg.n_invalid > 0:
        agg.status = "blocked-malformed"
        agg.reason = f"{agg.n_invalid} fixture(s) failed schema validation"
    elif agg.n_uncurated > 0:
        agg.status = "blocked-malformed"
        agg.reason = (
            f"{agg.n_uncurated} fixture(s) still have `_review:` markers — "
            f"complete curation before use as ground truth"
        )
    else:
        agg.status = "blocked-input"
        agg.reason = (
            "kb_search_code/kb_search_docs MCP calls are Phase 1.x; "
            "fixtures are schema-valid and curated"
        )
    return agg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_dir = pathlib.Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "conformance-recall"
    p.add_argument("--fixtures-dir", default=str(default_dir))
    p.add_argument("--fixture-count-min", type=int, default=20)
    args = p.parse_args()

    agg = run(pathlib.Path(args.fixtures_dir), fixture_count_min=args.fixture_count_min)
    out = {
        "rate": agg.rate,
        "n_fixtures": agg.n_fixtures,
        "n_valid": agg.n_valid,
        "n_invalid": agg.n_invalid,
        "n_uncurated": agg.n_uncurated,
        "status": agg.status,
        "reason": agg.reason,
        "fixtures": [
            {
                "id": fr.id, "valid": fr.valid,
                "n_canonical": fr.n_canonical,
                "has_review_marker": fr.has_review_marker,
                "schema_errors": fr.schema_errors,
            }
            for fr in agg.fixtures
        ],
    }
    print(json.dumps(out, indent=2))
    return 0 if agg.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
