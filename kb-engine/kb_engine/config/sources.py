"""sources.toml — declarative ingest configuration.

A `sources.toml` file lists one or more `[[source]]` array-of-tables. Each
entry maps a registered pack to a filesystem root, optionally narrowed by
include or exclude globs:

    [[source]]
    pack = "chio"
    root = "../arc"

    [[source]]
    pack = "alexandria"
    root = "../alexandria-corpus"
    glob = ["**/*.md", "**/*.yml"]
    exclude = ["**/_archive/**"]

The CLI (`chio-dev ingest --sources sources.toml`) hands each parsed
SourceConfig to the IngestPipeline. Pack name validation is done against
the registered entry-point names — an unregistered `pack:` reference
raises ConfigError before any file walk starts.

This module is engine-level — it has no Chio knowledge and must not
import anything `chio_*` (AGENTS.md hard rule #3).
"""
from __future__ import annotations

import importlib.metadata
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised on any sources.toml parse, validation, or path error."""


@dataclass(frozen=True)
class SourceConfig:
    """One `[[source]]` entry from sources.toml.

    Attributes
    ----------
    pack:
        Name of a registered kb_engine.plugins entry point. Must
        reference a pack already discoverable via importlib.metadata
        — unknown names raise ConfigError at parse time.
    root:
        Filesystem path to the source tree. Resolved against the
        sources.toml's parent directory if relative. Must exist at
        parse time.
    glob:
        Optional list of include glob patterns (matched relative to
        `root`). Empty list means "include everything the engine's
        SourceIngester hooks claim."
    exclude:
        Optional list of exclude glob patterns. Applied AFTER glob.
    """

    pack: str
    root: Path
    glob: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


def default_sources_path(cwd: Path | None = None, repo_root: Path | None = None) -> Path | None:
    """Locate a sources.toml file by convention.

    Lookup order:
      1. `<cwd>/sources.toml`
      2. `<repo_root>/sources.toml` (if `repo_root` provided and distinct)

    Returns the first existing path, or None if neither exists. Callers
    use the None return to fall back to the legacy positional source
    argument (back-compat).
    """
    cwd = cwd or Path.cwd()
    candidates: list[Path] = [cwd / "sources.toml"]
    if repo_root is not None:
        repo_path = repo_root / "sources.toml"
        if repo_path != candidates[0]:
            candidates.append(repo_path)
    for c in candidates:
        if c.is_file():
            return c
    return None


def _registered_pack_names(group: str = "kb_engine.plugins") -> set[str]:
    """Return the set of pack names visible via importlib.metadata.

    This is the canonical "is this pack installed?" check — no special
    Registry mutation required, the entry-point group is the source of
    truth.
    """
    return {ep.name for ep in importlib.metadata.entry_points(group=group)}


def load_sources_toml(
    path: Path,
    *,
    known_packs: set[str] | None = None,
) -> list[SourceConfig]:
    """Parse and validate a sources.toml file.

    Parameters
    ----------
    path:
        Absolute or relative path to a sources.toml. Relative `root`
        values inside the file are resolved against `path.parent`.
    known_packs:
        If provided, used in place of `_registered_pack_names()`. Tests
        pass this to avoid pulling real entry points; production code
        leaves it None and the function consults importlib.metadata.

    Returns
    -------
    list[SourceConfig]
        One entry per `[[source]]` array element, in file order.

    Raises
    ------
    ConfigError
        On any parse error, missing required key, missing root path,
        or reference to an unregistered pack.
    """
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"sources.toml not found: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"failed to parse {path}: {e}") from e

    raw_sources = data.get("source")
    if raw_sources is None:
        raise ConfigError(
            f"{path}: no [[source]] entries (expected an array-of-tables)"
        )
    if not isinstance(raw_sources, list):
        raise ConfigError(
            f"{path}: `source` must be an array-of-tables (use [[source]] not [source])"
        )

    if known_packs is None:
        known_packs = _registered_pack_names()

    base_dir = path.parent.resolve()
    out: list[SourceConfig] = []
    for i, entry in enumerate(raw_sources):
        if not isinstance(entry, dict):
            raise ConfigError(
                f"{path}: [[source]] #{i} is not a table"
            )
        pack = entry.get("pack")
        if not pack:
            raise ConfigError(
                f"{path}: [[source]] #{i} missing required key `pack`"
            )
        if not isinstance(pack, str):
            raise ConfigError(
                f"{path}: [[source]] #{i} `pack` must be a string"
            )
        if known_packs and pack not in known_packs:
            raise ConfigError(
                f"{path}: [[source]] #{i} pack {pack!r} is not registered "
                f"(known packs: {sorted(known_packs) or '<none installed>'})"
            )
        root_str = entry.get("root")
        if not root_str:
            raise ConfigError(
                f"{path}: [[source]] #{i} missing required key `root`"
            )
        if not isinstance(root_str, str):
            raise ConfigError(
                f"{path}: [[source]] #{i} `root` must be a string"
            )
        root = Path(root_str)
        if not root.is_absolute():
            root = (base_dir / root).resolve()
        if not root.exists():
            raise ConfigError(
                f"{path}: [[source]] #{i} root {root} does not exist"
            )

        glob = entry.get("glob", [])
        if not isinstance(glob, list) or not all(isinstance(g, str) for g in glob):
            raise ConfigError(
                f"{path}: [[source]] #{i} `glob` must be a list of strings"
            )
        exclude = entry.get("exclude", [])
        if not isinstance(exclude, list) or not all(isinstance(g, str) for g in exclude):
            raise ConfigError(
                f"{path}: [[source]] #{i} `exclude` must be a list of strings"
            )
        out.append(
            SourceConfig(
                pack=pack,
                root=root,
                glob=tuple(glob),
                exclude=tuple(exclude),
            )
        )
    return out
