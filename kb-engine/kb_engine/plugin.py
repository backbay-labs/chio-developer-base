"""The four plugin hooks plus the registry that loads and dispatches them.

Per PLAN.md "Plugin/extension architecture":

    A plugin is a Python package implementing any subset of the four
    hooks. No fork, no monkey-patch.

The four hooks
--------------

- `SourceIngester(file_path) -> Optional[ParsedFile]`
    Decide if/how to index a file. Chio-pack's Rust tree-sitter
    extractor is one example.

- `GraphProjector(parsed: ParsedFile) -> Iterable[Node | Edge]`
    Take parsed AST/symbols and emit nodes + edges using a schema
    pack's vocabulary.

- `ToolRegistrar(server: object) -> None`
    Declare MCP tools on the gateway. `server` is the Phase 1.3+
    MCP-server-framework handle; here typed as `object` to keep the
    plugin protocol stable across server-framework iterations.

- `FrontmatterHandler(type: str, frontmatter: dict) -> Iterable[DerivedRecord]`
    Interpret a vault note's `type:` value to decide what derived
    store(s) to write to.

Each hook is a Protocol, not an abstract base class. Plugins can be
plain functions OR classes — whatever fits. The registry dispatches by
type rather than by inheritance.
"""
from __future__ import annotations

import importlib
import importlib.metadata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .types import ConstraintSpec, DerivedRecord, Edge, Node, ParsedFile


# === Hook protocols ===


@runtime_checkable
class SourceIngester(Protocol):
    """Decide if/how to index a single file.

    Plugins return None to skip a file (most files are skipped — a
    Rust ingester returns None for .py files, etc).
    """

    def __call__(self, file_path: str) -> ParsedFile | None: ...


@runtime_checkable
class GraphProjector(Protocol):
    """Emit graph nodes and edges from a parsed file."""

    def __call__(self, parsed: ParsedFile) -> Iterable[Node | Edge]: ...


@runtime_checkable
class ToolRegistrar(Protocol):
    """Declare MCP tools on the gateway server.

    `server` is the Phase 1.3+ MCP-server-framework handle. The protocol
    keeps it as `object` so plugin signatures stay stable across server
    iterations. Plugins call methods on `server` per its documented API.
    """

    def __call__(self, server: object) -> None: ...


@runtime_checkable
class FrontmatterHandler(Protocol):
    """Interpret a vault note's `type:` value, emit derived records.

    The handler decides what derived stores to write (Graphiti, pgvector,
    Neo4j, ...) based on the frontmatter's `type` and content. Multiple
    handlers can fire for the same note; results are unioned.
    """

    def __call__(
        self, type: str, frontmatter: dict[str, Any]
    ) -> Iterable[DerivedRecord]: ...


@runtime_checkable
class ConstraintProvider(Protocol):
    """Declare Neo4j schema constraints a pack needs at bootstrap.

    M1-Multitenant deliverable 2: packs ship a `bootstrap_constraints`
    callable returning ConstraintSpec objects describing labels they
    own (chio-pack: ChioCapability, ChioFile, …). The engine collects
    every pack's specs and applies them once at ingest startup, so
    adopters get pack-specific constraints automatically and the
    engine stays ignorant of which labels exist.
    """

    def __call__(self) -> Iterable[ConstraintSpec]: ...


# === Registry ===


