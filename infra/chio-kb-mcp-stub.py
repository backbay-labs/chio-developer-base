"""Phase 1.1 health-stub server for chio-kb-mcp.

Replaced by the real MCP server in Phase 1.3+ (the 10 `kb_*` tools,
ranking, signed-retrieval envelope per PLAN.md Moonshot 2). Today this
exists so:

  - `make kb-up` brings up the compose stack and verifies all four
    services reach a healthy state.
  - `make kb-smoke` can curl /health and confirm the chio-kb-mcp
    container is reachable end-to-end.

Responds 200 on /health, 501 on every other path.
"""
from __future__ import annotations

import http.server
import os
import sys


HOST = os.environ.get("CHIO_KB_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("CHIO_KB_MCP_PORT", "8111"))


class StubHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler convention)
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","phase":"1.1","note":"stub"}\n')
            return
        self.send_response(501)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"chio-kb-mcp Phase 1.1 stub. The real MCP gateway "
            b"is Phase 1.3+. See PLAN.md.\n"
        )

    def log_message(self, fmt, *args):
        sys.stdout.write(f"{self.address_string()} - {fmt % args}\n")
        sys.stdout.flush()


def main() -> int:
    print(f"chio-kb-mcp Phase 1.1 stub listening on {HOST}:{PORT}", flush=True)
    server = http.server.ThreadingHTTPServer((HOST, PORT), StubHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
