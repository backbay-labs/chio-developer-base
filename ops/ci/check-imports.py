#!/usr/bin/env python3
"""Engine ↔ pack and pack ↔ pack boundary import-rule check.

Per PLAN.md and AGENTS.md hard rule #3:

  - `kb-engine/` MUST NOT import anything `chio_*` (or any `*_pack`).
  - One pack MUST NOT import another pack's namespace.
    Convention: a "pack" is a top-level Python package whose name
    ends in `_pack` (matching the existing `chio_pack` carve-out).
    A file is owned by `<X>_pack` if its repo-relative path traverses
    a directory named `<X>_pack`. The engine is meant to host more
    packs (e.g. `alexandria_pack`, M4 milestone) and the symmetric
    rule must hold *before* there is a second pack to test it
    against — bidirectional containment is what makes the boundary
    load-bearing rather than directional.

Detection strategy: Python AST walk (not text/regex).

The previous implementation used a regex against raw source lines.
That caught straightforward `import chio_pack` and
`from chio_pack import X`, but missed:

  - `importlib.import_module("chio_pack.tools")`
  - `__import__("chio_pack")`
  - aliased forms (`import chio_pack as cp`) split across continuations
  - imports inside string-formatted blocks that the regex would
    incidentally swallow

AST parsing closes those holes by visiting `ast.Import`,
`ast.ImportFrom`, and `ast.Call` nodes directly. See the unit tests
in `chio-pack/tests/test_check_imports.py` for the matrix.

`if TYPE_CHECKING:` handling
----------------------------

`from __future__ import annotations` is the codebase's preferred way
to keep runtime-free type imports out of cycles, but a future
contributor may legitimately reach for `if TYPE_CHECKING:` blocks
with a `chio_*` import for a typed callback signature in kb-engine.
That use is type-only — the import is never executed — so it does
not violate the boundary at runtime. We flag it as a **warning**
(exit code stays clean) so the violation is visible in review
without blocking the merge. To intentionally allow such an import,
add a single-line lint comment on the import:

    if TYPE_CHECKING:
        from chio_pack import schema  # TYPE_CHECKING ok per ADR-XXXX

The comment is informational today; an ADR (when filed) will say
which ADR governs the carve-out and the script will then promote
unannotated TYPE_CHECKING imports back to a hard error.

Exit codes:
    0 — clean (warnings allowed)
    1 — boundary violation found
    2 — script error (missing path, etc.)

Invoked by .github/workflows/eval.yml, the `make check-boundary`
target (M0-B.3), and the pytest-collected
`chio-pack/tests/test_check_imports.py::test_repo_clean` regression.
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

PACK_SUFFIX = "_pack"


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    detail: str
    kind: str  # "static", "dynamic", "type_checking", "pack_to_pack"


def _is_chio_or_pack(name: str) -> bool:
    """True if `name` is `chio_*` or any `*_pack` top-level package."""
    if not name:
        return False
    head = name.split(".", 1)[0]
    return head.startswith("chio_") or head.endswith(PACK_SUFFIX)


def _is_other_pack(name: str, current_pack: str | None) -> bool:
    """True if `name` is a pack other than `current_pack`."""
    if not name or current_pack is None:
        return False
    head = name.split(".", 1)[0]
    return head.endswith(PACK_SUFFIX) and head != current_pack


def _detect_pack(file_path: Path, repo_root: Path) -> str | None:
    """Return the pack name (`*_pack`) that owns this file, or None.

    A file is owned by pack `X_pack` if the path traversal from
    `repo_root` to `file_path` includes a directory named `X_pack`.
    """
    try:
        rel = file_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    for part in rel.parts:
        if part.endswith(PACK_SUFFIX):
            return part
    return None


def _type_checking_line_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """Return (start, end) line ranges of `if TYPE_CHECKING:` blocks.

    Matches both bare `TYPE_CHECKING` and dotted `typing.TYPE_CHECKING`.
    """
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_tc = (
            isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"
        ) or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if not is_tc:
            continue
        last_line = max(
            (getattr(child, "end_lineno", child.lineno) or child.lineno)
            for child in ast.walk(node)
            if hasattr(child, "lineno")
        )
        ranges.append((node.lineno, last_line))
    return ranges


def _line_in_ranges(line: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= line <= end for start, end in ranges)


def _is_dynamic_import_call(call: ast.Call) -> bool:
    """`importlib.import_module(...)` or `__import__(...)`."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        return True
    if isinstance(func, ast.Name) and func.id in {
        "import_module",
        "__import__",
    }:
        return True
    return False


