#!/usr/bin/env python3
"""Fail CI if affirmative orphaned ``crates/chio-receipts`` refs remain.

Per ADR-0002a (Wave 0 truth repair): receipt types live in
``crates/core/chio-core-types`` and the eval-bundle verifier is
``crates/sdk/chio-eval-receipt``. The historical path
``crates/chio-receipts`` does not exist in arc.

This check greps tracked text files for *affirmative* uses of the
orphaned path (imports, cargo package names, canonical_fix pointers)
and exits non-zero if any remain. Explanatory mentions that document
the rename ("there is no crates/chio-receipts", "orphaned …") are
allowed.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Affirmative orphan patterns — these mean the old path is still treated
# as real. Explanatory mentions are filtered separately.
AFFIRMATIVE = (
    # Rust module path
    re.compile(r"\bchio_receipts::"),
    # Cargo package / CLI invocations that treat it as a real crate
    re.compile(r"cargo\s+run\s+-p\s+chio-receipts\b"),
    re.compile(r"\b-p\s+chio-receipts\b"),
    # Frontmatter / YAML crate: field
    re.compile(r"(?m)^\s*crate:\s*chio-receipts\s*$"),
    # Path used as a real file pointer (canonical_fix, Implements, etc.)
    re.compile(r"(?:file|path):\s*[\"']?crates/chio-receipts/"),
    re.compile(r"`crates/chio-receipts/[^`]*`"),
    re.compile(r"(?<![/\w])crates/chio-receipts/(?:src|tests)/"),
    # Standalone package name in Implements / Tested-by style lists
    re.compile(r"`chio_receipts::"),
)

# Lines that document the rename / forbid the path are not violations.
EXPLANATORY = re.compile(
    r"(?i)("
    r"no\s+`?crates/chio-receipts"
    r"|orphaned\s+.*chio-receipts"
    r"|there\s+is\s+no\s+.*chio-receipts"
    r"|does\s+not\s+exist"
    r"|was\s+a\s+docs?\s+drift"
    r"|historical\s+path"
    r"|fail\s+(?:closed\s+)?on\s+crates/chio-receipts"
    r"|check-orphaned-crate-paths"
    r"|chio-receipts\s+path\s+references"
    r"|replace\s+with\s+crates/core/chio-core-types"
    r"|corrected\s+in\s+ADR-0002a"
    r"|ADR-0002a"
    r")"
)

ALLOWLIST_SUFFIXES = (
    "decisions/ADR-0002a-phase-0-slip.md",
    "ops/ci/check-orphaned-crate-paths.py",
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "target",
    ".cursor",
}

TEXT_SUFFIXES = {
    ".md",
    ".yml",
    ".yaml",
    ".py",
    ".toml",
    ".txt",
    ".rs",
    ".json",
    ".sh",
}


def _is_allowlisted(rel: str) -> bool:
    return any(rel.endswith(suffix) or rel == suffix for suffix in ALLOWLIST_SUFFIXES)


def _git_ls_files() -> list[Path]:
    """Prefer git ls-files for speed; fall back to a shallow walk."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        paths = []
        for raw in out.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode("utf-8", errors="replace")
            path = ROOT / rel
            if path.name == "Makefile" or path.suffix in TEXT_SUFFIXES:
                paths.append(path)
        return paths
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        files: list[Path] = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.name == "Makefile" or path.suffix in TEXT_SUFFIXES:
                files.append(path)
        return files


def main() -> int:
    hits: list[str] = []
    for path in _git_ls_files():
        rel = path.relative_to(ROOT).as_posix()
        if _is_allowlisted(rel):
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if not any(pat.search(line) for pat in AFFIRMATIVE):
                continue
            if EXPLANATORY.search(line):
                continue
            hits.append(f"{rel}:{i}: {line.strip()}")

    if hits:
        print("Orphaned chio-receipts path references found:", file=sys.stderr)
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        print(
            "\nReplace with crates/core/chio-core-types or "
            "crates/sdk/chio-eval-receipt (see ADR-0002a).",
            file=sys.stderr,
        )
        return 1

    print("check-orphaned-crate-paths: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
