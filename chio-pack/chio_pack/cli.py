"""chio-dev CLI — Phase 1.5 developer wrapper.

Subcommands:

  status            print make kb-status
  up / down         start/stop the docker stack
  ingest [SRC]      run kb_engine.IngestPipeline against a source root
  query <Q>         retrieve top-K via pgvector similarity (Phase 1.3+)
  sync [VAULT]      run vault-sync daemon (one-shot by default; --watch for forever)
  migrate-seeds     convert arc PR #599 graphiti seeds → vault/episodes
  eval              shell: make kb-eval-outcomes
  dogfood           shell: make kb-dogfood
  session start     emit a `tool_call`/`edit`/`test_run`/`mistake` from CLI
  session show      print recent session log

Most subcommands either shell out to the relevant Makefile target OR
delegate to a Python module that already exists. The CLI's job is
discovery — `chio-dev --help` is the entrypoint a new dev finds before
they read PLAN.md.

Per AGENTS.md hard rules, every action that would write to Graphiti
goes through the vault-sync daemon. The CLI never bypasses that.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import click


REPO_ROOT_HINT = "Run from the chio-developer-base/ root (or set CHIO_DEV_REPO)."

# The Postgres schema chio-dev's `ingest`/`sync`/`query` subcommands write
# to. Per M1-Multitenant deliverable 3, the schema is configurable so a
# second pack on the same Postgres database doesn't collide. Default
# preserves Phase 1.1's behaviour: writes go to `chio_kb`.
DEFAULT_PACK_SCHEMA = "chio_kb"


def _resolve_pack_schema(flag_value: str | None) -> str:
    """Resolve the pack schema in priority order.

    1. The `--pack-schema` CLI flag, if set.
    2. The `CHIO_KB_PACK_SCHEMA` environment variable.
    3. The default (`chio_kb`).
    """
    if flag_value:
        return flag_value
    return os.environ.get("CHIO_KB_PACK_SCHEMA", DEFAULT_PACK_SCHEMA)


def _repo_root() -> Path:
    """Best-effort repo root detection. Walk up looking for PLAN.md + Makefile."""
    env = os.environ.get("CHIO_DEV_REPO")
    if env:
        return Path(env).resolve()
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        if (candidate / "PLAN.md").exists() and (candidate / "Makefile").exists():
            return candidate
    return here


def _shell(cmd: str | list[str], *, cwd: Path | None = None, check: bool = True) -> int:
    """Run a shell command; relay stdout/stderr to the user's terminal."""
    if isinstance(cmd, list):
        printable = " ".join(shlex.quote(c) for c in cmd)
    else:
        printable = cmd
    click.secho(f"$ {printable}", fg="blue", err=True)
    res = subprocess.run(
        cmd if isinstance(cmd, list) else cmd,
        shell=isinstance(cmd, str),
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    if check and res.returncode != 0:
        sys.exit(res.returncode)
    return res.returncode


@click.group()
@click.version_option()
def main() -> None:
    """chio-dev — Chio knowledge-base developer CLI.

    Repo-rooted at the directory containing PLAN.md + Makefile, or the
    path set in CHIO_DEV_REPO.
    """


# === Stack lifecycle ===


@main.command()
def status() -> None:
    """Run `make kb-status` to see what exists vs. what's expected."""
    _shell("make kb-status", cwd=_repo_root(), check=False)


@main.command()
def up() -> None:
    """Bring up the Phase 1.1+ docker stack (`make kb-up`)."""
    _shell("make kb-up", cwd=_repo_root())


@main.command()
def down() -> None:
    """Stop the docker stack (`make kb-down`)."""
    _shell("make kb-down", cwd=_repo_root(), check=False)


# === Eval / dogfood ===


@main.command()
def eval() -> None:
    """Run the outcome-eval suite (`make kb-eval-outcomes`)."""
    _shell("make kb-eval-outcomes", cwd=_repo_root(), check=False)


@main.command()
def dogfood() -> None:
    """Regenerate `DOGFOOD-REVIEW.md` (`make kb-dogfood`). Phase 1.x."""
    _shell("make kb-dogfood", cwd=_repo_root(), check=False)


# === Vault operations ===


@main.command()
@click.argument("seeds_dir", required=False)
@click.option("--vault", default="vault", help="Path to vault/ root (default: vault)")
@click.option("--branch", default="HEAD", help="Provenance label for imported_from")
def migrate_seeds(seeds_dir: str | None, vault: str, branch: str) -> None:
    """One-shot: convert arc PR #599 seeds/graphiti/*.json → vault/episodes/*.md.

    SEEDS_DIR defaults to ../arc/ops/knowledge-base/seeds/graphiti.
    """
    repo = _repo_root()
    seeds = seeds_dir or str(repo.parent / "arc" / "ops" / "knowledge-base" / "seeds" / "graphiti")
    cmd = [
        sys.executable, str(repo / "ops" / "scripts" / "migrate-seeds.py"),
        "--seeds", seeds,
        "--vault", str(repo / vault),
        "--branch", branch,
    ]
    _shell(cmd, cwd=repo, check=False)


@main.command()
@click.argument("vault_path", required=False)
@click.option("--watch", is_flag=True, help="Run forever (watchdog/polling).")
@click.option("--state", default=None, help="Path to sync state JSON (default: ~/.chio-dev/vault-sync.state.json)")
@click.option(
    "--pack-schema",
    default=None,
    help=(
        "Postgres schema for any direct pgvector writes from sync. "
        "Default: $CHIO_KB_PACK_SCHEMA or 'chio_kb'."
    ),
)
def sync(
    vault_path: str | None,
    watch: bool,
    state: str | None,
    pack_schema: str | None,
) -> None:
    """Run the vault-sync daemon. One-shot by default; --watch for forever.

    VAULT_PATH defaults to <repo>/vault.
    """
    repo = _repo_root()
    vault_root = Path(vault_path) if vault_path else repo / "vault"
    state_path = Path(state) if state else Path.home() / ".chio-dev" / "vault-sync.state.json"

    schema = _resolve_pack_schema(pack_schema)
    # Surface the schema even though today's sync routers don't yet use
    # PostgresStore directly — when they do (Phase 1.4+), the resolved
    # schema is already threaded through the CLI surface.
    click.secho(f"Pack schema: {schema}", fg="green", err=True)

    from kb_engine import Registry
    from kb_engine.sync import JsonlRouter, NullRouter, VaultSyncDaemon

    registry = Registry()
    n_loaded = registry.load_entry_points()
    click.secho(f"Loaded {n_loaded} plugin entry point(s).", fg="green", err=True)

    audit_path = repo / "vault" / "_meta" / "dashboards" / "vault-sync-audit.jsonl"
    routers = [JsonlRouter(audit_path), NullRouter()]

    daemon = VaultSyncDaemon(registry, routers, state_path=state_path)

    if watch:
        click.secho(f"Watching {vault_root} (Ctrl+C to stop)…", fg="yellow", err=True)
        daemon.run_forever(vault_root)
    else:
        stats = daemon.run_once(vault_root)
        click.echo(json.dumps(
            {
                "files_seen": stats.files_seen,
                "files_processed": stats.files_processed,
                "files_skipped_unchanged": stats.files_skipped_unchanged,
                "files_skipped_no_frontmatter": stats.files_skipped_no_frontmatter,
                "records_routed": stats.records_routed,
                "audit_log": str(audit_path),
            },
            indent=2,
        ))


@main.command()
@click.argument("source_root", required=False)
@click.option(
    "--sources",
    "sources_path",
    default=None,
    help="Path to a sources.toml describing one or more [[source]] entries. "
         "Falls back to ./sources.toml or <repo>/sources.toml when omitted.",
)
@click.option("--no-postgres", is_flag=True, help="Skip embedding/pgvector ingest")
@click.option("--no-neo4j", is_flag=True, help="Skip graph projection/neo4j")
@click.option(
    "--pack-schema",
    default=None,
    help=(
        "Postgres schema for this pack's data. Default: $CHIO_KB_PACK_SCHEMA "
        "or 'chio_kb'. Use a distinct value (e.g. 'alexandria_kb') to share "
        "one Postgres database across packs."
    ),
)
def ingest(
    source_root: str | None,
    sources_path: str | None,
    no_postgres: bool,
    no_neo4j: bool,
    pack_schema: str | None,
) -> None:
    """Run the ingest pipeline.

    Three modes (resolved in order):

      1. `--sources <path>`         — explicit sources.toml.
      2. `[SOURCE_ROOT]` positional — back-compat, single root, default pack.
      3. Auto-discovered sources.toml (./sources.toml, then <repo>/sources.toml).
      4. Final fallback: `<repo>/../arc` against the default pack.

    sources.toml lets a multi-pack adopter point distinct trees at
    distinct packs in one declarative file. See kb-engine docs for the
    schema.

    Phase 1.3+ wiring: requires Postgres + Neo4j up and configured via
    .env (or sets via flags). Without --no-postgres / --no-neo4j, the
    pipeline tries to connect using POSTGRES_URL / NEO4J_URI from env.
    """
    from kb_engine import IngestPipeline, Registry
    from kb_engine.config import (
        ConfigError,
        SourceConfig,
        default_sources_path,
        load_sources_toml,
    )

    repo = _repo_root()

    schema = _resolve_pack_schema(pack_schema)
    click.secho(f"Pack schema: {schema}", fg="green", err=True)

    registry = Registry()
    n_loaded = registry.load_entry_points()
    click.secho(f"Loaded {n_loaded} plugin entry point(s).", fg="green", err=True)

    # Resolve which mode we're in.
    sources: list[SourceConfig] = []
    explicit_sources_arg = sources_path is not None
    if explicit_sources_arg:
        chosen_path = Path(sources_path)
    elif source_root is None:
        # No positional given — try to auto-discover sources.toml.
        chosen_path = default_sources_path(Path.cwd(), repo)
    else:
        chosen_path = None

    if chosen_path is not None:
        try:
            sources = load_sources_toml(chosen_path)
        except ConfigError as e:
            click.secho(f"error: {e}", fg="red", err=True)
            sys.exit(2)
        click.secho(
            f"Loaded {len(sources)} source(s) from {chosen_path}.",
            fg="green",
            err=True,
        )
    else:
        # Fall back to single-root positional behavior.
        src = Path(source_root) if source_root else repo.parent / "arc"
        if not src.exists():
            click.secho(f"error: source root {src} does not exist", fg="red", err=True)
            sys.exit(2)
        sources = [SourceConfig(pack="<positional>", root=src)]

    postgres = None
    if not no_postgres:
        url = os.environ.get("POSTGRES_URL")
        if url:
            try:
                from kb_engine.store import PostgresStore
                postgres = PostgresStore.from_url(url, schema=schema)
                postgres.bootstrap()
            except RuntimeError as e:
                click.secho(f"warning: postgres unavailable: {e}", fg="yellow", err=True)

    neo4j_store = None
    if not no_neo4j:
        uri = os.environ.get("NEO4J_URI")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "demodemo")
        if uri:
            try:
                from kb_engine.store import Neo4jStore
                neo4j_store = Neo4jStore.from_url(uri, user, password)
            except RuntimeError as e:
                click.secho(f"warning: neo4j unavailable: {e}", fg="yellow", err=True)

    embedder = None
    if postgres:
        from kb_engine.store import FakeEmbedder, OpenAIEmbedder

        if os.environ.get("OPENAI_API_KEY"):
            embedder = OpenAIEmbedder()
            click.secho("Using OpenAI embedder.", fg="green", err=True)
        else:
            embedder = FakeEmbedder(dim=postgres.embedding_dim)
            click.secho(
                "OPENAI_API_KEY not set; using FakeEmbedder (deterministic, "
                "no semantic value). Real ingest needs OpenAI key.",
                fg="yellow", err=True,
            )

    pipeline = IngestPipeline(registry, postgres=postgres, neo4j=neo4j_store, embedder=embedder)

    n_constraints = pipeline.bootstrap()
    if n_constraints:
        click.secho(
            f"Applied {n_constraints} pack constraint spec(s) to Neo4j.",
            fg="green",
            err=True,
        )

    aggregate_files_seen = 0
    aggregate_files_ingested = 0
    aggregate_nodes = 0
    aggregate_edges = 0
    aggregate_chunks = 0
    per_source: list[dict] = []
    for cfg in sources:
        click.secho(
            f"Ingesting [{cfg.pack}] {cfg.root}…",
            fg="blue",
            err=True,
        )
        stats = pipeline.ingest_tree(
            cfg.root,
            include_globs=cfg.glob,
            exclude_globs=cfg.exclude,
        )
        aggregate_files_seen += stats.files_seen
        aggregate_files_ingested += stats.files_ingested
        aggregate_nodes += stats.nodes_upserted
        aggregate_edges += stats.edges_upserted
        aggregate_chunks += stats.chunks_inserted
        per_source.append(
            {
                "pack": cfg.pack,
                "root": str(cfg.root),
                "files_seen": stats.files_seen,
                "files_ingested": stats.files_ingested,
                "nodes_upserted": stats.nodes_upserted,
                "edges_upserted": stats.edges_upserted,
                "chunks_inserted": stats.chunks_inserted,
            }
        )
    click.echo(json.dumps(
        {
            "files_seen": aggregate_files_seen,
            "files_ingested": aggregate_files_ingested,
            "nodes_upserted": aggregate_nodes,
            "edges_upserted": aggregate_edges,
            "chunks_inserted": aggregate_chunks,
            "pack_schema": schema,
            "sources": per_source,
        },
        indent=2,
    ))


