"""Built-in source ingesters shipped with kb-engine.

Per Wave 2 / M1-Ingesters scope: kb-engine ships generic, no-frills text-level
chunkers for `.py`, `.ts`/`.tsx`, and `.md`. Adopters who need real AST-level
parsing (e.g. tree-sitter for Rust) write a pack ingester. This is the
"baseline so a second adopter has *something* to start from" tier.

Architectural notes
-------------------

These ingesters live IN kb-engine but register through the same
`Registry` plugin mechanism that packs use. That makes the precedence rule
explicit: if a pack registers an ingester for the same extension (e.g. a
hypothetical chio-pack Python tree-sitter ingester), the pack wins because
packs load via entry points AFTER builtins are seeded.

These are TEXT EXTRACTION only. They do not emit graph nodes/edges — that's
the projector's job. They do not parse — they CHUNK on structural
delimiters (regex on def/class/heading boundaries). The justification for
not using AST libraries lives in each language file's docstring.
"""
from __future__ import annotations

from .markdown import MarkdownIngester, markdown_source_ingester
from .python import PythonIngester, python_source_ingester
from .typescript import TypescriptIngester, typescript_source_ingester

__all__ = [
    "MarkdownIngester",
    "PythonIngester",
    "TypescriptIngester",
    "markdown_source_ingester",
    "python_source_ingester",
    "typescript_source_ingester",
]
