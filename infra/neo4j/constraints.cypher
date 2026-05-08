// Bootstrap constraints for the Chio property graph.
//
// Phase 1.1 placeholder. The chio-pack schema (chio_pack/schema.py)
// will define the canonical labels and edge types in Phase 1.3+; the
// projector will emit nodes with stable IDs that these uniqueness
// constraints lock in.
//
// Run via: cypher-shell -u neo4j -p ... < /var/lib/neo4j/import/chio/constraints.cypher
//
// Today's constraints are a forward-looking superset of what
// chio-pack will eventually emit. Empty body is fine; Neo4j tolerates
// missing labels at constraint creation when IF NOT EXISTS is used.

// Each Chio* node has a stable `id` field that uniquely identifies it.
CREATE CONSTRAINT chio_capability_id IF NOT EXISTS
  FOR (n:ChioCapability) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_receipt_id IF NOT EXISTS
  FOR (n:ChioReceipt) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_guard_id IF NOT EXISTS
  FOR (n:ChioGuard) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_policy_id IF NOT EXISTS
  FOR (n:ChioPolicy) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_protocol_id IF NOT EXISTS
  FOR (n:ChioProtocol) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_standard_id IF NOT EXISTS
  FOR (n:ChioStandard) REQUIRE n.id IS UNIQUE;

// Structural (file/symbol/crate) nodes from the source-code projector.
CREATE CONSTRAINT chio_file_path IF NOT EXISTS
  FOR (n:ChioFile) REQUIRE n.path IS UNIQUE;

CREATE CONSTRAINT chio_symbol_id IF NOT EXISTS
  FOR (n:ChioSymbol) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT chio_crate_name IF NOT EXISTS
  FOR (n:ChioCrate) REQUIRE n.name IS UNIQUE;
