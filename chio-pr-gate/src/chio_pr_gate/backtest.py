"""Local backtest harness for the advisory PR gate.

Default: expanded synthetic fixtures shaped like the plan metrics (P/R with
TP/FP/TN/FN). When ``--arc-repo`` points at a local arc checkout and ``gh`` can
list merged PRs, also replay path-based labels from recent PR file lists.

Honest mode notes are always written into the JSON report — synthetic-only
runs never claim a real 50-PR history score.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .policy import ChioImpactPolicy


@dataclass(frozen=True)
class Fixture:
    name: str
    changed_paths: list[str]
    pr_body: str
    expected_impact: bool
    source: str = "synthetic"


# Expanded synthetic set: covers CANONICAL_DOC / IMPLEMENTS / GUARDS / ack /
# true-negatives so P/R is not a trivial 4-row toy.
SYNTHETIC_FIXTURES = [
    Fixture("spec-change", ["vault/spec/receipt-commitment.md"], "", True),
    Fixture("engine-change", ["kb-engine/kb_engine/store/postgres.py"], "", True),
    Fixture("pack-tool-change", ["chio-pack/chio_pack/tools/kb_impact.py"], "", True),
    Fixture("guard-policy", ["chio-pack/chio_pack/policy/guards.py"], "", True),
    Fixture("docs-only", ["README.md"], "", False),
    Fixture("ci-only", [".github/workflows/eval.yml"], "", False),
    Fixture("makefile-only", ["Makefile"], "", False),
    Fixture("acknowledged", ["chio-pack/chio_pack/tools/kb_impact.py"], "kb-gate: ack", True),
    Fixture("adr-docs", ["decisions/ADR-0005-signed-retrieval-eval.md"], "", False),
    Fixture("infra-compose", ["infra/docker-compose.yml"], "", False),
]


def run_backtest(fixtures: list[Fixture] | None = None) -> dict[str, float | int | str | list]:
    policy = ChioImpactPolicy()
    fixtures = fixtures or list(SYNTHETIC_FIXTURES)
    tp = fp = tn = fn = 0
    per_fixture: list[dict] = []
    for fixture in fixtures:
        decision = policy.evaluate(fixture.changed_paths, pr_body=fixture.pr_body, advisory=True)
        predicted = bool(decision.impacts)
        if predicted and fixture.expected_impact:
            tp += 1
            label = "tp"
        elif predicted and not fixture.expected_impact:
            fp += 1
            label = "fp"
        elif not predicted and not fixture.expected_impact:
            tn += 1
            label = "tn"
        else:
            fn += 1
            label = "fn"
        per_fixture.append({
            "name": fixture.name,
            "source": fixture.source,
            "predicted_impact": predicted,
            "expected_impact": fixture.expected_impact,
            "label": label,
            "status": decision.status,
        })
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "fixtures": len(fixtures),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "meets_advisory_floor": precision >= 0.7 and recall >= 0.8,
        "per_fixture": per_fixture,
    }


def _heuristic_expected_impact(paths: list[str]) -> bool:
    """Proxy label when follow-up-within-14d ground truth is unavailable.

    Treats capability/receipt/guard/policy/core-types paths as high-signal —
    honest about being a heuristic, not a measured follow-up label.
    """
    needles = (
        "capability",
        "receipt",
        "guard",
        "policy",
        "chio-core-types",
        "chio-eval-receipt",
        "attenuation",
        "revocation",
    )
    for path in paths:
        lower = path.lower()
        if any(n in lower for n in needles):
            return True
        if lower.startswith("crates/core/") or lower.startswith("crates/trust/"):
            return True
    return False


def load_arc_pr_fixtures(arc_repo: Path, limit: int = 50) -> list[Fixture]:
    """Load recent merged PR file lists via ``gh``. Returns [] on failure."""
    try:
        raw = subprocess.check_output(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                _gh_repo_slug(arc_repo),
                "--state",
                "merged",
                "--limit",
                str(limit),
                "--json",
                "number,title,files,body",
            ],
            cwd=str(arc_repo),
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    fixtures: list[Fixture] = []
    for pr in payload:
        files = [f.get("path", "") for f in (pr.get("files") or []) if f.get("path")]
        if not files:
            continue
        number = pr.get("number")
        fixtures.append(
            Fixture(
                name=f"arc-pr-{number}",
                changed_paths=files,
                pr_body=pr.get("body") or "",
                expected_impact=_heuristic_expected_impact(files),
                source="arc-gh-heuristic",
            )
        )
    return fixtures


def _gh_repo_slug(arc_repo: Path) -> str:
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(arc_repo),
            text=True,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "bb-connor/arc"
    # git@github.com:bb-connor/arc.git or https://github.com/bb-connor/arc.git
    if url.endswith(".git"):
        url = url[:-4]
    if "github.com:" in url:
        return url.split("github.com:", 1)[1]
    if "github.com/" in url:
        return url.split("github.com/", 1)[1]
    return "bb-connor/arc"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arc-repo", default=None, help="local arc checkout for gh PR replay")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default="../vault/_meta/dashboards/pr-gate-backtest.json")
    args = parser.parse_args()

    fixtures = list(SYNTHETIC_FIXTURES)
    mode = "synthetic"
    note = "expanded synthetic fixtures; arc history unwired or unavailable"
    arc_path = Path(args.arc_repo).expanduser().resolve() if args.arc_repo else None
    if arc_path and arc_path.exists():
        arc_fixtures = load_arc_pr_fixtures(arc_path, limit=args.limit)
        if arc_fixtures:
            fixtures = fixtures + arc_fixtures
            mode = "synthetic+arc-gh-heuristic"
            note = (
                "Includes gh-merged PR file lists with heuristic expected_impact "
                "(capability/receipt/guard/core paths). Not follow-up-within-14d "
                "ground truth — stays advisory."
            )
        else:
            note = "arc repo present but gh PR list unavailable; synthetic fixtures only"

    report = run_backtest(fixtures)
    report["mode"] = mode
    report["note"] = note
    report["target_precision"] = 0.7
    report["target_recall"] = 0.8
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Keep JSON compact for dashboard; drop per_fixture if huge? Keep — useful.
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {k: report[k] for k in (
        "mode", "fixtures", "precision", "recall", "meets_advisory_floor",
        "true_positive", "false_positive", "true_negative", "false_negative", "note",
    )}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
