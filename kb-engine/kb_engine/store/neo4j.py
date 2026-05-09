"""Neo4j backing store. Persists Node/Edge from GraphProjector output.

Per the engine ↔ pack boundary, this module knows nothing about Chio*
labels — it operates on the generic Node/Edge dataclasses from
kb_engine.types. Plugins (chio-pack and future <team>-pack) declare
their own namespaced label vocabularies; the store just upserts.

`upsert_nodes` and `upsert_edges` use Cypher MERGE so re-running the
ingest pipeline against the same input is idempotent — incremental
re-ingestion doesn't double-write.

The driver is injected so tests pass a Mock without ever opening a
bolt connection.
"""
from __future__ import annotations

import re
from typing import Any, Sequence

from ..types import ConstraintKind, ConstraintSpec, Edge, Node


# Neo4j label/property names embed directly into Cypher (you can't bind
# them as parameters), so we vet them before formatting. Allow ASCII
# letters, digits, and underscores; reject anything that could break out
# of the identifier and start a new statement.
_NEO4J_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name: str, kind: str) -> str:
    """Validate `name` looks like a plain Cypher identifier."""
    if not isinstance(name, str) or not _NEO4J_IDENT_RE.match(name):
        raise ValueError(
            f"invalid {kind} identifier {name!r}: must match "
            f"{_NEO4J_IDENT_RE.pattern}"
        )
    return name


