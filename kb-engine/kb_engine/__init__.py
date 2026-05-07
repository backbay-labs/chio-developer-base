"""kb-engine — generic retrieval / graph / MCP framework.

Phase 1.2 deliverable. Today this is a placeholder package so:

1. `make kb-status` reports kb-engine as ok.
2. A contributor can `uv sync` from a fresh checkout without errors.
3. The engine ↔ pack import-rule CI check has a real package to inspect.

There is no functional engine yet. See ../_README.md for the planned
layout and the four plugin hooks that domain packs (chio-pack and
future <team>-pack) implement against.

Importing anything beyond `__version__` from this package right now
will raise NotImplementedError on purpose — to make it visibly clear
that the engine is not yet implemented and to prevent a Phase 0
contributor from accidentally building against vapor.
"""
__version__ = "0.0.1"


def __getattr__(name: str):
    if name == "__version__":
        return globals()["__version__"]
    raise NotImplementedError(
        f"kb_engine.{name} is not yet implemented. "
        f"See chio-developer-base/PLAN.md (Phase 1.2) and kb-engine/_README.md."
    )
