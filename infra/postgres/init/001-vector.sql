-- Enable pgvector. The `chio_kb` schema and `code_chunks` table are
-- created at runtime by `PostgresStore.bootstrap()` (idempotent). The
-- `doc_chunks` table is not yet created; doc indexing lands in Phase 1.x
-- (see PLAN.md M1 / T1.4 generic text ingesters). This file just
-- installs the extension so the runtime CREATE TABLE has `vector`
-- available.
CREATE EXTENSION IF NOT EXISTS vector;