def _const_str_arg(call: ast.Call) -> str | None:
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _scan_file(
    py: Path,
    *,
    forbid_packs: bool,
    current_pack: str | None = None,
) -> list[Violation]:
    """Scan one file, returning all boundary violations in it.

    `forbid_packs=True` is the engine-side rule: any chio_*/`*_pack`
    import (static, aliased, or dynamic) is forbidden.

    `current_pack` triggers the pack-to-pack rule: any import of a
    *different* `*_pack` from inside this file is forbidden. Set
    `forbid_packs=False, current_pack="chio_pack"` to scan files
    owned by `chio_pack` for cross-pack imports.

    Both rules can be combined (`forbid_packs=True, current_pack=...`)
    but in practice the engine isn't owned by any pack, so callers
    pick one.
    """
    try:
        text = py.read_text(encoding="utf-8")
    except OSError as e:
        print(f"warning: skipped {py}: {e}", file=sys.stderr)
        return []
    try:
        tree = ast.parse(text, filename=str(py))
    except SyntaxError as e:
        print(f"warning: syntax error in {py}: {e}", file=sys.stderr)
        return []

    tc_ranges = _type_checking_line_ranges(tree)
    out: list[Violation] = []

    def _classify(name: str) -> str | None:
        if forbid_packs and _is_chio_or_pack(name):
            return "static"
        if current_pack and _is_other_pack(name, current_pack):
            return "pack_to_pack"
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                kind = _classify(alias.name)
                if not kind:
                    continue
                if _line_in_ranges(node.lineno, tc_ranges):
                    out.append(Violation(
                        path=py, line=node.lineno,
                        detail=f"if TYPE_CHECKING: import {alias.name}",
                        kind="type_checking",
                    ))
                else:
                    out.append(Violation(
                        path=py, line=node.lineno,
                        detail=f"import {alias.name}",
                        kind=kind,
                    ))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            kind = _classify(mod)
            if not kind:
                continue
            names = ", ".join(a.name for a in node.names)
            if _line_in_ranges(node.lineno, tc_ranges):
                out.append(Violation(
                    path=py, line=node.lineno,
                    detail=f"if TYPE_CHECKING: from {mod} import {names}",
                    kind="type_checking",
                ))
            else:
                out.append(Violation(
                    path=py, line=node.lineno,
                    detail=f"from {mod} import {names}",
                    kind=kind,
                ))
        elif isinstance(node, ast.Call) and _is_dynamic_import_call(node):
            target = _const_str_arg(node)
            if target is None:
                continue
            kind = _classify(target)
            if not kind:
                continue
            out.append(Violation(
                path=py, line=node.lineno,
                detail=f"dynamic import of {target!r}",
                kind="dynamic",
            ))
    return out


_SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git"}


def _walk_py(root: Path) -> list[Path]:
    return [
        p for p in sorted(root.rglob("*.py"))
        if not any(part in _SKIP_DIRS for part in p.parts)
    ]


def find_engine_violations(engine_root: Path) -> list[Violation]:
    """Engine-side rule: kb-engine imports nothing chio_*/`*_pack`."""
    if not engine_root.is_dir():
        print(f"error: {engine_root} not a directory", file=sys.stderr)
        sys.exit(2)
    violations: list[Violation] = []
    for py in _walk_py(engine_root):
        violations.extend(_scan_file(py, forbid_packs=True))
    return violations


def find_pack_violations(repo_root: Path) -> list[Violation]:
    """Pack-to-pack rule: a `*_pack` package imports no other `*_pack`.

    Walks the whole repo; any file whose path traverses a `*_pack`
    directory inherits that pack's identity and is then scanned for
    imports of *different* `*_pack` namespaces. Files outside any
    pack directory are skipped (not under this rule's jurisdiction).
    """
    violations: list[Violation] = []
    for py in _walk_py(repo_root):
        current = _detect_pack(py, repo_root)
        if current is None:
            continue
        violations.extend(
            _scan_file(py, forbid_packs=False, current_pack=current)
        )
    return violations


def _fmt(v: Violation, repo_root: Path) -> str:
    rel = v.path.relative_to(repo_root) if v.path.is_absolute() else v.path
    return f"  {rel}:{v.line}: [{v.kind}] {v.detail}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    engine_root = repo_root / "kb-engine" / "kb_engine"

    all_v = find_engine_violations(engine_root) + find_pack_violations(repo_root)
    errors = [v for v in all_v if v.kind != "type_checking"]
    warnings = [v for v in all_v if v.kind == "type_checking"]

    if warnings:
        print(f"warnings ({len(warnings)}) — TYPE_CHECKING-only imports:")
        for v in warnings:
            print(_fmt(v, repo_root))
        print(
            "  (allowed for type-only purposes; annotate with"
            " '# TYPE_CHECKING ok per ADR-XXXX' when an ADR governs"
            " the carve-out)"
        )
        print()

    if errors:
        print(
            f"engine ↔ pack / pack ↔ pack boundary violations ({len(errors)}):"
        )
        for v in errors:
            print(_fmt(v, repo_root))
        print()
        print(
            "kb-engine/ must not import chio_*/*_pack at runtime. Move"
            " the pack-specific code into the appropriate */*_pack/ and"
            " register a plugin via kb_engine.Registry. Packs must not"
            " import each other's namespaces — extract shared logic into"
            " kb_engine, or coordinate via a Registry hook."
        )
        return 1

    n_engine = len(_walk_py(engine_root))
    n_pack_files = sum(
        1 for p in _walk_py(repo_root)
        if _detect_pack(p, repo_root) is not None
    )
    print(
        f"ok — boundary check clean: {n_engine} engine files,"
        f" {n_pack_files} pack files, {len(warnings)} TYPE_CHECKING warnings."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
