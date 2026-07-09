"""Smoke helper for local installs (`chio-kb-smoke`).

Hits ``/health`` and ``tools/list`` against a running gateway.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("CHIO_KB_MCP_URL", "http://localhost:8111")
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            health = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"health failed: {exc}", file=sys.stderr)
        return 1
    print("health:", json.dumps(health))
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    ).encode()
    req = urllib.request.Request(
        f"{base}/mcp/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"tools/list failed: {exc}", file=sys.stderr)
        return 1
    tools = (payload.get("result") or {}).get("tools") or []
    print(f"tools: {len(tools)}")
    for t in tools:
        print(" -", t.get("name"))
    return 0 if tools else 2


if __name__ == "__main__":
    raise SystemExit(main())
