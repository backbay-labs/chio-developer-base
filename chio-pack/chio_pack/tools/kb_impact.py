"""kb_impact — estimate related components, tests, and docs for a path or crate."""
from __future__ import annotations

from typing import Any

NAME = "kb_impact"

DESCRIPTION = "Estimate related components, tests, and docs for a path or crate."

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path_or_crate": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
    },
    "required": ["path_or_crate"],
}


def call(arguments: dict[str, Any]) -> dict[str, Any]:
    if "path_or_crate" not in arguments:
        return {
            "status": "error",
            "reason": "missing required argument: path_or_crate",
        }
    from chio_pack.runtime import get_runtime

    path = arguments["path_or_crate"]
    limit = int(arguments.get("limit", 50))
    rt = get_runtime()
    entity_ids = [f"file:{path}", f"crate:{path}", path]
    if "/" not in path and not path.startswith("crates/"):
        entity_ids.append(f"crate:{path}")

    components: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for eid in entity_ids:
        for n in rt.neighbors(eid, depth=2, limit=limit):
            nid = str(n.get("id", ""))
            if not nid or nid in seen:
                continue
            seen.add(nid)
            labels = [str(x) for x in (n.get("labels") or [])]
            item = {"id": nid, "labels": labels, "path": n.get("path")}
            label_blob = " ".join(labels).lower()
            if "test" in label_blob or "/test" in nid.lower():
                tests.append(item)
            elif "doc" in label_blob or nid.startswith("doc:"):
                docs.append(item)
            else:
                components.append(item)

    # Also surface lexical code hits for the path/crate string.
    code_response = rt.search_code(query=path, limit=min(12, limit))
    for hit in code_response.get("results", []):
        components.append(
            {
                "id": f"chunk:{hit.get('id')}",
                "file_path": hit.get("file_path"),
                "similarity": hit.get("similarity"),
            }
        )

    return {
        "status": "ok",
        "tool": NAME,
        "path_or_crate": path,
        "components": components[:limit],
        "tests": tests[:limit],
        "docs": docs[:limit],
    }