@main.command()
@click.argument("query")
@click.option("--limit", default=10)
@click.option(
    "--pack-schema",
    default=None,
    help=(
        "Postgres schema to query. Default: $CHIO_KB_PACK_SCHEMA or "
        "'chio_kb'. Must match the schema used at ingest time."
    ),
)
def query(query: str, limit: int, pack_schema: str | None) -> None:
    """Phase 1.3+ retrieval. Today, calls pgvector similarity search."""
    from kb_engine.store import OpenAIEmbedder, PostgresStore

    url = os.environ.get("POSTGRES_URL")
    if not url:
        click.secho("error: POSTGRES_URL not set", fg="red", err=True)
        sys.exit(2)
    if not os.environ.get("OPENAI_API_KEY"):
        click.secho("error: OPENAI_API_KEY not set (required to embed query)", fg="red", err=True)
        sys.exit(2)

    schema = _resolve_pack_schema(pack_schema)

    try:
        store = PostgresStore.from_url(url, schema=schema)
        embedder = OpenAIEmbedder()
        vec = embedder([query])[0]
        results = store.search_similar(vec, limit=limit)
        click.echo(json.dumps(results, indent=2, default=str))
    except RuntimeError as e:
        click.secho(f"error: {e}", fg="red", err=True)
        sys.exit(2)


