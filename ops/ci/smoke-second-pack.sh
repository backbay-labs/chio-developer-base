#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${CHIO_SMOKE_WORK_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/chio-second-pack.XXXXXX")}"
MIN_ENTRY_POINTS="${CHIO_SMOKE_MIN_ENTRY_POINTS:-2}"

cleanup() {
  if [[ -z "${CHIO_SMOKE_WORK_DIR:-}" ]]; then
    rm -rf "$WORK_DIR"
  fi
}
trap cleanup EXIT

python3 -m venv "$WORK_DIR/.venv"
PY="$WORK_DIR/.venv/bin/python"

"$PY" -m pip install --upgrade pip >/dev/null
"$PY" -m pip install -q -e "$ROOT/kb-engine" -e "$ROOT/chio-pack"

"$WORK_DIR/.venv/bin/chio-dev" init-pack demo --path "$WORK_DIR" >/dev/null
"$PY" -m pip install -q -e "$WORK_DIR/demo-pack"

LOADED="$("$PY" - <<'PY'
from kb_engine import Registry

r = Registry()
print(r.load_entry_points())
PY
)"

echo "loaded entry points: $LOADED"

if [[ "$LOADED" -lt "$MIN_ENTRY_POINTS" ]]; then
  echo "expected at least $MIN_ENTRY_POINTS entry point(s), got $LOADED" >&2
  exit 1
fi
