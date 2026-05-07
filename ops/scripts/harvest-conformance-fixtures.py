#!/usr/bin/env python3
"""
harvest-conformance-fixtures.py — Phase 0 fixture generator for the
`conformance-harness-recall` outcome eval (chio-pack/eval/PHASE-0.md, Eval 3).

Walks arc git history for commits that modified tests/conformance/. For each,
identifies the failing-test signature (best-effort) and the canonical fix files,
and emits one fixture YAML per qualifying commit.

This is best-effort. Output fixtures carry a `_review:` field with confidence
level; PHASE-0.md says ambiguous fixtures should be DROPPED, not guessed at —
this script flags low-confidence ones instead of auto-resolving them.

Phase 0 deliverable. Tracked by PLAN.md Phase 0 task 0.3.

Usage:
    uv run python ops/scripts/harvest-conformance-fixtures.py \\
        --arc-repo ../arc \\
        --out chio-pack/eval/fixtures/conformance-recall \\
        --target 20

After running, REVIEW each fixture and:
  1. Drop fixtures with confidence=low.
  2. Replace canonical_fix[].section "TODO: human-curated" with real anchors.
  3. Verify failure_message reads like a real test failure (not a commit subject).
  4. Delete the `_review` field once curated.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFORMANCE_PATHS = [
    "tests/conformance/",
    "crates/chio-conformance/",
    "integrations/mcp-adapter/tests/",
]

# Files that count as "test" surfaces for the harvester's purposes.
# Arc uses several conformance test idioms — pytest, jest, Rust integration,
# JSON scenario fixtures, and peer client/server programs.
TEST_FILE_RE = re.compile(
    r"(?:^|/)(?:"
    r"test_[^/]+\.py"               # pytest
    r"|[^/]+\.test\.ts"             # jest TS
    r"|[^/]+\.test\.js"             # jest JS
    r"|conformance[^/]*\.rs"        # Rust integration tests like conformance_cli.rs
    r")$"
)

# Additional test-surface predicates that need path-prefix awareness.
def is_test_file(path: str) -> bool:
    if TEST_FILE_RE.search(path):
        return True
    # JSON scenario fixtures count as tests
    if path.startswith("tests/conformance/native/scenarios/") and path.endswith(".json"):
        return True
    # Rust integration tests under crates/.../tests/
    if (
        path.startswith("crates/")
        and "/tests/" in path
        and path.endswith(".rs")
        and "conformance" in path.lower()
    ):
        return True
    if path.startswith("integrations/mcp-adapter/tests/") and "conformance" in path.lower():
        return True
    return False


SKIP_MARKER_RE = re.compile(
    r"(@pytest\.mark\.(?:skip|xfail)\b"
    r"|test\.skip\b"
    r"|describe\.skip\b"
    r"|#\[ignore\]"
    r"|@SkipFor\b)"
)


def git(args: list[str], repo: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo)] + args,
        check=True, capture_output=True, text=True,
    )
    return res.stdout


def candidate_commits(repo: Path, search_limit: int, branch: str) -> list[str]:
    """Commit SHAs (newest first) on `branch` that touched any conformance path."""
    cmd = ["log", branch, "--format=%H", "--no-merges", f"-n{search_limit}"]
    cmd.append("--")
    cmd.extend(CONFORMANCE_PATHS)
    out = git(cmd, repo).strip()
    return out.splitlines() if out else []


def changed_files(repo: Path, sha: str) -> list[str]:
    out = git(["show", "--name-only", "--format=", sha], repo).strip()
    return [line for line in out.splitlines() if line]


def commit_subject(repo: Path, sha: str) -> str:
    return git(["log", "--format=%s", "-n1", sha], repo).strip()


def commit_body(repo: Path, sha: str) -> str:
    return git(["log", "--format=%b", "-n1", sha], repo).strip()


def commit_date(repo: Path, sha: str) -> str:
    return git(["log", "--format=%cI", "-n1", sha], repo).strip()


def diff_for_file(repo: Path, sha: str, path: str) -> str:
    return git(["show", "--format=", sha, "--", path], repo)


def looks_like_canonical_fix(path: str) -> bool:
    if path.startswith("tests/"):
        return False
    if path.endswith((".lock", ".toml")):
        return False  # build manifests rarely encode the fix
    return any(path.startswith(prefix) for prefix in (
        "crates/",
        "spec/",
        "docs/standards/",
        "docs/conformance/",
        "docs/sdk/",
        "docs/protocol/",
        "docs/release/",
        "docs/mcp/",
    ))


def extract_test_signatures(diff: str, file_path: str) -> list[str]:
    """Best-effort signature extraction from added test bodies in a diff."""
    sigs: list[str] = []
    if file_path.endswith(".py"):
        for m in re.finditer(r"^\+\s*def (test_[A-Za-z0-9_]+)\s*\(", diff, re.MULTILINE):
            sigs.append(f"{file_path}::{m.group(1)}")
    elif file_path.endswith((".test.ts", ".test.js")):
        for m in re.finditer(
            r"^\+\s*(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]",
            diff, re.MULTILINE,
        ):
            sigs.append(f"{file_path}:{m.group(1)}")
    elif file_path.endswith(".rs"):
        # Rust convention: test functions are conventionally named test_*.
        # This misses Rust tests with non-conforming names but avoids
        # capturing every Rust function in the diff.
        for m in re.finditer(
            r"^\+\s*(?:async\s+)?fn (test_[A-Za-z0-9_]+)\s*\(",
            diff, re.MULTILINE,
        ):
            sigs.append(f"{file_path}::{m.group(1)}")
    elif file_path.endswith(".json"):
        # Scenario JSON files: signature is the file plus the scenario id
        # if one is present in the added lines.
        for m in re.finditer(r'^\+\s*"id"\s*:\s*"([^"]+)"', diff, re.MULTILINE):
            sigs.append(f"{file_path}#{m.group(1)}")
            break
        if not sigs:
            sigs.append(file_path)
    return sigs


def diff_has_skip_marker_removal(diff: str) -> bool:
    """A `-` line that contains a skip marker → confidence boost."""
    for line in diff.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            if SKIP_MARKER_RE.search(line):
                return True
    return False


def first_failure_message_guess(commit_subj: str, body: str) -> str:
    text = f"{commit_subj}\n{body}".strip()
    for m in re.finditer(r"`([^`]{20,200})`", text):
        return m.group(1)
    return text.splitlines()[0] if text else ""


def render_fixture_yaml(fixture: dict[str, Any]) -> str:
    """Minimal YAML emitter — same flavor as migrate-seeds.py."""
    def s(v: Any) -> str:
        if isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        if isinstance(v, bool):
            return "true" if v else "false"
        if v is None:
            return "null"
        if isinstance(v, (int, float)):
            return json.dumps(v)
        raise TypeError(type(v))

    lines: list[str] = []
    for k, v in fixture.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
                continue
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        prefix = "  - " if first else "    "
                        lines.append(f"{prefix}{ik}: {s(iv)}")
                        first = False
                else:
                    lines.append(f"  - {s(item)}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for ik, iv in v.items():
                lines.append(f"  {ik}: {s(iv)}")
        elif isinstance(v, str) and "\n" in v:
            lines.append(f"{k}: |")
            for ln in v.splitlines():
                lines.append(f"  {ln}")
        else:
            lines.append(f"{k}: {s(v)}")
    return "\n".join(lines) + "\n"


def harvest(repo: Path, target: int, search_limit: int, branch: str) -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    commits = candidate_commits(repo, search_limit, branch)
    for sha in commits:
        files = changed_files(repo, sha)
        test_files = [f for f in files if is_test_file(f)]
        fix_files = [f for f in files if looks_like_canonical_fix(f)]
        if not test_files or not fix_files:
            continue

        subj = commit_subject(repo, sha)
        body = commit_body(repo, sha)
        date = commit_date(repo, sha)

        signatures: list[str] = []
        confidence = "low"
        for tf in test_files:
            d = diff_for_file(repo, sha, tf)
            sigs = extract_test_signatures(d, tf)
            if sigs:
                signatures.extend(sigs)
                if diff_has_skip_marker_removal(d):
                    confidence = "high"
                elif confidence == "low":
                    confidence = "medium"
        if not signatures:
            continue

        primary_sig = signatures[0]
        if primary_sig in seen_signatures:
            continue
        seen_signatures.add(primary_sig)

        fixture: dict[str, Any] = {
            "id":              f"{sha[:10]}-{Path(test_files[0]).stem}",
            "_review":         f"confidence={confidence}; auto-harvested from {sha} on {date}",
            "failing_test":    primary_sig,
        }
        if signatures[1:]:
            fixture["alternate_signatures"] = signatures[1:]
        fixture["failure_message"]    = first_failure_message_guess(subj, body)
        fixture["canonical_fix"]      = [
            {"file": ff, "section": "TODO: human-curated"} for ff in fix_files
        ]
        fixture["relevant_arc_commit"] = sha
        fixture["commit_subject"]      = subj
        fixture["commit_date"]         = date

        fixtures.append(fixture)
        if len(fixtures) >= target:
            break
    return fixtures


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arc-repo", required=True, help="path to arc repo clone")
    p.add_argument("--out", required=True, help="output dir for fixture *.yml files")
    p.add_argument("--target", type=int, default=20, help="number of fixtures to emit")
    p.add_argument("--search-limit", type=int, default=400, help="max commits scanned")
    p.add_argument("--branch", default="HEAD", help="branch (or ref) to walk; default HEAD")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    repo = Path(args.arc_repo)
    if not (repo / ".git").exists():
        print(f"error: --arc-repo {repo} is not a git repo", file=sys.stderr)
        return 2

    fixtures = harvest(repo, target=args.target, search_limit=args.search_limit, branch=args.branch)

    if len(fixtures) < args.target:
        print(
            f"warning: harvested only {len(fixtures)}/{args.target} fixtures "
            f"(scanned {args.search_limit} commits). Increase --search-limit "
            f"or curate manually.",
            file=sys.stderr,
        )

    out_dir = Path(args.out)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    by_confidence: dict[str, int] = {}
    for fix in fixtures:
        conf = re.search(r"confidence=(\w+)", fix["_review"]).group(1)
        by_confidence[conf] = by_confidence.get(conf, 0) + 1
        path = out_dir / f"{fix['id']}.yml"
        text = render_fixture_yaml(fix)
        if args.dry_run:
            print(f"--- {path} ---")
            print(text)
        else:
            path.write_text(text)
            print(f"  {conf:<6}  {path}")

    print()
    print(f"harvested {len(fixtures)} fixtures → {out_dir}")
    for c in ("high", "medium", "low"):
        if by_confidence.get(c):
            print(f"  {c}: {by_confidence[c]}")
    print()
    print("Manual curation REQUIRED before use as eval ground truth:")
    print("  1. Drop fixtures with confidence=low.")
    print("  2. Replace canonical_fix[].section 'TODO: human-curated' with real anchors.")
    print("  3. Verify failure_message reads like a real test failure (not a commit subject).")
    print("  4. Delete the `_review` field once curated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
