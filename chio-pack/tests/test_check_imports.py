"""Unit tests for ops/ci/check-imports.py.

The script lives at `ops/ci/check-imports.py` (hyphenated, not directly
importable by name); we load it via importlib so we can exercise the
detection helpers in isolation. The repo-wide regression test at the
end runs the script's `main()` against the live tree to guarantee the
script itself stays green on every commit (M0-B.3).

Coverage matrix:

    detection            kind            test
    -------------------  --------------  ----------------------------
    static engine import "static"        ``test_static_*``
    aliased import       "static"        ``test_aliased_*``
    importlib.import_module("chio_*")
                         "dynamic"       ``test_dynamic_importlib``
    __import__("chio_*") "dynamic"       ``test_dynamic_dunder``
    if TYPE_CHECKING:    "type_checking" ``test_type_checking_*``
    pack-to-pack         "pack_to_pack"  ``test_pack_to_pack_*``
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "ops" / "ci" / "check-imports.py"


def _load_module():
    """Load `check-imports.py` as a module (handle the hyphen)."""
    spec = importlib.util.spec_from_file_location(
        "_check_imports", SCRIPT_PATH
    )
    assert spec and spec.loader, f"could not spec-load {SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_check_imports"] = mod
    spec.loader.exec_module(mod)
    return mod


CHECK = _load_module()


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Build a synthetic repo skeleton mirroring the real one."""
    (tmp_path / "kb-engine" / "kb_engine").mkdir(parents=True)
    (tmp_path / "chio-pack" / "chio_pack").mkdir(parents=True)
    (tmp_path / "alexandria-pack" / "alexandria_pack").mkdir(parents=True)
    return tmp_path


def _scan_engine_file(path: Path) -> list:
    return CHECK._scan_file(path, forbid_packs=True)


def _scan_pack_file(path: Path, current_pack: str) -> list:
    return CHECK._scan_file(
        path, forbid_packs=False, current_pack=current_pack
    )


# ============== Engine-side rule (existing behavior, AST-ified) ==============


