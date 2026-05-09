"""Engine-level configuration parsers.

Today this exposes the `sources.toml` parser used by `chio-dev ingest
--sources sources.toml`. The format is a TOML file with `[[source]]`
array-of-tables; each entry names a registered pack and a filesystem
root, optionally with include/exclude globs.

Per AGENTS.md hard rule #3, this module must remain pack-agnostic —
no `chio_*` imports.
"""
from __future__ import annotations

from .sources import (
    ConfigError,
    SourceConfig,
    default_sources_path,
    load_sources_toml,
)

__all__ = [
    "ConfigError",
    "SourceConfig",
    "default_sources_path",
    "load_sources_toml",
]
