#!/usr/bin/env python3
"""
migrate-seeds.py — one-shot migration of arc PR #599 seeds/graphiti/*.json
into vault/episodes/*.md notes with frontmatter that the vault-sync daemon
(Phase 1) can use to derive Graphiti episodes from.

Idempotent: re-running with unchanged source JSON produces no writes
(seed_content_hash in frontmatter is checked against the source). Re-running
with changed source updates the note in place and PRESERVES any human edits
in sections marked `<!-- HUMAN EDITS BELOW THIS LINE -->`.

Phase 0 deliverable. Tracked by ADR-0000 commitment #2 and PLAN.md Phase 1.3.

Usage:
    uv run python ops/scripts/migrate-seeds.py \\
        --seeds ../arc/ops/knowledge-base/seeds/graphiti \\
        --vault vault \\
        --branch codex/chio-kb-a-grade-dogfood
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Body subkeys that should appear as TYPED LISTS in frontmatter (not body sections).
#
# All keys are stored snake_case to match the convention used by the existing
# vault notes (see vault/episodes/*.md, vault/_meta/templates/episode.md, and
# the chio-frontmatter.css selectors that target snake_case property keys).
KNOWN_TYPED_LIST_FIELDS = {
    "authoritative_files",
    "tests",
    "validation",
    # Per-episode allow-list of MCP tools an agent should reach for first.
    # Added M0-D.3 to stop dumping the field as raw JSON in the body when a
    # seed (e.g. agent-workflow-constraints.json) ships it.
    "preferred_tools",
}

# Body subkeys that become markdown ## sections in the rendered note.
KNOWN_BODY_PROSE_FIELDS = {
    "editing_guidance": "Guidance",
    "constraints":      "Constraints",
    "decisions":        "Decisions",
    "release_steps":    "Release steps",
    "evidence":         "Evidence",
    "workflow":         "Workflow",
    "rules":            "Rules",
}

HUMAN_EDIT_MARKER = "<!-- HUMAN EDITS BELOW THIS LINE -->"


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", name).lower()
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "untitled"


def sha256_hex(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def yaml_string(s: str) -> str:
    """Quote a string safely for YAML. JSON strings are valid YAML quoted strings."""
    return json.dumps(s, ensure_ascii=False)


def render_frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, str):
            lines.append(f"{key}: {yaml_string(value)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    if isinstance(item, str):
                        lines.append(f"  - {yaml_string(item)}")
                    else:
                        lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
        else:
            raise TypeError(f"unsupported frontmatter value type for {key}: {type(value)}")
    lines.append("---")
    return "\n".join(lines)


def build_note(seed: dict[str, Any], source_path: Path, branch: str) -> tuple[str, str]:
    """Return (slug, full_markdown_content) for the seed."""
    name = seed["name"]
    slug = slugify(name)
    seed_type = seed.get("type", "episode")
    body = seed.get("body", {}) if isinstance(seed.get("body"), dict) else {}
    summary = body.get("summary", "")

    typed_lists = {
        k: body[k]
        for k in KNOWN_TYPED_LIST_FIELDS
        if k in body and isinstance(body[k], list)
    }

    meta: dict[str, Any] = {
        "id":                       f"episode.{slug}",
        "type":                     f"episode-{seed_type.replace('_', '-')}",
        "status":                   "imported",
        "scope":                    seed.get("scope", "chio-repo"),
        "title":                    name,
        "graphiti_episode_name":    name,
        "source_description":       seed.get("source_description", ""),
    }
    for k, v in typed_lists.items():
        meta[k] = v
    meta["imported_from"]      = f"{source_path.as_posix()} @ {branch}"
    meta["imported_at"]        = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["seed_content_hash"]  = "sha256:" + sha256_hex(seed)

    sections: list[str] = []
    sections.append(render_frontmatter(meta))
    sections.append("")
    sections.append(f"# {name}")
    sections.append("")
    if summary:
        sections.append(summary)
        sections.append("")

    for body_key, heading in KNOWN_BODY_PROSE_FIELDS.items():
        if body_key not in body:
            continue
        v = body[body_key]
        sections.append(f"## {heading}")
        sections.append("")
        if isinstance(v, list):
            for item in v:
                sections.append(f"- {item}")
        else:
            sections.append(str(v))
        sections.append("")

    handled = {"summary", *KNOWN_TYPED_LIST_FIELDS, *KNOWN_BODY_PROSE_FIELDS.keys()}
    leftover = {k: v for k, v in body.items() if k not in handled}
    if leftover:
        sections.append("## Unmapped body fields (review)")
        sections.append("")
        sections.append("```json")
        sections.append(json.dumps(leftover, indent=2, sort_keys=True))
        sections.append("```")
        sections.append("")

    sections.append(HUMAN_EDIT_MARKER)
    sections.append("")

    return slug, "\n".join(sections)


def existing_seed_hash(text: str) -> str | None:
    m = re.search(r"^seed_content_hash:\s*\"?sha256:([0-9a-f]+)\"?\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def split_at_human_marker(text: str) -> tuple[str, str]:
    idx = text.find(HUMAN_EDIT_MARKER)
    if idx == -1:
        return text, ""
    end = idx + len(HUMAN_EDIT_MARKER)
    return text[:end], text[end:]


def write_note(out_path: Path, content: str, *, force: bool) -> str:
    """
    Returns one of: 'created', 'updated', 'preserved', 'skipped'.
    Preserves text below HUMAN_EDIT_MARKER if the file already exists.
    """
    new_hash_match = re.search(r"^seed_content_hash:\s*\"?sha256:([0-9a-f]+)\"?\s*$",
                               content, re.MULTILINE)
    assert new_hash_match, "rendered note must include seed_content_hash"
    new_hash = new_hash_match.group(1)

    if out_path.exists():
        existing = out_path.read_text()
        old_hash = existing_seed_hash(existing)
        if old_hash == new_hash and not force:
            return "skipped"
        _, human = split_at_human_marker(existing)
        machine, _ = split_at_human_marker(content)
        merged = machine + human
        out_path.write_text(merged)
        return "preserved" if human.strip() else "updated"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content)
    return "created"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", required=True, help="path to seeds/graphiti/ directory")
    p.add_argument("--vault", required=True, help="path to vault/ root")
    p.add_argument("--branch", default="HEAD", help="source branch label for provenance")
    p.add_argument("--force", action="store_true", help="rewrite even if seed_content_hash matches")
    p.add_argument("--dry-run", action="store_true", help="report actions without writing")
    args = p.parse_args()

    seeds_dir = Path(args.seeds)
    vault_dir = Path(args.vault)
    if not seeds_dir.is_dir():
        print(f"error: --seeds {seeds_dir} not a directory", file=sys.stderr)
        return 2

    out_dir = vault_dir / "episodes"
    seeds = sorted(seeds_dir.glob("*.json"))
    if not seeds:
        print(f"warning: no *.json in {seeds_dir}", file=sys.stderr)
        return 1

    summary: dict[str, int] = {}
    for src in seeds:
        try:
            with src.open() as f:
                payload = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  malformed  {src.name}: {e}", file=sys.stderr)
            summary["malformed"] = summary.get("malformed", 0) + 1
            continue

        if not isinstance(payload, dict) or "name" not in payload:
            print(f"  malformed  {src.name}: missing top-level name", file=sys.stderr)
            summary["malformed"] = summary.get("malformed", 0) + 1
            continue

        slug, content = build_note(payload, source_path=src, branch=args.branch)
        out = out_dir / f"{slug}.md"
        if args.dry_run:
            action = "would-create" if not out.exists() else "would-update"
        else:
            action = write_note(out, content, force=args.force)
        summary[action] = summary.get(action, 0) + 1
        print(f"  {action:<12}  {src.name}  →  {out}")

    print()
    for k in sorted(summary):
        print(f"  {k}: {summary[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
