"""The 10 ``kb_*`` MCP tools owned by chio-pack.

Per PLAN.md "Plugin/extension architecture" and AGENTS.md "The 10 MCP
tools", each tool is a small module exposing four attributes:

  - ``NAME`` (str): MCP tool name (e.g. ``kb_search_code``).
  - ``DESCRIPTION`` (str): human-readable one-line summary.
  - ``INPUT_SCHEMA`` (dict): JSON-Schema for the tool's arguments.
  - ``call(arguments: dict) -> dict``: the tool implementation.

The 10 tools are wired into the gateway by
:func:`chio_pack.plugin.chio_tool_registrar`, which calls
``server.register_tool(name, description, input_schema, call)`` once per
tool. The ``server`` is duck-typed — any object with a callable
``register_tool`` attribute satisfies the contract. Tests use the
:class:`chio_pack.tools.fake_server.FakeServer`. Production uses the
Phase 1.3+ MCP-server-framework handle.

The implementations themselves are deliberately thin shims that return
``{"status": "stub", "reason": "Phase 1.3+", ...}`` until the underlying
retrieval path is wired (Phase 1.3+, see PLAN.md). The point of landing
the registrar now is the plugin contract — once ``register_tool`` is
proven end-to-end, swapping a stub for a real query is one-line work
inside the relevant tool module.

The schema fields here mirror arc PR #599's ``mcp-server`` so a client
that worked against arc's ``CHIO_KB_MCP`` continues to work against the
chio-developer-base gateway.
"""
from __future__ import annotations

from . import (
    kb_add_episode,
    kb_brief_feature,
    kb_context,
    kb_eval,
    kb_find_docs,
    kb_find_tests,
    kb_impact,
    kb_neighbors,
    kb_search_code,
    kb_search_docs,
)

# Canonical order matches AGENTS.md "The 10 MCP tools".
ALL_TOOLS = (
    kb_search_code,
    kb_search_docs,
    kb_find_tests,
    kb_find_docs,
    kb_neighbors,
    kb_context,
    kb_impact,
    kb_brief_feature,
    kb_eval,
    kb_add_episode,
)

ALL_NAMES = tuple(t.NAME for t in ALL_TOOLS)

__all__ = [
    "ALL_TOOLS",
    "ALL_NAMES",
    "kb_search_code",
    "kb_search_docs",
    "kb_find_tests",
    "kb_find_docs",
    "kb_neighbors",
    "kb_context",
    "kb_impact",
    "kb_brief_feature",
    "kb_eval",
    "kb_add_episode",
]
