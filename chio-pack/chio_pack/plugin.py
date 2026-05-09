"""Registration of chio-pack's hooks against kb_engine.Registry.

Per PLAN.md "kb-engine ↔ chio-pack boundary", chio-pack is the canonical
schema pack. This module registers four hook implementations:

  - SourceIngester for Rust files (.rs) — minimal today; Phase 1.3+
    uses tree-sitter for symbol extraction.
  - GraphProjector emitting ChioFile/ChioCrate nodes + CONTAINS edges.
  - ToolRegistrar — stub today; Phase 1.3+ registers 10 kb_* tools.
  - FrontmatterHandler routing vault-note frontmatter to the right
    derived-store target (graphiti / neo4j) based on `type` and
    `chio-node` fields.

The `register(registry)` entry point is declared in
chio-pack/pyproject.toml under [project.entry-points."kb_engine.plugins"]
so kb_engine.Registry.load_entry_points() picks it up automatically
when chio-pack is installed.

This module proves the engine ↔ pack boundary works end-to-end:
chio_pack imports kb_engine; kb_engine never imports chio_pack
(enforced by ops/ci/check-imports.py).
"""
from __future__ import annotations

from typing import Any

from kb_engine import (
    DerivedRecord,
    Edge,
    Node,
    ParsedFile,
    Registry,
)

from . import schema
from .tools import ALL_TOOLS


# === SourceIngester ===


def rust_source_ingester(file_path: str) -> ParsedFile | None:
    """Recognize .rs files. Today returns a stub ParsedFile so the
    GraphProjector has something to project. Phase 1.3+ reads file
    content and extracts symbols via tree-sitter.
    """
    if not file_path.endswith(".rs"):
        return None
    return ParsedFile(
        path=file_path,
        language="rust",
        text="",  # Phase 1.3+
        symbols=[],  # Phase 1.3+
        properties={"crate": _crate_from_path(file_path)},
    )


def _crate_from_path(path: str) -> str:
    """Best-effort crate name from path 'crates/<name>/src/...'."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "crates":
        return parts[1]
    return "unknown"


# === GraphProjector ===


def chio_graph_projector(parsed: ParsedFile) -> list[Node | Edge]:
    """Emit ChioFile + ChioCrate nodes plus a CONTAINS edge.

    Phase 1.3+ extends to ChioSymbol nodes (one per parsed.symbols
    entry) plus CALLS/IMPORTS/DEFINES edges where the parser surfaces
    them.
    """
    if parsed.language != "rust":
        return []
    out: list[Node | Edge] = []
    file_id = f"file:{parsed.path}"
    out.append(Node(
        id=file_id,
        label=schema.FILE,
        properties={"path": parsed.path},
    ))
    crate = parsed.properties.get("crate", "unknown")
    if crate != "unknown":
        crate_id = f"crate:{crate}"
        out.append(Node(
            id=crate_id,
            label=schema.CRATE,
            properties={"name": crate},
        ))
        out.append(Edge(
            src_id=crate_id,
            dst_id=file_id,
            relationship=schema.CONTAINS,
        ))
    return out


# === ToolRegistrar ===


def chio_tool_registrar(server: object) -> None:
    """Register the 10 ``kb_*`` MCP tools on the gateway server.

    The 10 tools (per AGENTS.md "The 10 MCP tools") are owned by
    chio-pack and live as one module each under
    :mod:`chio_pack.tools`. Each module exposes ``NAME``,
    ``DESCRIPTION``, ``INPUT_SCHEMA``, and a ``call(arguments)`` function.

    ``server`` is duck-typed: any object with a callable
    ``register_tool(name, description, input_schema, call)`` attribute
    satisfies the contract. The Phase 1.3+ MCP-server-framework handle
    will satisfy it; tests use
    :class:`chio_pack.tools.fake_server.FakeServer`.

    Tool implementations are thin shims that return
    ``{"status": "stub", "reason": "Phase 1.3+", ...}`` until their
    underlying retrieval paths are wired (Phase 1.3+, see PLAN.md). The
    plugin contract — *registration mechanism* — is what's load-bearing
    here. Swapping a stub for a real query is one-line work inside the
    relevant tool module once pgvector + Neo4j + the chunker are wired.

    Raises:
        TypeError: if ``server`` does not expose a callable
            ``register_tool``. The error is intentional — failing fast at
            registrar time beats silently dropping tools.
    """
    register = getattr(server, "register_tool", None)
    if not callable(register):
        raise TypeError(
            f"server {type(server).__name__} does not expose a callable "
            "register_tool(name, description, input_schema, call); "
            "see chio_pack.tools.fake_server.FakeServer for the protocol."
        )
    for tool in ALL_TOOLS:
        register(
            tool.NAME,
            tool.DESCRIPTION,
            tool.INPUT_SCHEMA,
            tool.call,
        )


# === FrontmatterHandler ===


def chio_frontmatter_handler(
    type: str, frontmatter: dict[str, Any]
) -> list[DerivedRecord]:
    """Route a vault-note frontmatter to derived-store targets.

    Per AGENTS.md hard rule #1, this MUST NOT write directly to
    Graphiti. It returns DerivedRecord objects; the vault-sync daemon
    (Phase 1.4) is the only writer.
    """
    out: list[DerivedRecord] = []
    if type in schema.GRAPHITI_TYPES:
        out.append(DerivedRecord(
            target="graphiti",
            payload={
                "name": frontmatter.get(
                    "graphiti_episode_name", frontmatter.get("title", "")
                ),
                "type": type,
                "scope": frontmatter.get("scope", "chio-repo"),
                "source_description": frontmatter.get("source_description", ""),
                "frontmatter": frontmatter,
            },
        ))
    if type in schema.NEO4J_TYPES:
        label = schema.label_for_chio_node(frontmatter.get("chio-node"))
        if label:
            out.append(DerivedRecord(
                target="neo4j",
                payload={
                    "id": frontmatter.get("id", ""),
                    "label": label,
                    "properties": frontmatter,
                },
            ))
    return out


# === Registry entry point ===


def register(registry: Registry) -> None:
    """Called by `kb_engine.Registry.load_entry_points()`.

    Wired in chio-pack/pyproject.toml under
    `[project.entry-points."kb_engine.plugins"]`.
    """
    registry.register_source_ingester(rust_source_ingester)
    registry.register_graph_projector(chio_graph_projector)
    registry.register_tool_registrar(chio_tool_registrar)
    for type_ in schema.GRAPHITI_TYPES | schema.NEO4J_TYPES:
        registry.register_frontmatter_handler(type_, chio_frontmatter_handler)
