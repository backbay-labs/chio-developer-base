"""chio-pack schema: namespaced labels and edge types for the Chio property graph.

Per AGENTS.md hard rule #3, `kb_engine` cannot import `chio_*`. The
dependency flows the OTHER way: chio_pack imports kb_engine to declare
its own schema using the engine's plugin protocols.

All node labels are namespaced with the `Chio` prefix to prevent
collisions if other adopter packs (platform-pack, opus-pack, etc.) join
the same Neo4j instance later.
"""
from __future__ import annotations

# === High-level concept nodes ===
CAPABILITY = "ChioCapability"
RECEIPT = "ChioReceipt"
GUARD = "ChioGuard"
POLICY = "ChioPolicy"
PROTOCOL = "ChioProtocol"
STANDARD = "ChioStandard"

# === Structural nodes (from source-code projector) ===
FILE = "ChioFile"
SYMBOL = "ChioSymbol"
CRATE = "ChioCrate"
DOC = "ChioDoc"
SPEC = "ChioSpec"
SECTION = "ChioSection"

# === Concept hubs ===
CONCEPT = "ChioConcept"
ENTITY = "ChioEntity"

ALL_NODE_LABELS = {
    CAPABILITY, RECEIPT, GUARD, POLICY, PROTOCOL, STANDARD,
    FILE, SYMBOL, CRATE, DOC, SPEC, SECTION,
    CONCEPT, ENTITY,
}

# === Edge relationship vocabulary ===

# Structural
CONTAINS = "CONTAINS"
CALLS = "CALLS"
IMPORTS = "IMPORTS"
DEPENDS_ON = "DEPENDS_ON"

# Documentation
DOCUMENTED_IN = "DOCUMENTED_IN"
HAS_DOC = "HAS_DOC"
CANONICAL_DOC = "CANONICAL_DOC"

# Implementation
IMPLEMENTS = "IMPLEMENTS"
TESTED_BY = "TESTED_BY"
HAS_TEST = "HAS_TEST"
DEFINES = "DEFINES"

# Chio-protocol-specific
GUARDS = "GUARDS"
VALIDATES = "VALIDATES"
SUPERSEDES = "SUPERSEDES"
OWNED_BY = "OWNED_BY"
VALIDATED_BY = "VALIDATED_BY"
USES_CONCEPT = "USES_CONCEPT"
MENTIONS = "MENTIONS"


def is_chio_label(label: str) -> bool:
    """True if the label is in this pack's namespace."""
    return label in ALL_NODE_LABELS


# === Vault-note type → graph-target mapping ===

# Episode types are derived to Graphiti (temporal memory).
GRAPHITI_TYPES = frozenset({
    "episode-architecture-summary",
    "episode-architecture-decision",
    "episode-workflow-constraint",
    "episode-release-note",
    "episode-pr-repair",
    "episode-session-note",
})

# Spec/ADR/playbook types are derived to Neo4j (the property graph).
NEO4J_TYPES = frozenset({
    "spec",
    "adr",
    "playbook",
})


def label_for_chio_node(chio_node: str | None) -> str | None:
    """Map a vault-note `chio-node` frontmatter value to its graph label."""
    if not chio_node:
        return None
    return {
        "Capability": CAPABILITY,
        "Receipt": RECEIPT,
        "Guard": GUARD,
        "Policy": POLICY,
        "Protocol": PROTOCOL,
        "Standard": STANDARD,
    }.get(chio_node)
