-- Enable pgvector. Phase 1.x will add chio_kb schema + tables for
-- code_chunks and doc_chunks. For now this just installs the extension
-- so the kb-engine ingest pipeline can create vector columns.
CREATE EXTENSION IF NOT EXISTS vector;