def _spec_to_cypher(spec: ConstraintSpec) -> str:
    """Render a ConstraintSpec as a single idempotent Cypher statement.

    Uses `IF NOT EXISTS` everywhere so re-running on a database that
    already has the constraint is a no-op. Auto-derives a constraint
    name from label+property+kind when the spec doesn't supply one.
    """
    label = _safe_ident(spec.label, "label")
    prop = _safe_ident(spec.property, "property")
    name = spec.name or f"{label}_{prop}_{spec.kind.value.lower()}"
    name = _safe_ident(name, "constraint name")

    if spec.kind == ConstraintKind.UNIQUENESS:
        return (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
    if spec.kind == ConstraintKind.EXISTENCE:
        return (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS NOT NULL"
        )
    if spec.kind == ConstraintKind.INDEX:
        return (
            f"CREATE INDEX {name} IF NOT EXISTS "
            f"FOR (n:{label}) ON (n.{prop})"
        )
    raise ValueError(f"unknown ConstraintKind {spec.kind!r}")


class Neo4jStore:
    """Property-graph store with idempotent upserts.

    Construct with an injected `driver` (a `neo4j.Driver` in production;
    a `Mock` in tests). `apply_constraints()` is a one-shot at startup;
    `upsert_nodes()` and `upsert_edges()` run on every ingest pass.
    """

    def __init__(self, driver: Any, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    @classmethod
    def from_url(
        cls, uri: str, user: str, password: str, *, database: str = "neo4j",
    ) -> "Neo4jStore":
        """Open a real Neo4j driver. Lazy SDK import."""
        try:
            from neo4j import GraphDatabase  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "neo4j Python driver not installed. `pip install neo4j>=5`."
            ) from e
        driver = GraphDatabase.driver(uri, auth=(user, password))
        return cls(driver, database=database)

    def apply_constraints(self, cypher_statements: Sequence[str]) -> None:
        """Apply uniqueness/index constraints. Statements are passed in by
        the schema pack (chio-pack ships infra/neo4j/constraints.cypher).
        Each statement runs in its own transaction; failures of
        individual statements (e.g., 'constraint already exists' on
        re-runs without IF NOT EXISTS) are swallowed in this method —
        callers wanting strict semantics should run statements one-by-one.
        """
        with self.driver.session(database=self.database) as session:
            for stmt in cypher_statements:
                stmt = stmt.strip()
                if not stmt or stmt.startswith("//"):
                    continue
                try:
                    session.run(stmt)
                except Exception:
                    # Idempotent constraint application: ignore "already exists"
                    pass

    def apply_constraint_specs(self, specs: Sequence[ConstraintSpec]) -> int:
        """Apply ConstraintSpec objects (M1-Multitenant deliverable 2).

        Renders each spec via `_spec_to_cypher` and runs them through
        the same idempotent path as `apply_constraints()`. The engine
        calls this once at bootstrap with the union of every loaded
        pack's specs (via `Registry.iter_constraint_specs()`), so
        adopters get pack-specific schema enforcement without the
        engine knowing which labels exist.

        Returns the number of specs actually attempted (== len(specs))
        so callers can log "applied N constraint specs".
        """
        statements = [_spec_to_cypher(s) for s in specs]
        self.apply_constraints(statements)
        return len(statements)

    def upsert_nodes(self, nodes: Sequence[Node]) -> int:
        """Idempotent MERGE of nodes by (label, id). Returns count.

        Cypher batched by label so the MERGE picks up the right schema
        index. Properties are unioned (existing fields not overwritten
        unless the upsert provides a new value).
        """
        if not nodes:
            return 0
        # Bucket by label for the batched MERGE
        by_label: dict[str, list[Node]] = {}
        for node in nodes:
            by_label.setdefault(node.label, []).append(node)

        total = 0
        with self.driver.session(database=self.database) as session:
            for label, batch in by_label.items():
                rows = [
                    {"id": n.id, "props": dict(n.properties)}
                    for n in batch
                ]
                # Label can't be parameterized in Cypher, so compose it
                # from a vetted source: the engine accepts whatever the
                # plugin emitted, and the plugin owns the namespacing
                # (per the engine ↔ pack boundary).
                cypher = (
                    f"UNWIND $rows AS row "
                    f"MERGE (n:`{label}` {{id: row.id}}) "
                    f"SET n += row.props"
                )
                session.run(cypher, rows=rows)
                total += len(batch)
        return total

    def upsert_edges(self, edges: Sequence[Edge]) -> int:
        """Idempotent MERGE of edges by (src_id, dst_id, relationship).

        Both endpoints must already exist as nodes (or be created by the
        match — see Cypher below). The store does not invent labels for
        endpoint nodes; if the endpoint is missing, the MERGE skips and
        the edge isn't created. Callers should upsert nodes first.
        """
        if not edges:
            return 0
        by_rel: dict[str, list[Edge]] = {}
        for edge in edges:
            by_rel.setdefault(edge.relationship, []).append(edge)

        total = 0
        with self.driver.session(database=self.database) as session:
            for rel, batch in by_rel.items():
                rows = [
                    {"src": e.src_id, "dst": e.dst_id, "props": dict(e.properties)}
                    for e in batch
                ]
                cypher = (
                    f"UNWIND $rows AS row "
                    f"MATCH (s {{id: row.src}}) "
                    f"MATCH (d {{id: row.dst}}) "
                    f"MERGE (s)-[r:`{rel}`]->(d) "
                    f"SET r += row.props"
                )
                session.run(cypher, rows=rows)
                total += len(batch)
        return total

    def query_neighbors(self, node_id: str, depth: int = 1, limit: int = 50) -> list[dict[str, Any]]:
        """Return neighbors within `depth` hops of `node_id`. Phase 1.3
        helper for the kb_neighbors MCP tool (Phase 1.3+ wires it).
        """
        cypher = (
            "MATCH (n {id: $id})-[r*1..$depth]-(m) "
            "RETURN m.id AS id, labels(m) AS labels, "
            "       [rel IN r | type(rel)] AS path "
            "LIMIT $limit"
        )
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, id=node_id, depth=depth, limit=limit)
            return [dict(record) for record in result]

    def delete_node(self, node_id: str) -> int:
        """Hard-delete a single node by id (across any label).

        Used by the vault-sync daemon's deletion path: vault is
        canonical, Graphiti / Neo4j are derived, so removing a vault
        note must remove the corresponding graph node. The
        accompanying tombstone JSONL audit (sync.TombstoneAuditWriter)
        keeps the deletion observable and reversible.

        DETACH DELETE drops incident edges along with the node, so the
        graph stays consistent (no dangling rels). Returns the number
        of nodes actually deleted (0 if no such id exists — idempotent
        re-run is safe).
        """
        cypher = "MATCH (n {id: $id}) DETACH DELETE n RETURN count(n) AS deleted"
        with self.driver.session(database=self.database) as session:
            result = session.run(cypher, id=node_id)
            try:
                record = result.single()
            except Exception:
                record = None
            if record is None:
                return 0
            try:
                # Driver result records support `record["key"]`.
                return int(record["deleted"])
            except (KeyError, TypeError, ValueError):
                return 0

    def reset(self, label_prefix: str | None = None) -> None:
        """Delete all nodes (or all nodes whose label starts with
        `label_prefix`). Used by `make kb-reset`. Destructive.
        """
        if label_prefix:
            cypher = f"MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH '{label_prefix}') DETACH DELETE n"
        else:
            cypher = "MATCH (n) DETACH DELETE n"
        with self.driver.session(database=self.database) as session:
            session.run(cypher)

    def close(self) -> None:
        if hasattr(self.driver, "close"):
            self.driver.close()