@dataclass
class Registry:
    """Loads and dispatches plugin hooks.

    Two registration modes:

    1. **Entry-point loading** (production): plugins declare themselves
       in their pyproject.toml under
       [project.entry-points."kb_engine.plugins"]. Call `load_entry_points()`
       to discover them.

    2. **Direct registration** (tests, single-file plugins): call
       `register_*()` methods to add hooks programmatically.

    Both modes coexist; entry-point hooks merge with direct ones.

    Builtin source ingesters
    ------------------------

    On construction, the Registry seeds the kb-engine builtin source
    ingesters (`.py`, `.ts`/`.tsx`/`.js`/`.jsx`/`.mts`/`.cts`, `.md`/
    `.markdown`/`.mdx`) into a separate `_builtin_source_ingesters`
    list. Pack-registered ingesters live in `source_ingesters` and are
    checked FIRST. The precedence rule is therefore explicit:

        pack ingesters > builtin ingesters

    A pack registering a Python tree-sitter ingester via
    `registry.register_source_ingester(...)` shadows the builtin
    Python chunker — the pack's hook returns first when the engine
    calls `ingest_file()`. Builtins remain available as a fallback
    for extensions the pack does not handle.

    To suppress the builtins entirely (e.g., a test that wants only its
    own ingesters), pass `seed_builtins=False` to `__init__` or call
    `clear_builtin_ingesters()`.
    """

    source_ingesters: list[SourceIngester] = field(default_factory=list)
    graph_projectors: list[GraphProjector] = field(default_factory=list)
    tool_registrars: list[ToolRegistrar] = field(default_factory=list)
    frontmatter_handlers: dict[str, list[FrontmatterHandler]] = field(default_factory=dict)
    constraint_providers: list[ConstraintProvider] = field(default_factory=list)
    # Internal: builtin ingesters seeded on construction. Checked AFTER
    # pack/user-registered hooks so pack > builtin precedence is explicit.
    _builtin_source_ingesters: list[SourceIngester] = field(default_factory=list)
    # Construction-time toggle for seeding builtins. False is for tests
    # that want a strictly empty registry.
    seed_builtins: bool = True

    def __post_init__(self) -> None:
        if self.seed_builtins and not self._builtin_source_ingesters:
            self.register_builtin_ingesters()

    # === Direct registration ===

    def register_source_ingester(self, hook: SourceIngester) -> None:
        if not isinstance(hook, SourceIngester) and not callable(hook):
            raise TypeError(f"hook {hook!r} is not callable / not a SourceIngester")
        self.source_ingesters.append(hook)

    def register_builtin_ingesters(self) -> None:
        """Seed the kb-engine built-in source ingesters.

        Registers `.py`, `.ts`/`.tsx`/`.js`/`.jsx`/`.mts`/`.cts`,
        `.md`/`.markdown`/`.mdx`, and a generic text ingester that covers
        Makefile / Dockerfile / .yml / .toml / .sh / .txt / .rst files.
        Idempotent — calling twice does not double-register.

        Builtins go on `_builtin_source_ingesters` (not the public
        `source_ingesters` list), so any pack-registered hook for the
        same extension takes precedence at dispatch time.

        Imported lazily inside the function to avoid a circular import
        at module load (kb_engine.ingesters depends on kb_engine.types
        and indirectly on this module via the SourceIngester protocol).
        """
        if self._builtin_source_ingesters:
            return
        from .ingesters import (  # noqa: PLC0415 — see docstring
            MarkdownIngester,
            PythonIngester,
            TextIngester,
            TypescriptIngester,
        )
        self._builtin_source_ingesters.extend([
            PythonIngester(),
            TypescriptIngester(),
            MarkdownIngester(),
            TextIngester(),
        ])

    def clear_builtin_ingesters(self) -> None:
        """Remove all seeded builtins. Use in tests for a clean slate."""
        self._builtin_source_ingesters.clear()

    def register_graph_projector(self, hook: GraphProjector) -> None:
        if not isinstance(hook, GraphProjector) and not callable(hook):
            raise TypeError(f"hook {hook!r} is not callable / not a GraphProjector")
        self.graph_projectors.append(hook)

    def register_tool_registrar(self, hook: ToolRegistrar) -> None:
        if not isinstance(hook, ToolRegistrar) and not callable(hook):
            raise TypeError(f"hook {hook!r} is not callable / not a ToolRegistrar")
        self.tool_registrars.append(hook)

    def register_frontmatter_handler(
        self, type_value: str, hook: FrontmatterHandler
    ) -> None:
        if not isinstance(hook, FrontmatterHandler) and not callable(hook):
            raise TypeError(f"hook {hook!r} is not callable / not a FrontmatterHandler")
        self.frontmatter_handlers.setdefault(type_value, []).append(hook)

    def register_constraint_provider(self, hook: ConstraintProvider) -> None:
        """Register a callable that returns ConstraintSpec objects.

        Per M1-Multitenant deliverable 2: each pack registers its own
        constraint provider here; the engine never hard-codes Chio (or
        any other pack's) labels.
        """
        if not isinstance(hook, ConstraintProvider) and not callable(hook):
            raise TypeError(
                f"hook {hook!r} is not callable / not a ConstraintProvider"
            )
        self.constraint_providers.append(hook)

    # === Entry-point loading ===

    def load_entry_points(self, group: str = "kb_engine.plugins") -> int:
        """Discover plugins via importlib.metadata entry points.

        Each entry point should be a module with a `register(registry)`
        function that calls back into `register_*` methods.

        Returns the number of entry points successfully loaded.
        """
        n = 0
        for ep in importlib.metadata.entry_points(group=group):
            try:
                module = ep.load()
            except Exception as e:
                print(f"warning: failed to load entry point {ep.name}: {e}")
                continue
            register_fn = getattr(module, "register", None)
            if register_fn is None:
                print(f"warning: entry point {ep.name} has no `register` function")
                continue
            register_fn(self)
            n += 1
        return n

    # === Dispatch ===

    def ingest_file(self, file_path: str) -> ParsedFile | None:
        """Run source ingesters; first non-None wins.

        Order: pack/user-registered hooks (`source_ingesters`) FIRST,
        then the kb-engine builtins (`_builtin_source_ingesters`). This
        encodes the documented precedence rule: pack > builtin.
        """
        for ingester in self.source_ingesters:
            result = ingester(file_path)
            if result is not None:
                return result
        for ingester in self._builtin_source_ingesters:
            result = ingester(file_path)
            if result is not None:
                return result
        return None

    def project_graph(self, parsed: ParsedFile) -> list[Node | Edge]:
        """Run all graph projectors and union their output."""
        out: list[Node | Edge] = []
        for projector in self.graph_projectors:
            out.extend(projector(parsed))
        return out

    def register_tools(self, server: object) -> None:
        """Run all tool registrars against the given server."""
        for registrar in self.tool_registrars:
            registrar(server)

    def handle_frontmatter(
        self, type_value: str, frontmatter: dict[str, Any]
    ) -> list[DerivedRecord]:
        """Run handlers registered for `type_value` and union their output.

        Handlers registered with `type_value="*"` always run.
        """
        out: list[DerivedRecord] = []
        for hook in self.frontmatter_handlers.get(type_value, []):
            out.extend(hook(type_value, frontmatter))
        for hook in self.frontmatter_handlers.get("*", []):
            out.extend(hook(type_value, frontmatter))
        return out

    def iter_constraint_specs(self) -> list[ConstraintSpec]:
        """Collect every registered pack's ConstraintSpecs.

        Returns an empty list when no provider is registered — the
        engine's "no Chio knowledge" rule. Callers (the ingest
        pipeline at bootstrap time) hand this list to
        Neo4jStore.apply_constraint_specs().
        """
        out: list[ConstraintSpec] = []
        for provider in self.constraint_providers:
            out.extend(provider())
        return out
