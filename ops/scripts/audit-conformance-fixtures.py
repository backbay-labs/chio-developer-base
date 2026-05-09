#!/usr/bin/env python3
"""
audit-conformance-fixtures.py — credibility audit of the
conformance-harness-recall fixture set (Eval 3, PHASE-0.md).

The Skeptic's audit (M0) flagged two structural credibility risks in the
20 fixtures shipped under chio-pack/eval/fixtures/conformance-recall/:

  1. The auto-harvester (ops/scripts/harvest-conformance-fixtures.py) emits
     `canonical_fix[].section: "TODO: human-curated"` placeholders. Any
     fixture that retains a TODO section is fabricated ground truth.

  2. The same harvester falls back to `first_failure_message_guess()` which
     pulls the commit subject when no real failure string is in the commit
     body. A failure_message that is actually the subject line of a
     conventional commit ("fix(scope): …") is the wrong retrieval query —
     it tests "can the KB find files for this PR?", not the eval's actual
     question, "can the KB find the canonical fix for this test failure?"

This script catches both issues and exits non-zero so CI / Make targets
can gate on the result. Per task M0-D.1 in scratchpad.md.

Heuristic for "looks like a commit subject":
  - First non-empty line is < 80 chars long, AND
  - First line matches a Conventional-Commits prefix
    (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`,
    `style`, `build`, `ci`, `revert`) optionally with a `(scope)`,
    OR the message contains NONE of the typical real-failure tokens
    (FAIL, FAILED, FAIL!, expected:, assertion, traceback, error:,
    panicked, AssertionError, ...).

This is a heuristic — it will produce false positives on
test failures whose first line happens to look conventional. The script
flags rather than rewrites: human review converts a flag into either a
real curation or a `failure_message_kind: "real-test-failure"` annotation.

Exit codes:
    0 — all fixtures pass (no TODO sections, ≥10 real failure messages)
    1 — credibility floor breached
    2 — script error (PyYAML missing, fixtures dir missing, etc.)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml
except ImportError:
    print("error: PyYAML required (uv add pyyaml --group dev)", file=sys.stderr)
    sys.exit(2)


CONVENTIONAL_PREFIX_RE = re.compile(
    r"^(?:feat|fix|chore|docs|refactor|test|perf|style|build|ci|revert)"
    r"(?:\([^)]*\))?:\s+\S",
    re.IGNORECASE,
)

# Tokens that typically appear in a real test-failure dump but rarely in a
# pure commit subject. If any of these appear ANYWHERE in the message we
# treat it as a real failure even when the first line is short.
REAL_FAILURE_TOKENS = (
    "FAILED",
    "FAIL ",
    "FAIL!",
    "FAIL\t",
    "FAIL\n",
    "expected:",
    "got:",
    "assertion",
    "Traceback",
    "Error:",
    "error:",
    "panicked",
    "AssertionError",
    "InvalidSignature",
    "Reason:",
    "Got verdict",
    "Expected verdict",
    " > ",          # vitest/jest line prefix
    "::",           # pytest test path or Rust path
)

TODO_MARKERS = ("TODO: human-curated", "TODO:", "TODO ")


@dataclass
class Finding:
    fixture_id: str
    path: pathlib.Path
    todo_sections: int = 0
    failure_message_kind: str = "real-test-failure"
    failure_message_first_line: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    n_total: int = 0
    n_with_TODO: int = 0
    n_real_failure_messages: int = 0
    n_commit_subject_failure_messages: int = 0
    n_unknown: int = 0
    findings: list[Finding] = field(default_factory=list)


def _classify_failure_message(msg: str) -> tuple[str, str]:
    """Return (kind, first_line) where kind ∈
    {"real-test-failure", "commit-subject", "unknown"}."""
    lines = [ln for ln in msg.splitlines() if ln.strip()]
    first = lines[0].strip() if lines else ""
    if not first:
        return "unknown", ""

    has_real_token = any(tok.lower() in msg.lower() for tok in REAL_FAILURE_TOKENS)
    looks_conventional = bool(CONVENTIONAL_PREFIX_RE.match(first))
    is_short = len(first) < 80 and len(lines) <= 2

    if has_real_token:
        return "real-test-failure", first
    if looks_conventional and is_short:
        return "commit-subject", first
    if is_short:
        return "commit-subject", first
    # Multi-line message without any of the known real-failure tokens —
    # could be either, mark as unknown so a human picks.
    return "unknown", first


def _count_todo_sections(payload: dict[str, Any]) -> int:
    cf = payload.get("canonical_fix", [])
    if not isinstance(cf, list):
        return 0
    n = 0
    for entry in cf:
        if not isinstance(entry, dict):
            continue
        section = str(entry.get("section", ""))
        if any(marker in section for marker in TODO_MARKERS):
            n += 1
    return n


def discover_fixtures(fixtures_dir: pathlib.Path) -> list[pathlib.Path]:
    if not fixtures_dir.is_dir():
        print(f"error: fixtures dir {fixtures_dir} missing", file=sys.stderr)
        sys.exit(2)
    out: list[pathlib.Path] = []
    for p in sorted(fixtures_dir.glob("*.yml")):
        if p.name.startswith("_") or p.stem.endswith("_example"):
            continue
        if p.name == "example.yml":
            continue
        out.append(p)
    return out


def audit(fixtures_dir: pathlib.Path) -> AuditResult:
    result = AuditResult()
    for path in discover_fixtures(fixtures_dir):
        with path.open() as f:
            payload = yaml.safe_load(f) or {}
        if not isinstance(payload, dict):
            continue
        result.n_total += 1
        finding = Finding(
            fixture_id=str(payload.get("id", path.stem)),
            path=path,
        )
        todo_n = _count_todo_sections(payload)
        if todo_n:
            finding.todo_sections = todo_n
            result.n_with_TODO += 1
            finding.notes.append(f"{todo_n} canonical_fix[].section TODO marker(s)")

        msg = str(payload.get("failure_message", ""))
        # Honor an explicit author-tagged kind (set during prior audits).
        explicit_kind = payload.get("failure_message_kind")
        if isinstance(explicit_kind, str) and explicit_kind:
            kind = explicit_kind
            first_line = msg.splitlines()[0].strip() if msg.strip() else ""
            finding.notes.append(f"author-tagged failure_message_kind={kind}")
        else:
            kind, first_line = _classify_failure_message(msg)

        finding.failure_message_kind = kind
        finding.failure_message_first_line = first_line

        if kind == "real-test-failure":
            result.n_real_failure_messages += 1
        elif kind == "commit-subject":
            result.n_commit_subject_failure_messages += 1
        else:
            result.n_unknown += 1
        result.findings.append(finding)
    return result


def render_report(result: AuditResult) -> str:
    lines = []
    lines.append(f"conformance-recall fixture audit ({result.n_total} fixtures)")
    lines.append("=" * 60)
    lines.append(f"  TODO sections in canonical_fix:    {result.n_with_TODO}")
    lines.append(f"  real test-failure messages:        {result.n_real_failure_messages}")
    lines.append(f"  commit-subject-shaped messages:    {result.n_commit_subject_failure_messages}")
    lines.append(f"  ambiguous (need human review):     {result.n_unknown}")
    lines.append("")
    if result.n_with_TODO:
        lines.append("Fixtures with TODO sections (BLOCKER):")
        for f in result.findings:
            if f.todo_sections:
                lines.append(f"  - {f.fixture_id} ({f.todo_sections} TODO section(s))")
        lines.append("")
    if result.n_commit_subject_failure_messages:
        lines.append("Fixtures with commit-subject-shaped failure_message:")
        lines.append("  (consider tagging `failure_message_kind: \"commit-subject\"`)")
        for f in result.findings:
            if f.failure_message_kind == "commit-subject":
                lines.append(f"  - {f.fixture_id}: {f.failure_message_first_line[:70]}")
        lines.append("")
    if result.n_unknown:
        lines.append("Fixtures with ambiguous failure_message (review):")
        for f in result.findings:
            if f.failure_message_kind == "unknown":
                lines.append(f"  - {f.fixture_id}: {f.failure_message_first_line[:70]}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    default_dir = (
        pathlib.Path(__file__).resolve().parents[2]
        / "chio-pack"
        / "eval"
        / "fixtures"
        / "conformance-recall"
    )
    p.add_argument("--fixtures-dir", default=str(default_dir),
                   help="path to conformance-recall fixtures dir")
    p.add_argument("--min-real-failure-messages", type=int, default=10,
                   help="audit fails if fewer than N fixtures have real "
                        "test-failure messages (default: 10, per Skeptic target)")
    p.add_argument("--json", action="store_true",
                   help="emit machine-readable JSON instead of the report")
    args = p.parse_args()

    result = audit(pathlib.Path(args.fixtures_dir))

    if args.json:
        print(json.dumps({
            "n_total": result.n_total,
            "n_with_TODO": result.n_with_TODO,
            "n_real_failure_messages": result.n_real_failure_messages,
            "n_commit_subject_failure_messages": result.n_commit_subject_failure_messages,
            "n_unknown": result.n_unknown,
            "fixtures": [
                {
                    "id": f.fixture_id,
                    "path": str(f.path.relative_to(pathlib.Path.cwd()))
                            if f.path.is_absolute() else str(f.path),
                    "todo_sections": f.todo_sections,
                    "failure_message_kind": f.failure_message_kind,
                    "failure_message_first_line": f.failure_message_first_line,
                    "notes": f.notes,
                }
                for f in result.findings
            ],
        }, indent=2))
    else:
        print(render_report(result))

    failed = False
    if result.n_with_TODO > 0:
        print(
            f"FAIL: {result.n_with_TODO} fixture(s) carry TODO canonical_fix sections.",
            file=sys.stderr,
        )
        failed = True
    if result.n_real_failure_messages < args.min_real_failure_messages:
        print(
            f"FAIL: only {result.n_real_failure_messages} fixture(s) have real "
            f"test-failure messages (need ≥{args.min_real_failure_messages}).",
            file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