def test_static_static_import_is_caught(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text("import chio_pack\n")
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "static"
    assert "chio_pack" in vs[0].detail


def test_static_from_import_is_caught(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text("from chio_pack.schema import FILE\n")
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "static"


def test_aliased_import_is_caught(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text("import chio_pack as cp\n")
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "static"
    assert "chio_pack" in vs[0].detail


def test_clean_engine_file_passes(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "ok.py"
    f.write_text(
        "from __future__ import annotations\n"
        "import os\n"
        "from typing import Any\n"
    )
    assert _scan_engine_file(f) == []


def test_docstring_mention_is_not_a_violation(tmp_repo: Path) -> None:
    """A line that *says* 'import chio_pack' inside a docstring or
    comment must not trigger; only real ast.Import/ast.ImportFrom
    nodes count. This is a regression guard against the regex era.
    """
    f = tmp_repo / "kb-engine" / "kb_engine" / "ok.py"
    f.write_text(
        '"""docstring.\n\n    import chio_pack  # this is text, not code\n"""\n'
        "# import chio_pack\n"
        "import os\n"
    )
    assert _scan_engine_file(f) == []


# ============== Dynamic imports ==============


def test_dynamic_importlib(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text(
        "import importlib\n"
        'm = importlib.import_module("chio_pack.tools")\n'
    )
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "dynamic"
    assert "chio_pack.tools" in vs[0].detail


def test_dynamic_importlib_unqualified(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text(
        "from importlib import import_module\n"
        'm = import_module("chio_pack")\n'
    )
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "dynamic"


def test_dynamic_dunder_import(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "bad.py"
    f.write_text('m = __import__("chio_pack")\n')
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "dynamic"


def test_dynamic_with_non_chio_target_is_clean(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "ok.py"
    f.write_text(
        "import importlib\n"
        'm = importlib.import_module("kb_engine.store.postgres")\n'
    )
    assert _scan_engine_file(f) == []


def test_dynamic_with_non_constant_arg_is_skipped(tmp_repo: Path) -> None:
    """A computed module name (e.g. `import_module(name)`) cannot be
    statically resolved; we conservatively skip rather than raise.
    The boundary lives by the static cases; runtime-computed module
    names are out of scope and warrant a code review anyway.
    """
    f = tmp_repo / "kb-engine" / "kb_engine" / "edge.py"
    f.write_text(
        "import importlib\n"
        "name = 'chio_pack'\n"
        "m = importlib.import_module(name)\n"
    )
    assert _scan_engine_file(f) == []


# ============== TYPE_CHECKING handling ==============


def test_type_checking_import_emits_warning_not_error(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "tc.py"
    f.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from chio_pack import schema\n"
    )
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "type_checking"


def test_type_checking_dotted_form(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "tc.py"
    f.write_text(
        "import typing\n"
        "if typing.TYPE_CHECKING:\n"
        "    import chio_pack\n"
    )
    vs = _scan_engine_file(f)
    assert len(vs) == 1
    assert vs[0].kind == "type_checking"


def test_runtime_import_after_type_checking_block_still_errors(
    tmp_repo: Path,
) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "mixed.py"
    f.write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from chio_pack import schema  # ok-warning\n"
        "import chio_pack as cp  # actual runtime use, must fail\n"
    )
    vs = _scan_engine_file(f)
    kinds = sorted(v.kind for v in vs)
    assert kinds == ["static", "type_checking"]


# ============== Pack-to-pack rule ==============


def test_pack_to_pack_static(tmp_repo: Path) -> None:
    """A second pack importing chio_pack's namespace is forbidden."""
    f = tmp_repo / "alexandria-pack" / "alexandria_pack" / "x.py"
    f.write_text("from chio_pack.schema import FILE\n")
    vs = _scan_pack_file(f, current_pack="alexandria_pack")
    assert len(vs) == 1
    assert vs[0].kind == "pack_to_pack"


def test_pack_to_pack_dynamic(tmp_repo: Path) -> None:
    """Dynamic cross-pack import is also forbidden — closing the
    same regex hole that B.1 fixed for the engine side.
    """
    f = tmp_repo / "alexandria-pack" / "alexandria_pack" / "x.py"
    f.write_text(
        "import importlib\n"
        'importlib.import_module("chio_pack.tools")\n'
    )
    vs = _scan_pack_file(f, current_pack="alexandria_pack")
    assert len(vs) == 1
    assert vs[0].kind == "dynamic"


def test_pack_to_pack_aliased(tmp_repo: Path) -> None:
    f = tmp_repo / "alexandria-pack" / "alexandria_pack" / "x.py"
    f.write_text("import chio_pack as cp\n")
    vs = _scan_pack_file(f, current_pack="alexandria_pack")
    assert len(vs) == 1
    assert vs[0].kind == "pack_to_pack"


def test_pack_self_import_is_clean(tmp_repo: Path) -> None:
    """`chio_pack` importing its own `chio_pack.schema` is fine —
    same pack, no boundary crossed.
    """
    f = tmp_repo / "chio-pack" / "chio_pack" / "x.py"
    f.write_text("from chio_pack import schema\n")
    assert _scan_pack_file(f, current_pack="chio_pack") == []


def test_pack_importing_engine_is_clean(tmp_repo: Path) -> None:
    """A pack importing kb_engine is the *intended* direction —
    the only direction the engine ↔ pack contract permits.
    """
    f = tmp_repo / "chio-pack" / "chio_pack" / "x.py"
    f.write_text("from kb_engine import Registry\n")
    assert _scan_pack_file(f, current_pack="chio_pack") == []


def test_detect_pack_resolves_owning_pack(tmp_repo: Path) -> None:
    """A file under `<X>_pack/` is owned by `X_pack`."""
    deep = tmp_repo / "chio-pack" / "chio_pack" / "eval" / "runners" / "x.py"
    deep.parent.mkdir(parents=True, exist_ok=True)
    deep.write_text("")
    assert CHECK._detect_pack(deep, tmp_repo) == "chio_pack"


def test_detect_pack_returns_none_outside_packs(tmp_repo: Path) -> None:
    f = tmp_repo / "kb-engine" / "kb_engine" / "x.py"
    f.write_text("")
    assert CHECK._detect_pack(f, tmp_repo) is None


# ============== Repo-wide regression ==============


def test_repo_clean() -> None:
    """The live tree must pass `check-imports.py main()` for both
    the engine-side and pack-to-pack rules. The pytest-collected
    mirror of the boundary job: any push that introduces a violation
    will fail the unit-test job before it has a chance to land on
    main.
    """
    rc = CHECK.main()
    assert rc == 0, (
        "boundary check failed on the live tree — see the printed"
        " violations above. Run `make check-boundary` locally to"
        " reproduce."
    )
