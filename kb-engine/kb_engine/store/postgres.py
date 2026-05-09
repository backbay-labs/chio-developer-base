"""pgvector backing store. Stores code chunks with embeddings.

Schema (created by `bootstrap()`):

    CREATE SCHEMA IF NOT EXISTS <schema>;

    CREATE TABLE <schema>.code_chunks (
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

The schema name is configurable so multiple packs (chio-pack, alexandria-pack,
opus-pack, …) can share a single Postgres database without colliding. The
default `chio_kb` keeps the Phase 1.1 stack working unchanged.

NOTE on doc_chunks: the doc_chunks table is not yet created; doc
indexing lands in Phase 1.x — see PLAN.md (M1 / T1.4 generic text
ingesters). The previous "schema-only stub today" comment described
a table that no `bootstrap()` call ever created and no insert path
ever populated — a phantom schema that the Skeptic's M0 audit
flagged as a silent-zero hazard. If a code path needs doc-chunk
storage before Phase 1.x lands, see `_doc_chunks_not_implemented`
below for the canonical fail-loud path.

The store is connection-injected: tests pass a Mock; production
constructs via from_url(). Statements use parameterized queries
exclusively — no string-formatted SQL — so the test seams that swap
the connection don't have to mock query parsing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import parse_qs, urlsplit, urlunsplit


# Schema names are configuration values, not user input — but they're
# interpolated into SQL by name (Postgres doesn't allow parameterizing
# schema identifiers). Validate strictly so a typo can never become a
# SQL-injection vector. The pattern matches Postgres' unquoted-identifier
# rules: lowercase ASCII letter or underscore, then more of the same plus
# digits. No mixed case, no dashes, no spaces, no leading digits.
_SCHEMA_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Default schema preserves Phase 1.1 behaviour. Existing data in `chio_kb`
# keeps working without any migration.
DEFAULT_SCHEMA = "chio_kb"


def _validate_schema(schema: str) -> str:
    """Validate a schema name; return the validated string.

    Raises ValueError with a clear message if the name doesn't match
    `^[a-z][a-z0-9_]*$`. This is a bouncer at the door so every other
    code path can format the schema into SQL without a second thought.
    """
    if not isinstance(schema, str):
        raise ValueError(
            f"schema must be a string, got {type(schema).__name__}"
        )
    if not _SCHEMA_NAME_RE.match(schema):
        raise ValueError(
            f"invalid schema name {schema!r}: must match "
            f"{_SCHEMA_NAME_RE.pattern} (lowercase letter or underscore, "
            f"then letters/digits/underscores)"
        )
    return schema


def _doc_chunks_not_implemented() -> None:
    """Fail-loud anchor for any future code path that needs doc-chunk
    storage before Phase 1.x lands. The previous design referenced a
    phantom `chio_kb.doc_chunks` table that was never created — a
    silent-zero hazard. Until M1 / T1.4 wires generic text ingesters
    and a real `doc_chunks` schema, callers must raise rather than
    no-op.
    """
    raise NotImplementedError(
        "doc_chunks table not yet bootstrapped — see PLAN.md Phase 1.x"
    )


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

    Multitenant story: every schema-qualified statement uses the
    `schema` argument passed at construction. Two PostgresStore
    instances pointed at the same connection but different schemas
    don't see each other's data — the M1-Multitenant requirement.
    """

    def __init__(
        self,
        conn: Any,
        embedding_dim: int = 1536,
        *,
        schema: str = DEFAULT_SCHEMA,
    ) -> None:
        self.conn = conn
        self.embedding_dim = embedding_dim
        # Validate up front: an invalid schema name should fail before
        # any SQL runs, not midway through bootstrap().
        self.schema = _validate_schema(schema)

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        embedding_dim: int = 1536,
        schema: str | None = None,
    ) -> "PostgresStore":
        """Open a real psycopg connection. Lazy SDK import so tests can run
        without psycopg installed.

        Schema resolution order (first wins):
          1. `schema=` keyword argument.
          2. `?schema=…` query parameter on the URL.
          3. DEFAULT_SCHEMA (`chio_kb`).

        If the URL carries a `schema=` query, it is stripped before
        being handed to psycopg — psycopg doesn't recognize it as a
        libpq parameter and would raise.
        """
        try:
            import psycopg  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "psycopg not installed. `pip install psycopg[binary] pgvector`."
            ) from e

        # Pull schema from the URL query if present, then strip it so
        # psycopg sees a clean URL.
        url_for_psycopg, schema_from_url = _split_schema_from_url(url)
        resolved_schema = schema or schema_from_url or DEFAULT_SCHEMA
        conn = psycopg.connect(url_for_psycopg, autocommit=True)
        try:
            from pgvector.psycopg import register_vector  # type: ignore

            register_vector(conn)
        except ImportError:
            # pgvector type adapter optional for tests; production install
            # has it via the dependency.
            pass
        return cls(conn, embedding_dim=embedding_dim, schema=resolved_schema)

    def bootstrap(self) -> None:
        """Create schema, table, and indexes. Idempotent (uses IF NOT EXISTS)."""
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {s};")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {s}.code_chunks (
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
                f"CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path "
                f"ON {s}.code_chunks (file_path);"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_code_chunks_embedding "
                f"ON {s}.code_chunks USING ivfflat "
                f"(embedding vector_cosine_ops) WITH (lists = 100);"
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

        s = self.schema
        with self.conn.cursor() as cur:
            for chunk, embedding in zip(chunks, embeddings):
                if len(embedding) != self.embedding_dim:
                    raise ValueError(
                        f"embedding dim {len(embedding)} != configured "
                        f"{self.embedding_dim}"
                    )
                cur.execute(
                    f"""
                    INSERT INTO {s}.code_chunks
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
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, file_path, source_root, language, line_start,
                       line_end, chunk_text, properties,
                       1 - (embedding <=> %s) AS similarity
                FROM {s}.code_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_vec, query_vec, limit),
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def reset(self) -> None:
        """Drop and recreate the schema. Used by `make kb-reset`. Destructive."""
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE;")
        self.bootstrap()

    def close(self) -> None:
        if hasattr(self.conn, "close"):
            self.conn.close()


def _split_schema_from_url(url: str) -> tuple[str, str | None]:
    """Pop a `schema=` query parameter off `url`. Return (clean_url, schema).

    If the URL has no `schema=` query, returns the original url and
    None. Multiple `schema=` values are not supported (use the kwarg).

    psycopg doesn't recognize `schema` as a libpq parameter, so leaving
    it in the URL would raise at connect time. We split it out cleanly
    here so the URL handed to psycopg.connect() is always libpq-valid.
    """
    parts = urlsplit(url)
    if not parts.query:
        return url, None
    qs = parse_qs(parts.query, keep_blank_values=True)
    if "schema" not in qs:
        return url, None
    schema_values = qs.pop("schema")
    schema = schema_values[0] if schema_values else None
    # Re-encode the query without `schema`. parse_qs returns lists; we
    # flatten back into a single ?k=v&k2=v2 string preserving order
    # is not strictly required for psycopg.
    new_query = "&".join(
        f"{k}={v}" for k, vs in qs.items() for v in vs
    )
    cleaned = urlunsplit((
        parts.scheme, parts.netloc, parts.path, new_query, parts.fragment,
    ))
    return cleaned, schema