# === Pack scaffolding ===


@main.command("init-pack")
@click.argument("name")
@click.option(
    "--path",
    "dest",
    default=".",
    show_default=True,
    help="Parent directory to create <name>-pack/ inside.",
)
def init_pack(name: str, dest: str) -> None:
    """Scaffold a new kb-engine plugin pack at <PATH>/<NAME>-pack/.

    NAME must match `^[a-z][a-z0-9_]*$` (lowercase, underscore allowed,
    must start with a letter — same rule W2-Multitenant uses for schema
    namespaces).

    The created pack is registrable as-is: stubs for the four protocols
    (SourceIngester, GraphProjector, ToolRegistrar, FrontmatterHandler)
    return sensible defaults so `Registry().load_entry_points()` finds
    the pack without any hand-written code first. Each stub carries a
    `# TODO(<name>-pack):` comment marking the next decision.

    Refuses to overwrite an existing directory (exit 2).
    """
    from chio_pack.scaffold import ScaffoldError, scaffold_pack

    dest_path = Path(dest)
    try:
        pack_dir = scaffold_pack(name, dest_path)
    except ScaffoldError as e:
        click.secho(f"error: {e}", fg="red", err=True)
        sys.exit(2)
    click.secho(f"created {pack_dir}", fg="green", err=True)
    click.echo(str(pack_dir))



