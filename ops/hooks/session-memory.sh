#!/usr/bin/env bash
set -euo pipefail

scratchpad="${1:-.cursor/scratchpad.md}"
if [[ ! -f "$scratchpad" ]]; then
  echo "usage: $0 path/to/scratchpad.md" >&2
  exit 2
fi

session_id="${CHIO_DEV_SESSION_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
text="$(python3 - "$scratchpad" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
content = path.read_text(encoding="utf-8")
print(content[-4000:])
PY
)"

uv run --project chio-pack chio-dev --help >/dev/null 2>&1 || {
  echo "chio-dev unavailable; run from repo root after uv sync" >&2
  exit 2
}

uv run --project chio-pack python - "$session_id" "$text" <<'PY'
import json
import sys

from chio_pack.tools import kb_memory_add

session_id, text = sys.argv[1], sys.argv[2]
result = kb_memory_add.call({
    "session_id": session_id,
    "title": "Scratchpad delta mirror",
    "text": text,
})
print(json.dumps(result, indent=2))
raise SystemExit(0 if result.get("status") == "ok" else 1)
PY
