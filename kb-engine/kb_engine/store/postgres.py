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
    CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);
    CREATE INDEX ... (file_path);

    CREATE TABLE <schema>.doc_chunks (
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

The schema name is configurable so multiple packs (chio-pack, alexandria-pack,
opus-pack, …) can share a single Postgres database without colliding. The
default `chio_kb` keeps the Phase 1.1 stack working unchanged.

Wave 1 (Phase 1.3): ``doc_chunks`` is a real table with the same shape as
``code_chunks``. Markdown / prose ingest writes here; ``kb_search_docs``
queries it. The prior phantom-schema stub is gone.

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

from .vector import Filters, Hit, VectorRecord


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

    @property
    def dim(self) -> int:
        """VectorStore protocol alias for the configured embedding dimension."""
        return self.embedding_dim

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
        except (ImportError, TypeError, AttributeError):
            # pgvector adapter optional for unit tests that inject MagicMock
            # connections; production installs register against a real conn.
            # TypeError/AttributeError: mock conn is not a psycopg Connection.
            pass
        return cls(conn, embedding_dim=embedding_dim, schema=resolved_schema)

    def bootstrap(self) -> None:
        """Create schema, tables, and indexes. Idempotent (uses IF NOT EXISTS)."""
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {s};")
            for table in ("code_chunks", "doc_chunks"):
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {s}.{table} (
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
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_file_path "
                    f"ON {s}.{table} (file_path);"
                )
                # HNSW preferred over uncalibrated IVFFlat lists=100 (Wave 1).
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_embedding "
                    f"ON {s}.{table} USING hnsw "
                    f"(embedding vector_cosine_ops) "
                    f"WITH (m = 16, ef_construction = 64);"
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

    def insert_doc_chunks(
        self,
        chunks: Sequence[CodeChunk],
        embeddings: Sequence[list[float]],
    ) -> int:
        """Insert documentation chunks. Same contract as insert_code_chunks."""
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
                    INSERT INTO {s}.doc_chunks
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
        *, table: str = "code_chunks",
    ) -> list[dict[str, Any]]:
        """Return top-k chunks by cosine similarity to query_vec."""
        if table not in ("code_chunks", "doc_chunks"):
            raise ValueError(f"unsupported table {table!r}")
        if len(query_vec) != self.embedding_dim:
            raise ValueError(
                f"query_vec dim {len(query_vec)} != configured {self.embedding_dim}"
            )
        s = self.schema
        qvec = _as_pgvector(query_vec)
        with self.conn.cursor() as cur:
            # Deduplicate by file_path so re-ingest / multi-chunk files
            # don't crowd top-k with the same path (Wave 1 retrieval-A).
            cur.execute(
                f"""
                SELECT DISTINCT ON (file_path)
                       id, file_path, source_root, language, line_start,
                       line_end, chunk_text, properties,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {s}.{table}
                ORDER BY file_path, embedding <=> %s::vector
                """,
                (qvec, qvec),
            )
            rows = [dict(zip(
                [d[0] for d in cur.description] if cur.description else [],
                row,
            )) for row in cur.fetchall()]
        rows.sort(key=lambda r: float(r.get("similarity") or 0.0), reverse=True)
        return rows[:limit]

    def search_docs(
        self, query_vec: list[float], limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return top-k documentation chunks by cosine similarity."""
        return self.search_similar(query_vec, limit=limit, table="doc_chunks")

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert generic vector records into the pgvector chunk table.

        The existing table shape predates the generic VectorStore protocol.
        We map the protocol fields losslessly enough for retrieval:
        record id -> file_path, tenant -> source_root, text -> chunk_text.
        """
        chunks = [
            CodeChunk(
                file_path=record["id"],
                source_root=record["tenant"],
                language=str(record.get("properties", {}).get("language", "text")),
                line_start=int(record.get("properties", {}).get("line_start", 1)),
                line_end=int(record.get("properties", {}).get("line_end", 1)),
                chunk_text=record["text"],
                properties=dict(record.get("properties", {})),
            )
            for record in records
        ]
        embeddings = [record["embedding"] for record in records]
        self.insert_code_chunks(chunks, embeddings)

    def query(
        self,
        embedding: list[float],
        k: int,
        filters: Filters | None = None,
    ) -> list[Hit]:
        """Return VectorStore hits from the pgvector chunk table."""
        if len(embedding) != self.embedding_dim:
            raise ValueError(
                f"query_vec dim {len(embedding)} != configured {self.embedding_dim}"
            )
        filters = filters or {}
        where: list[str] = []
        params: list[Any] = []
        tenant = filters.get("tenant")
        if tenant:
            where.append("source_root = %s")
            params.append(tenant)
        properties = filters.get("properties")
        if properties:
            where.append("properties @> %s::jsonb")
            params.append(json.dumps(properties, sort_keys=True))
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        s = self.schema
        qvec = _as_pgvector(embedding)
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, file_path, source_root, language, line_start,
                       line_end, chunk_text, properties,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {s}.code_chunks
                {where_sql}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [qvec, *params, qvec, k],
            )
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return [
            {
                "id": str(row.get("file_path", row.get("id", ""))),
                "text": str(row.get("chunk_text", "")),
                "score": float(row.get("similarity", 0.0)),
                "tenant": str(row.get("source_root", "")),
                "properties": dict(row.get("properties") or {}),
            }
            for row in rows
        ]

    def snapshot_id(self) -> str:
        """Stable-ish snapshot cursor for retrieval receipts."""
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  (SELECT COUNT(*) FROM {s}.code_chunks) AS code_n,
                  (SELECT COUNT(*) FROM {s}.doc_chunks) AS doc_n,
                  (SELECT COALESCE(MAX(id), 0) FROM {s}.code_chunks) AS code_max,
                  (SELECT COALESCE(MAX(id), 0) FROM {s}.doc_chunks) AS doc_max
                """
            )
            row = cur.fetchone()
        if not row:
            return f"{s}:empty"
        return f"{s}:code={row[0]}:{row[2]}:doc={row[1]}:{row[3]}"

    def reset(self) -> None:
        """Drop and recreate the schema. Used by `make kb-reset`. Destructive."""
        s = self.schema
        with self.conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE;")
        self.bootstrap()

    def close(self) -> None:
        if hasattr(self.conn, "close"):
            self.conn.close()


def _as_pgvector(values: Sequence[float]) -> Any:
    """Adapt a float sequence for pgvector ``<=>`` / ``::vector`` binds.

    Prefer the ``pgvector.psycopg.Vector`` adapter when installed. Fall
    back to the literal ``[f1,f2,...]`` string form that Postgres accepts
    with an explicit ``::vector`` cast — bare Python lists bind as
    ``double precision[]`` and fail with ``operator does not exist``.
    """
    try:
        from pgvector.psycopg import Vector  # type: ignore

        return Vector(list(values))
    except ImportError:
        return "[" + ",".join(str(float(v)) for v in values) + "]"


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