@main.command('verify')
@click.argument('response_json', type=click.Path(exists=True, dir_okay=False, path_type=Path))
def verify_cmd(response_json: Path) -> None:
    """Verify a signed retrieval response (Wave 4 / Phase 2B)."""
    from kb_engine.receipt import verify_response

    payload = json.loads(response_json.read_text(encoding='utf-8'))
    ok, reason = verify_response(payload)
    if ok:
        click.secho('✓ receipt verified', fg='green')
        sys.exit(0)
    click.secho(f'✗ verification failed: {reason}', fg='red', err=True)
    sys.exit(1)


@main.command('retrieval-eval')
@click.option('--fail-below-a', is_flag=True)
@click.option('--fixtures', 'fixtures_dir', default=None)
def retrieval_eval_cmd(fail_below_a: bool, fixtures_dir: str | None) -> None:
    """Run retrieval fixtures against the live tool runtime."""
    from chio_pack.eval.retrieval import run_retrieval_eval

    fixtures = Path(fixtures_dir) if fixtures_dir else None
    report = run_retrieval_eval(fixtures_dir=fixtures, fail_below_a=fail_below_a)
    click.echo(json.dumps(report, indent=2))
    if fail_below_a and report.get('grade') != 'A':
        sys.exit(1)


# === Session log ===


@main.group()
def session() -> None:
    """Manage chio-dev session logs (~/.chio-dev/sessions/*.jsonl).

    Sessions are the input to the repeated-mistake-rate eval (Eval 2).
    """


@session.command("show")
def session_show() -> None:
    """Print the current session's path and last 20 events."""
    from chio_pack.eval import session_log

    path = session_log.session_path()
    click.echo(str(path))
    if path.exists():
        events = session_log.load_session(path)[-20:]
        for ev in events:
            click.echo(json.dumps(ev))


@session.command("tool-call")
@click.option("--tool", required=True)
@click.option("--args", default="{}")
@click.option("--result-ids", default="")
def session_tool_call(tool: str, args: str, result_ids: str) -> None:
    """Manually record a tool_call event (mostly for testing the harness)."""
    from chio_pack.eval import session_log

    parsed_args = json.loads(args) if args else {}
    rids = [s for s in result_ids.split(",") if s]
    session_log.tool_call(tool=tool, args=parsed_args, result_ids=rids)
    click.secho(f"Recorded tool_call: {tool}", fg="green", err=True)


if __name__ == "__main__":
    main()
