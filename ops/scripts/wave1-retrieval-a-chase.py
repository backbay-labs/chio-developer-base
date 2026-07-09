#!/usr/bin/env python3
"""Wave 1: exclusive truncate → OpenAI ingest → retrieval-A eval.

Runs ingest + eval in one process against the same Postgres handles so a
peer agent cannot TRUNCATE between the two steps.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    os.chdir(REPO / "chio-pack")
    sys.path.insert(0, str(REPO / "chio-pack"))
    sys.path.insert(0, str(REPO / "kb-engine"))

    from kb_engine import IngestPipeline, Registry
    from kb_engine.config import load_sources_toml
    from kb_engine.runtime import Runtime as EngineRuntime
    from kb_engine.store import Neo4jStore, OpenAIEmbedder, PostgresStore
    from chio_pack.eval.retrieval import run_retrieval_eval
    from chio_pack.runtime import ToolRuntime, set_runtime

    schema = os.environ.get("CHIO_KB_PACK_SCHEMA", "chio_kb")
    vault = Path(os.environ.get("CHIO_KB_VAULT_ROOT", REPO / "vault"))
    sources = load_sources_toml(REPO / "sources.toml")
    registry = Registry()
    n = registry.load_entry_points()
    print(f"plugins={n}", flush=True)

    pg = PostgresStore.from_url(os.environ["POSTGRES_URL"], schema=schema)
    pg.bootstrap()
    neo = Neo4jStore.from_url(
        os.environ["NEO4J_URI"],
        os.environ.get("NEO4J_USER", "neo4j"),
        os.environ.get("NEO4J_PASSWORD", "demodemo"),
    )
    emb = OpenAIEmbedder()
    print(f"embedder={type(emb).__name__}", flush=True)

    pipeline = IngestPipeline(registry, postgres=pg, neo4j=neo, embedder=emb)
    cfg = sources[0]
    print(f"ingest root={cfg.root} globs={len(cfg.glob)}", flush=True)
    stats = pipeline.ingest_tree(
        cfg.root, include_globs=cfg.glob, exclude_globs=cfg.exclude
    )
    print(
        json.dumps(
            {
                "files_seen": stats.files_seen,
                "files_ingested": stats.files_ingested,
                "chunks_inserted": stats.chunks_inserted,
            }
        ),
        flush=True,
    )

    engine_rt = EngineRuntime(
        registry=registry,
        postgres=pg,
        neo4j=neo,
        embedder=emb,
        vault_root=vault,
        pack_schema=schema,
    )
    set_runtime(ToolRuntime(handles=engine_rt, vault_root=vault))

    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(DISTINCT file_path) FROM chio_kb.doc_chunks"
        )
        docs = cur.fetchone()
        cur.execute(
            "SELECT count(*), count(DISTINCT file_path) FROM chio_kb.code_chunks"
        )
        code = cur.fetchone()
    print({"docs": docs, "code": code}, flush=True)
    if docs[1] < 20 or code[1] < 90:
        print("ERROR: corpus too small after ingest", flush=True)
        return 2

    report = run_retrieval_eval()
    out = Path("/tmp/retrieval-a-final.json")
    out.write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {"grade": report.get("grade"), "metrics": report.get("metrics")},
            indent=2,
        ),
        flush=True,
    )
    fails = [
        r
        for r in report.get("results", [])
        if r.get("p_at_k", 0) < 1 or r.get("mrr", 0) < 1
    ]
    print(f"imperfect {len(fails)}/{len(report.get('results', []))}", flush=True)
    for r in fails:
        print(
            f"  {r['id']} cat={r['category']} p={r['p_at_k']} mrr={r['mrr']}",
            flush=True,
        )
        print(f"    expected={r['expected']}", flush=True)
        print(f"    hits={r['hits'][:5]}", flush=True)
    return 0 if report.get("grade") == "A" else 1


if __name__ == "__main__":
    raise SystemExit(main())
