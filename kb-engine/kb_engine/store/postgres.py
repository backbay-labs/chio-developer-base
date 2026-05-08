"""pgvector backing store. Stores code/doc chunks with embeddings.

Schema (created by `bootstrap()`):

    CREATE SCHEMA IF NOT EXISTS chio_kb;

    CREATE TABLE chio_kb.code_chunks (
        id            BIGSERIAL PRIMARY KEY,
        file_path     TEXT NOT NULL,
        source_root   TEXT NOT NULL,
        language      TEXT NOT NULL,
        line_start    INTEGER NOT NULL,
        line_end      INTEGER NOT NULL,
        chunk_text    TEXT NOT NULL,
        embedding     vector(<dim>),
        properties    JSONB DEFAULT '{}',
        created_at    TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops);
    CREATE INDEX ... (file_path);

    chio_kb.doc_chunks: same shape, with `doc_type`, `title`, `section`
    instead of language/line columns. (Phase 1.3+ — schema-only stub today.)

The store is connection-injected: tests pass a Mock; production
constructs via from_url(). Statements use parameterized queries
exclusively — no string-formatted SQL — so the test seams that swap
the connection don't have to mock query parsing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class CodeChunk:
    file_path: str
    source_root: str
    language: str
    line_start: int
    line_end: int
    chunk_text: str
    properties: dict[str, Any]


class PostgresStore:
    """pgvector-backed code/doc chunk store.

    Construct with an injected connection (a `psycopg.Connection` in
    production; a `Mock` in tests). `bootstrap()` creates the schema and
    indexes idempotently. `insert_code_chunks()` accepts a list of
    CodeChunk + matching list of vectors.
    """

    def __init__(self, conn: Any, embedding_dim: int = 1536) -> None:
        self.conn = conn
        self.embedding_dim = embedding_dim

    @classmethod
    def from_url(cls, url: str, *, embedding_dim: int = 1536) -> "PostgresStore":
        """Open a real psycopg connection. Lazy SDK import so tests can run
        without psycopg installed.
        """
        try:
            import psycopg  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "psycopg not installed. `pip install psycopg[binary] pgvector`."
            ) from e
        conn = psycopg.connect(url, autocommit=True)
        try:
            from pgvector.psycopg import register_vector  # type: ignore

            register_vector(conn)
        except ImportError:
            # pgvector type adapter optional for tests; production install
            # has it via the dependency.
            pass
        return cls(conn, embedding_dim=embedding_dim)

    def bootstrap(self) -> None:
        """Create schema, table, and indexes. Idempotent (uses IF NOT EXISTS)."""
        with self.conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS chio_kb;")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS chio_kb.code_chunks (
                    id          BIGSERIAL PRIMARY KEY,
                    file_path   TEXT NOT NULL,
                    source_root TEXT NOT NULL,
                    language    TEXT NOT NULL,
                    line_start  INTEGER NOT NULL,
                    line_end    INTEGER NOT NULL,
                    chunk_text  TEXT NOT NULL,
                    embedding   vector({self.embedding_dim}),
                    properties  JSONB DEFAULT '{{}}'::jsonb,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path "
                "ON chio_kb.code_chunks (file_path);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_code_chunks_embedding "
                "ON chio_kb.code_chunks USING ivfflat "
                "(embedding vector_cosine_ops) WITH (lists = 100);"
            )

    def insert_code_chunks(
        self,
        chunks: Sequence[CodeChunk],
        embeddings: Sequence[list[float]],
    ) -> int:
        """Insert chunks with their embeddings. Returns the count inserted.

        Embeddings list MUST be parallel to chunks list (same length,
        same order). Vector dimensionality MUST match the constructor's
        `embedding_dim`.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) "
                f"must be the same length"
            )
        if not chunks:
            return 0

        with self.conn.cursor() as cur:
            for chunk, embedding in zip(chunks, embeddings):
                if len(embedding) != self.embedding_dim:
                    raise ValueError(
                        f"embedding dim {len(embedding)} != configured "
                        f"{self.embedding_dim}"
                    )
                cur.execute(
                    """
                    INSERT INTO chio_kb.code_chunks
                        (file_path, source_root, language, line_start,
                         line_end, chunk_text, embedding, properties)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk.file_path, chunk.source_root, chunk.language,
                        chunk.line_start, chunk.line_end, chunk.chunk_text,
                        embedding, json.dumps(chunk.properties),
                    ),
                )
        return len(chunks)

    def search_similar(
        self, query_vec: list[float], limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return top-k chunks by cosine similarity to query_vec."""
        if len(query_vec) != self.embedding_dim:
            raise ValueError(
                f"query_vec dim {len(query_vec)} != configured {self.embedding_dim}"
            )
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, file_path, source_root, language, line_start,
                       line_end, chunk_text, properties,
                       1 - (embedding <=> %s) AS similarity
                FROM chio_kb.code_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_vec, query_vec, limit),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def reset(self) -> None:
        """Drop and recreate the schema. Used by `make kb-reset`. Destructive."""
        with self.conn.cursor() as cur:
            cur.execute("DROP SCHEMA IF EXISTS chio_kb CASCADE;")
        self.bootstrap()

    def close(self) -> None:
        if hasattr(self.conn, "close"):
            self.conn.close()
