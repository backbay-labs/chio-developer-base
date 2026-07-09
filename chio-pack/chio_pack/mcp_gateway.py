"""Thin entrypoint so `chio-kb-mcp` console script resolves.

The production gateway lives at ``infra/chio-kb-mcp-server.py`` (Docker
CMD). This module re-exports that server's ``main`` for local
``uv run chio-kb-mcp`` / entry-point installs.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    server = repo / "infra" / "chio-kb-mcp-server.py"
    if not server.is_file():
        # Installed wheel / container layout: server copied to /app/server.py
        alt = Path("/app/server.py")
        if alt.is_file():
            server = alt
        else:
            print(f"chio-kb-mcp: server not found at {server}", file=sys.stderr)
            return 2
    # Execute as __main__ so module-level SERVER boots.
    runpy.run_path(str(server), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
