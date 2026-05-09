"""A minimal in-memory MCP-server fake.

Used by tests and by ``chio_tool_registrar``'s docstring examples to
demonstrate the duck-typed server protocol that
:func:`chio_pack.plugin.chio_tool_registrar` targets:

    server.register_tool(name: str, description: str,
                         input_schema: dict, call: Callable[[dict], dict])

The Phase 1.3+ MCP server framework will expose the same shape (or wrap
it). Keeping a tiny fake here means kb-engine and chio-pack tests don't
need an HTTP/JSON-RPC server to verify the plugin contract round-trips.

Lives in chio-pack (not kb-engine) because it's a test convenience for
pack authors, not part of the engine surface.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    call: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class FakeServer:
    """An in-memory ``Server`` compatible with the registrar protocol.

    Attributes:
        tools: Map of tool-name -> :class:`RegisteredTool`. Direct access
            is fine for tests.
    """

    tools: dict[str, RegisteredTool] = field(default_factory=dict)

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        call: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        if name in self.tools:
            raise ValueError(f"tool already registered: {name}")
        if not callable(call):
            raise TypeError(f"call must be callable, got {type(call).__name__}")
        self.tools[name] = RegisteredTool(
            name=name,
            description=description,
            input_schema=input_schema,
            call=call,
        )

    # Convenience helpers for tests / interactive REPL use.

    def list_tools(self) -> list[str]:
        return sorted(self.tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.tools:
            raise KeyError(name)
        return self.tools[name].call(arguments)
