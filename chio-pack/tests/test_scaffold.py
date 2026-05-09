"""Tests for `chio-dev init-pack` and the scaffold module.

Verifies:
  - Valid names produce a complete, registrable pack tree.
  - Invalid names are rejected before any directory is created.
  - The scaffold refuses to overwrite an existing directory.
  - The generated pack's `register()` populates all four hook types
    against a fresh `kb_engine.Registry()` (the same assertion the
    scaffolded `tests/test_register.py` makes).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from chio_pack.cli import main
from chio_pack.scaffold import (
    PACK_NAME_RE,
    ScaffoldError,
    scaffold_pack,
    validate_pack_name,
)


# === Name validation ===


@pytest.mark.parametrize("name", ["alexandria", "opus", "alpha", "a", "a1", "a_b"])
def test_validate_pack_name_accepts_valid(name):
    validate_pack_name(name)  # no raise


@pytest.mark.parametrize(
    "name",
    [
        "",
        "Alexandria",  # uppercase
        "1pack",  # digit start
        "_pack",  # underscore start
        "alex-pack",  # hyphen
        "alex pack",  # space
        "alex.pack",  # dot
    ],
)
def test_validate_pack_name_rejects_invalid(name):
    with pytest.raises(ScaffoldError):
        validate_pack_name(name)


def test_pack_name_regex_matches_pattern():
    assert PACK_NAME_RE.pattern == r"^[a-z][a-z0-9_]*$"


# === Scaffold layout ===


def test_scaffold_creates_expected_files(tmp_path):
    pack_dir = scaffold_pack("alexandria", tmp_path)
    assert pack_dir == (tmp_path / "alexandria-pack").resolve()
    assert (pack_dir / "pyproject.toml").is_file()
    assert (pack_dir / "README.md").is_file()
    assert (pack_dir / "alexandria_pack" / "__init__.py").is_file()
    assert (pack_dir / "alexandria_pack" / "plugin.py").is_file()
    assert (pack_dir / "alexandria_pack" / "schema.py").is_file()
    assert (pack_dir / "tests" / "test_register.py").is_file()


def test_scaffold_pyproject_declares_entry_point(tmp_path):
    pack_dir = scaffold_pack("alexandria", tmp_path)
    pyproject = (pack_dir / "pyproject.toml").read_text()
    assert '[project.entry-points."kb_engine.plugins"]' in pyproject
    assert 'alexandria = "alexandria_pack.plugin"' in pyproject


def test_scaffold_schema_uses_uppercase_constant(tmp_path):
    pack_dir = scaffold_pack("alexandria", tmp_path)
    schema_text = (pack_dir / "alexandria_pack" / "schema.py").read_text()
    # chio-pack pattern: UPPERCASE_NAME = "Title-prefixed-string"
    assert 'ALEXANDRIA_ARTIFACT = "AlexandriaArtifact"' in schema_text
    assert "ALL_NODE_LABELS" in schema_text


def test_scaffold_plugin_has_todo_for_each_protocol(tmp_path):
    pack_dir = scaffold_pack("alexandria", tmp_path)
    plugin_text = (pack_dir / "alexandria_pack" / "plugin.py").read_text()
    # The four hook stubs each carry a TODO with the pack name.
    assert plugin_text.count("TODO(alexandria-pack)") >= 4


def test_scaffold_refuses_to_overwrite(tmp_path):
    scaffold_pack("alexandria", tmp_path)
    with pytest.raises(ScaffoldError, match="refusing to overwrite"):
        scaffold_pack("alexandria", tmp_path)


def test_scaffold_rejects_invalid_name_before_creating(tmp_path):
    with pytest.raises(ScaffoldError):
        scaffold_pack("BadName", tmp_path)
    # Nothing should have been created.
    assert list(tmp_path.iterdir()) == []


# === Generated pack is registrable ===


def test_generated_plugin_register_populates_hooks(tmp_path, monkeypatch):
    """The scaffolded `register()` call populates all four hook types
    on a fresh Registry — same assertion the bundled test_register.py
    makes, exercised here in-process so we don't have to spawn pip.
    """
    pack_dir = scaffold_pack("alexandria", tmp_path)
    # Make the generated package importable.
    monkeypatch.syspath_prepend(str(pack_dir))
    # Ensure no stale cached import.
    for mod in list(sys.modules):
        if mod.startswith("alexandria_pack"):
            del sys.modules[mod]
    from kb_engine import Registry

    import alexandria_pack.plugin as alex_plugin  # noqa: PLC0415

    r = Registry()
    alex_plugin.register(r)
    assert len(r.source_ingesters) == 1
    assert len(r.graph_projectors) == 1
    assert len(r.tool_registrars) == 1
    assert isinstance(r.frontmatter_handlers, dict)


# === CLI integration ===


def test_cli_init_pack_creates_directory(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init-pack", "opus", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "opus-pack" / "pyproject.toml").is_file()


def test_cli_init_pack_default_path_is_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init-pack", "alpha"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "alpha-pack" / "pyproject.toml").is_file()


def test_cli_init_pack_rejects_invalid_name(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init-pack", "BadName", "--path", str(tmp_path)])
    assert result.exit_code == 2
    assert "invalid pack name" in (result.output + (result.stderr or ""))
    assert list(tmp_path.iterdir()) == []


def test_cli_init_pack_refuses_overwrite(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init-pack", "opus", "--path", str(tmp_path)])
    assert result.exit_code == 0
    result2 = runner.invoke(main, ["init-pack", "opus", "--path", str(tmp_path)])
    assert result2.exit_code == 2
    assert "refusing to overwrite" in (result2.output + (result2.stderr or ""))
