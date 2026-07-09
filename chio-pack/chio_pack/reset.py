"""Reset helper (`chio-kb-reset`) — drops pack schema tables only.

Does NOT wipe Neo4j / Graphiti. Never calls ``make kb-reset`` volume wipe.
Requires POSTGRES_URL. Safe for Wave 1 re-ingest loops.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print("POSTGRES_URL not set", file=sys.stderr)
        return 2
    schema = os.environ.get("CHIO_KB_PACK_SCHEMA", "chio_kb")
    from kb_engine.store import PostgresStore

    store = PostgresStore.from_url(url, schema=schema)
    store.bootstrap()
    store.reset()
    print(f"reset schema={schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
