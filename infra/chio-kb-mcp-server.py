"""Real chio-kb-mcp gateway (Wave 1 / Phase 1.3).

Replaces the Phase 1.1 health stub. Exposes:

  GET  /health
  POST /mcp/   — JSON-RPC 2.0 (initialize, tools/list, tools/call)

Tools are registered via chio-pack's plugin ToolRegistrar against a
duck-typed server that stores callables. Retrieval tools use the
shared RuntimeContext (Postgres + Neo4j + Embedder).
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse


HOST = os.environ.get("CHIO_KB_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("CHIO_KB_MCP_PORT", "8111"))
PROTOCOL_VERSION = "2025-03-26"


class ToolServer:
    """Duck-typed MCP tool registry matching chio_tool_registrar."""

    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        call: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "call": call,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            }
            for t in self.tools.values()
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            return {"status": "error", "reason": f"unknown tool: {name}"}
        return tool["call"](arguments or {})


def build_server() -> ToolServer:
    from chio_pack.plugin import chio_tool_registrar
    from chio_pack.runtime import get_runtime

    # Eagerly construct runtime so /health can report store readiness.
    get_runtime()
    server = ToolServer()
    chio_tool_registrar(server)
    return server


SERVER = build_server()


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def handle_mcp(body: dict[str, Any]) -> dict[str, Any]:
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return _jsonrpc_result(
            req_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "chio-kb-mcp", "version": "0.3.0"},
            },
        )
    if method == "notifications/initialized":
        return _jsonrpc_result(req_id, {})
    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": SERVER.list_tools()})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            return _jsonrpc_error(req_id, -32602, "missing params.name")
        try:
            result = SERVER.call_tool(str(name), arguments)
        except Exception as exc:  # noqa: BLE001 — surface to client
            return _jsonrpc_result(
                req_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "error",
                                    "reason": str(exc),
                                    "traceback": traceback.format_exc(),
                                }
                            ),
                        }
                    ],
                    "isError": True,
                },
            )
        return _jsonrpc_result(
            req_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(result, default=str)}
                ],
                "structuredContent": result,
                "isError": result.get("status") == "error",
            },
        )
    return _jsonrpc_error(req_id, -32601, f"method not found: {method}")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            from chio_pack.runtime import get_runtime

            rt = get_runtime()
            payload = {
                "status": "ok",
                "phase": "1.3",
                "tools": len(SERVER.tools),
                "postgres": rt.postgres is not None,
                "neo4j": rt.neo4j is not None,
                "embedder": type(rt.embedder).__name__,
                "pack_schema": rt.pack_schema,
            }
            self._send_json(200, payload)
            return
        self._send_text(404, "not found\n")

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path not in ("/mcp", "/mcp/"):
            self._send_text(404, "not found\n")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return
        if isinstance(body, list):
            responses = [handle_mcp(item) for item in body]
            self._send_json(200, responses)
            return
        self._send_json(200, handle_mcp(body))

    def _send_json(self, code: int, payload: Any) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, code: int, text: str) -> None:
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(f"{self.address_string()} - {fmt % args}\n")
        sys.stdout.flush()


def main() -> int:
    print(
        f"chio-kb-mcp Phase 1.3 listening on {HOST}:{PORT} "
        f"({len(SERVER.tools)} tools)",
        flush=True,
    )
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
