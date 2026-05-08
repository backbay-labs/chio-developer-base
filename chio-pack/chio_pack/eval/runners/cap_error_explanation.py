"""Runner for the capability-error-explanation outcome eval (Eval 4).

Scope today (Phase 0 fixture-validation):
  - Load fixtures from chio-pack/eval/fixtures/cap-error-explanation/*.yml.
  - Skip _example: true files.
  - Validate schema (id, scenario, context_query, augmentations_under_test).
  - Verify each fixture exercises all four canonical augmentations
    (raw, kb_brief_feature, +signed_receipt, +episode_link).
  - Return Aggregate with status="blocked-input" — actual scoring
    requires the rater pool (per ADR-0004) and the augmentation tools
    (kb_brief_feature, signed-retrieval — Phase 1.x and 2B).

Scope when raters + tools are wired (Phase 1.5 + ADR-0004 sign-off):
  - For each scenario × augmentation, build the rendered explanation:
      raw                             → fixture's `body` verbatim
      kb_brief_feature                → invoke kb_brief_feature with args
      kb_brief_feature + signed_receipt → above + Phase 2B receipt
      kb_brief_feature + episode_link → above + episode link
  - Submit to each of three raters per RATERS.md (rater-A human,
    rater-B Sonnet 4.6 canonical rubric, rater-C Haiku 4.5 accuracy-
    emphasis variant per rubrics-accuracy-emphasis.md).
  - Compute per-scenario score = mean(clarity, accuracy, actionability,
    brevity).
  - Disagreement-flag fires when any dimension's max - min > 1; rater-D
    (Opus 4.7) re-rates that dimension.
  - Aggregate per-augmentation: mean across scenarios across raters.
  - Phase 0 baseline: only `raw` augmentation; the other three may
    improve in Phase 1+ as kb_brief_feature evolves.
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


REQUIRED_FIELDS = {"id", "scenario", "context_query", "augmentations_under_test"}
CANONICAL_AUGMENTATIONS = {
    "raw",
    "kb_brief_feature",
    "kb_brief_feature + signed_receipt",
    "kb_brief_feature + episode_link",
}


@dataclass
class FixtureResult:
    id: str
    path: pathlib.Path
    valid: bool
    augmentations_present: set[str] = field(default_factory=set)
    augmentations_missing: set[str] = field(default_factory=set)
    schema_errors: list[str] = field(default_factory=list)


@dataclass
class Aggregate:
    rate: float | None = None
    n_fixtures: int = 0
    n_valid: int = 0
    n_invalid: int = 0
    n_with_full_augmentation_set: int = 0
    fixtures: list[FixtureResult] = field(default_factory=list)
    status: str = "ok"
    reason: str = ""


def _load_yaml(path: pathlib.Path) -> dict[str, Any] | None:
    try:
        with path.open() as f:
            return yaml.safe_load(f)
    except yaml.YAMLError:
        return None


def _validate_fixture(payload: dict[str, Any]) -> tuple[list[str], set[str]]:
    errors: list[str] = []
    augs_present: set[str] = set()

    for f in sorted(REQUIRED_FIELDS - set(payload.keys())):
        errors.append(f"missing top-level field: {f}")

    auts = payload.get("augmentations_under_test", [])
    if not isinstance(auts, list) or not auts:
        errors.append("augmentations_under_test must be a non-empty list")
    else:
        for i, aut in enumerate(auts):
            if not isinstance(aut, dict):
                errors.append(f"augmentations_under_test[{i}] must be a mapping")
                continue
            name = aut.get("name")
            if not name:
                errors.append(f"augmentations_under_test[{i}].name missing")
                continue
            augs_present.add(name)
            # raw augmentation must have static body; others have body OR body_source
            if name == "raw":
                if "body" not in aut:
                    errors.append(
                        f"augmentations_under_test[{i}] (raw) requires a `body` field"
                    )
            else:
                if "body" not in aut and "body_source" not in aut:
                    errors.append(
                        f"augmentations_under_test[{i}] ({name}) requires "
                        f"`body` or `body_source`"
                    )

    return errors, augs_present


def discover_fixtures(fixtures_dir: pathlib.Path) -> list[pathlib.Path]:
    paths = sorted(pathlib.Path(p) for p in glob.glob(str(fixtures_dir / "*.yml")))
    real: list[pathlib.Path] = []
    for p in paths:
        payload = _load_yaml(p)
        if isinstance(payload, dict) and payload.get("_example") is True:
            continue
        real.append(p)
    return real


def run(fixtures_dir: pathlib.Path, fixture_count_min: int = 10) -> Aggregate:
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
        errors, augs = _validate_fixture(payload)
        missing = CANONICAL_AUGMENTATIONS - augs
        result = FixtureResult(
            id=str(payload.get("id", path.stem)),
            path=path,
            valid=not errors,
            augmentations_present=augs,
            augmentations_missing=missing,
            schema_errors=errors,
        )
        agg.fixtures.append(result)
        if result.valid:
            agg.n_valid += 1
        else:
            agg.n_invalid += 1
        if not missing:
            agg.n_with_full_augmentation_set += 1

    if agg.n_invalid > 0:
        agg.status = "blocked-malformed"
        agg.reason = f"{agg.n_invalid} fixture(s) failed schema validation"
    elif agg.n_with_full_augmentation_set < agg.n_fixtures:
        # Some fixtures have an incomplete augmentation set — still "blocked-input"
        # but the report should highlight the gap.
        agg.status = "blocked-input"
        agg.reason = (
            f"rater pool + augmentation tools are Phase 1.x; "
            f"fixtures are schema-valid; "
            f"{agg.n_with_full_augmentation_set}/{agg.n_fixtures} fixtures "
            f"exercise all four canonical augmentations"
        )
    else:
        agg.status = "blocked-input"
        agg.reason = (
            "rater pool (ADR-0004) + augmentation tools are Phase 1.x; "
            "all fixtures schema-valid with full augmentation set"
        )
    return agg


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_dir = pathlib.Path(__file__).resolve().parents[3] / "eval" / "fixtures" / "cap-error-explanation"
    p.add_argument("--fixtures-dir", default=str(default_dir))
    p.add_argument("--fixture-count-min", type=int, default=10)
    args = p.parse_args()

    agg = run(pathlib.Path(args.fixtures_dir), fixture_count_min=args.fixture_count_min)
    out = {
        "rate": agg.rate,
        "n_fixtures": agg.n_fixtures,
        "n_valid": agg.n_valid,
        "n_invalid": agg.n_invalid,
        "n_with_full_augmentation_set": agg.n_with_full_augmentation_set,
        "status": agg.status,
        "reason": agg.reason,
        "fixtures": [
            {
                "id": fr.id, "valid": fr.valid,
                "augmentations_present": sorted(fr.augmentations_present),
                "augmentations_missing": sorted(fr.augmentations_missing),
                "schema_errors": fr.schema_errors,
            }
            for fr in agg.fixtures
        ],
    }
    print(json.dumps(out, indent=2))
    return 0 if agg.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
