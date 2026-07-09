"""Tests for kb_engine.config.sources — sources.toml parsing.

Coverage:
  - Parse a minimal valid file.
  - Reject missing `pack`.
  - Reject reference to an unregistered pack.
  - Reject missing root path.
  - Optional `glob` / `exclude` lists round-trip correctly.
  - default_sources_path lookup order: cwd → repo root → None.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kb_engine.config import (
    ConfigError,
    SourceConfig,
    default_sources_path,
    load_sources_toml,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_minimal_valid_file(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "alexandria"
        root = "{src_root}"
        ''',
    )
    sources = load_sources_toml(cfg_path, known_packs={"alexandria"})
    assert len(sources) == 1
    assert sources[0].pack == "alexandria"
    assert sources[0].root == src_root.resolve()
    assert sources[0].glob == ()
    assert sources[0].exclude == ()


def test_relative_root_resolves_against_toml_parent(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        '''
        [[source]]
        pack = "alexandria"
        root = "corpus"
        ''',
    )
    sources = load_sources_toml(cfg_path, known_packs={"alexandria"})
    assert sources[0].root == src_root.resolve()


def test_optional_globs_and_excludes(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "alexandria"
        root = "{src_root}"
        glob = ["**/*.md", "**/*.yml"]
        exclude = ["**/_archive/**"]
        ''',
    )
    sources = load_sources_toml(cfg_path, known_packs={"alexandria"})
    assert sources[0].glob == ("**/*.md", "**/*.yml")
    assert sources[0].exclude == ("**/_archive/**",)


def test_include_alias_maps_to_glob(tmp_path):
    """`include = [...]` is accepted as an alias for `glob = [...]`."""
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "alexandria"
        root = "{src_root}"
        include = ["**/*.md"]
        ''',
    )
    sources = load_sources_toml(cfg_path, known_packs={"alexandria"})
    assert sources[0].glob == ("**/*.md",)


def test_multiple_source_entries_preserve_order(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "chio"
        root = "{a}"

        [[source]]
        pack = "alexandria"
        root = "{b}"
        ''',
    )
    sources = load_sources_toml(cfg_path, known_packs={"chio", "alexandria"})
    assert [s.pack for s in sources] == ["chio", "alexandria"]
    assert sources[0].root == a.resolve()
    assert sources[1].root == b.resolve()


def test_rejects_missing_pack_key(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        root = "{src_root}"
        ''',
    )
    with pytest.raises(ConfigError, match="missing required key `pack`"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_unregistered_pack(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "nonexistent"
        root = "{src_root}"
        ''',
    )
    with pytest.raises(ConfigError, match="not registered"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_missing_root_key(tmp_path):
    cfg_path = _write(
        tmp_path / "sources.toml",
        '''
        [[source]]
        pack = "alexandria"
        ''',
    )
    with pytest.raises(ConfigError, match="missing required key `root`"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_nonexistent_root(tmp_path):
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "alexandria"
        root = "{tmp_path / 'does-not-exist'}"
        ''',
    )
    with pytest.raises(ConfigError, match="does not exist"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_no_source_entries(tmp_path):
    cfg_path = _write(
        tmp_path / "sources.toml",
        '''
        [meta]
        note = "no source entries"
        ''',
    )
    with pytest.raises(ConfigError, match="no \\[\\[source\\]\\] entries"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_table_instead_of_array_of_tables(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [source]
        pack = "alexandria"
        root = "{src_root}"
        ''',
    )
    with pytest.raises(ConfigError, match="must be an array-of-tables"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_invalid_toml(tmp_path):
    cfg_path = _write(tmp_path / "sources.toml", "not = = = valid\n")
    with pytest.raises(ConfigError, match="failed to parse"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_rejects_glob_not_a_list(tmp_path):
    src_root = tmp_path / "corpus"
    src_root.mkdir()
    cfg_path = _write(
        tmp_path / "sources.toml",
        f'''
        [[source]]
        pack = "alexandria"
        root = "{src_root}"
        glob = "*.md"
        ''',
    )
    with pytest.raises(ConfigError, match="`glob` must be a list of strings"):
        load_sources_toml(cfg_path, known_packs={"alexandria"})


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_sources_toml(tmp_path / "missing.toml")


# === default_sources_path ===


def test_default_sources_path_finds_cwd_first(tmp_path):
    cwd = tmp_path / "cwd"
    repo = tmp_path / "repo"
    cwd.mkdir()
    repo.mkdir()
    (cwd / "sources.toml").write_text("# cwd version", encoding="utf-8")
    (repo / "sources.toml").write_text("# repo version", encoding="utf-8")
    found = default_sources_path(cwd=cwd, repo_root=repo)
    assert found == cwd / "sources.toml"


def test_default_sources_path_falls_back_to_repo_root(tmp_path):
    cwd = tmp_path / "cwd"
    repo = tmp_path / "repo"
    cwd.mkdir()
    repo.mkdir()
    (repo / "sources.toml").write_text("# repo version", encoding="utf-8")
    found = default_sources_path(cwd=cwd, repo_root=repo)
    assert found == repo / "sources.toml"


def test_default_sources_path_returns_none_when_neither_exists(tmp_path):
    cwd = tmp_path / "cwd"
    repo = tmp_path / "repo"
    cwd.mkdir()
    repo.mkdir()
    found = default_sources_path(cwd=cwd, repo_root=repo)
    assert found is None
