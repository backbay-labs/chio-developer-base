#!/usr/bin/env python3
"""Engine ↔ pack boundary import-rule check.

Per PLAN.md and AGENTS.md hard rule #3: `kb-engine/` MUST NOT import
anything `chio_*`. The boundary is enforced here at CI time.

Walks all `*.py` files under `kb-engine/kb_engine/` and fails if any line
contains an import of a `chio_*` module.

Exit codes:
    0 — clean
    1 — boundary violation found
    2 — script error (missing kb-engine, etc.)

Invoked by .github/workflows/eval.yml (Phase 0 stub) and Phase 1.x CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VIOLATION_RE = re.compile(
    r"^\s*(?:import\s+chio_\w+"
    r"|from\s+chio_\w+(?:\.\w+)*\s+import)"
)


def find_violations(engine_root: Path) -> list[tuple[Path, int, str]]:
    if not engine_root.is_dir():
        print(f"error: {engine_root} not a directory", file=sys.stderr)
        sys.exit(2)
    violations: list[tuple[Path, int, str]] = []
    for py in engine_root.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except OSError as e:
            print(f"warning: skipped {py}: {e}", file=sys.stderr)
            continue
        for n, line in enumerate(text.splitlines(), start=1):
            if VIOLATION_RE.match(line):
                violations.append((py, n, line.rstrip()))
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    engine_root = repo_root / "kb-engine" / "kb_engine"
    violations = find_violations(engine_root)
    if violations:
        print(f"engine ↔ pack boundary violations in {engine_root}:")
        for path, line_no, content in violations:
            print(f"  {path.relative_to(repo_root)}:{line_no}: {content}")
        print()
        print(
            "kb-engine/ must not import chio_*. Move the Chio-specific code"
            " into chio-pack/ and register a plugin via kb_engine.Registry."
        )
        return 1
    print(f"ok — no engine ↔ pack boundary violations in {engine_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
