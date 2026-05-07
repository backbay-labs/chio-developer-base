"""Shared dataclasses used across plugin hooks.

These types are deliberately minimal. Plugins extend them by composition
(adding a `properties` dict) rather than by inheritance — keeps the
engine ↔ pack boundary stable as packs evolve their own schemas.

No Chio knowledge here. Field names are domain-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Symbol:
    """A code symbol (function, class, etc.) extracted from a parsed file.

    Plugins may attach domain-specific metadata via properties. The engine
    does not interpret properties — they round-trip to graph projection.
    """

    name: str
    kind: str  # function, class, module, ... (plugin-defined vocabulary)
    line_start: int
    line_end: int
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedFile:
    """The result of a SourceIngester reading one file.

    Attributes:
        path: The file path, relative to the source root.
        language: Source language (python, rust, javascript, markdown, ...).
        symbols: Symbols extracted from the file (may be empty for prose).
        text: The file's text content, retained for downstream embedding.
        properties: Free-form plugin-defined metadata (crate name, doc type, etc).
    """

    path: str
    language: str
    text: str
    symbols: list[Symbol] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Node:
    """A graph node emitted by a GraphProjector.

    `id` is a stable identity (file path + symbol anchor, etc). `label`
    is the plugin's namespaced label (e.g., `ChioCapability`,
    `PlatformService`).
    """

    id: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    """A graph edge emitted by a GraphProjector.

    `relationship` is the plugin's namespaced edge type (e.g.,
    `IMPLEMENTS`, `GUARDS`). The engine treats it as opaque.
    """

    src_id: str
    dst_id: str
    relationship: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class DerivedRecord:
    """A record derived from a vault-note frontmatter handler.

    The handler decides what derived stores to write to (Graphiti episode,
    pgvector embedding, neo4j node, etc.). The engine routes these to the
    appropriate backing store based on `target`.
    """

    target: str  # "graphiti" | "pgvector" | "neo4j" | <plugin-defined>
    payload: dict[str, Any]
