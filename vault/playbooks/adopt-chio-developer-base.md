---
id: playbooks.adopt-chio-developer-base
type: playbook
status: draft
owners: []
related-spec: []
related-receipts: []
last-validated: 2026-05-07
---

# Adopt chio-developer-base for your repo

> How a second team (platform / opus / alpha / …) brings up the chio-developer-base stack against their own repo. This playbook exists because [[../decisions/ADR-0001-repo-graduation|ADR-0001]]'s "graduate" outcome is gated on a real second adopter — *with working code*, not a verbal commit.

## Current readiness (v0.1.x)

Honest state of what's ready vs. rough at the time you read this. Update when the surfaces below mature.

| Surface | Ready | Notes |
| --- | --- | --- |
| `kb-engine` plugin contract (4 hooks + Registry) | ✓ | Protocols stable; tests cover dispatch + boundary |
| `chio-pack` as plugin (entry point) | ✓ | Loads via `Registry.load_entry_points()` |
| `chio-dev` CLI (`status`, `up`, `down`, `ingest`, `sync`, `query`, `session`, `eval`, `dogfood`, `migrate-seeds`) | ✓ | Click-based; lazy-imports backing-store deps |
| Engine ↔ pack boundary (CI-enforced) | ✓ | `ops/ci/check-imports.py` + AST unit test |
| Phase 0 outcome eval fixtures (38 total) | ✓ | All four evals fixture-complete |
| Phase 0 runners (4 modules) | ✓ scaffold | Return `blocked-input` until real input pipelines (Phase 1.5+ sessions, Phase 1.x KB stack); ADR-0002 baselines pending |
| `make kb-up` docker stack | ⚠ syntax-validated, not exercised in CI | Compose config validates; bringing it up needs a docker daemon |
| pgvector / Neo4j ingest | ⚠ wired with FakeEmbedder | `chio-dev ingest --no-postgres --no-neo4j` works without infra; full path needs OPENAI_API_KEY + live stack |
| Vault-sync daemon (frontmatter → DerivedRecords) | ⚠ one-shot works; watch mode lazy | `chio-dev sync` one-shot writes to JsonlRouter audit log; production GraphitiHttpRouter is Phase 1.4+ |
| `chio-kb-mcp` real gateway (10 `kb_*` tools) | ✗ stub only | Phase 1.3+ deliverable; today the docker container runs a /health stub |
| Federated cross-repo queries | ✗ explicitly out of scope for v1 | Per [PLAN.md](../../PLAN.md) "Non-goals" |

## When this playbook applies

You should adopt chio-developer-base when:

- You have a multi-repo or single-repo codebase with material Rust + docs / spec content.
- You'd benefit from retrieval-augmented context grounded in a property graph (capability-style or otherwise).
- You want signed-receipt-style provenance on agent retrievals (Phase 2B+).
- You're prepared to author a **schema pack** for your domain — chio-developer-base is intentionally Chio-shaped at the top, generic only at the engine layer.

You should NOT adopt if:

- Your repo is small enough that `grep` + an MCP code-search tool already covers the discoverability you need. (Honest first.)
- You're not prepared to staff a curator who keeps your vault non-stale.
- You expect to fork the engine. Don't fork; register a pack via `kb_engine.plugin` hooks.

## Pre-flight

- [ ] You can clone chio-developer-base and run `make kb-status` — all Phase 0 deps green.
- [ ] You have **uv** and **docker compose** locally.
- [ ] Your target repo has a stable layout (don't try to onboard during a major refactor).
- [ ] One human is named as the **pack owner** for your team.

## Step 1 — Decide: new pack, or sources-only adoption?

Two paths:

**1A. Sources-only.** Your domain maps cleanly onto chio-pack's existing schema (Capability, Receipt, Guard, Policy, Protocol, Standard). You only need to add your repo as a `source` and reuse chio-pack's schema. Cheaper. Pick this if you're a Chio-protocol consumer (an SDK peer, a guard plugin author).

**1B. New pack.** Your domain has its own concepts that don't fit Chio's schema. You'll author a `<your-team>-pack/` alongside `chio-pack/`. Required if your nodes / edges meaningfully differ. Recommended for large independent codebases (platform, opus, alpha as eventual examples).

Don't split the difference. Mixing your concepts into chio-pack pollutes the engine ↔ pack boundary the engine relies on.

## Step 2A — Sources-only adoption

> Skip to step 2B if you chose 1B.

The v0.1.x path doesn't yet have `sources.toml` — that's Phase 1.x indexing-pipeline config. Today the `chio-dev ingest` CLI takes a source-root argument directly:

```sh
chio-dev ingest /path/to/your-repo
chio-dev ingest /path/to/your-repo --no-postgres --no-neo4j   # dry-run, no infra
```

The CLI walks the repo, runs the Registry's `SourceIngester` hooks (currently chio-pack's Rust ingester only — your pack adds more in 2B), projects nodes/edges to Neo4j, and chunks code to pgvector. Output is JSON with `files_seen / files_ingested / nodes_upserted / edges_upserted / chunks_inserted`.

When `make kb-up` brings the docker stack live and `make kb-eval-retrieval` lands (Phase 1.x), confirm A-grade retrieval against your repo's content. If it drops below A, the issue is content gaps in your repo, not the engine.

## Step 2B — New-pack adoption

Copy chio-pack as a template:

```sh
cp -R chio-pack <your-team>-pack
cd <your-team>-pack
# update pyproject.toml: name, scripts, package
```

The four plugin protocols in [`kb_engine.plugin`](../../kb-engine/kb_engine/plugin.py) you implement:

| Hook | Signature | Reference (chio-pack) |
| ---- | --------- | --------------------- |
| `SourceIngester` | `(file_path) -> ParsedFile \| None` | [`chio_pack.plugin.rust_source_ingester`](../../chio-pack/chio_pack/plugin.py) |
| `GraphProjector` | `(parsed) -> Iterable[Node \| Edge]` | [`chio_pack.plugin.chio_graph_projector`](../../chio-pack/chio_pack/plugin.py) |
| `ToolRegistrar` | `(server) -> None` | [`chio_pack.plugin.chio_tool_registrar`](../../chio-pack/chio_pack/plugin.py) (stub today) |
| `FrontmatterHandler` | `(type, frontmatter) -> Iterable[DerivedRecord]` | [`chio_pack.plugin.chio_frontmatter_handler`](../../chio-pack/chio_pack/plugin.py) |

Define your **schema** in `<your-team>_pack/schema.py`. Match chio-pack's pattern — namespaced string labels and edge types as module constants:

```python
# Example for a hypothetical platform-pack:
SERVICE = "PlatformService"
DEPLOYMENT = "PlatformDeployment"

DEPLOYS = "DEPLOYS"
DEPENDS = "DEPENDS"
```

Then your projector emits `Node(label=SERVICE, ...)` and `Edge(relationship=DEPLOYS, ...)`.

Critical rule: **your labels and edges use your team's prefix** (`Platform*`, `Opus*`). Do not reuse `Chio*` labels even if a concept "feels similar." Namespacing keeps cross-pack queries possible without semantic collisions.

Wire your `register(registry)` entry point in `pyproject.toml`:

```toml
[project.entry-points."kb_engine.plugins"]
platform = "platform_pack.plugin"
```

Then `Registry.load_entry_points()` finds it automatically alongside chio-pack.

## Step 3 — Outcome evals for your pack

Copy `chio-pack/eval/PHASE-0.md` and adapt the four outcome evals to your domain:

- `time-to-first-correct-fix` — pick 8 historical bugs from your repo.
- `repeated-mistake-rate` — same harness, your session logs.
- `<domain>-harness-recall` — rename per your test harness (e.g., `platform-integration-recall`).
- `<domain>-error-explanation` — rename per your error class.

Targets are *yours to set*. The chio-developer-base targets aren't gospel; they're calibrated to Chio. Document your targets in your pack's `eval/PHASE-0.md` and an ADR.

## Step 4 — Vault layout

Your pack gets its own folder under `vault/<your-team>/` OR a separate vault directory entirely. Recommended: separate vault, joined by the daemon's federation layer (Phase 1+).

Required folders mirror chio-developer-base's seven (`spec/`, `decisions/`, `episodes/`, `playbooks/`, `daily/`, `crates/` or your equivalent, `_meta/`). Don't add an eighth without an ADR — the discipline travels with the pack.

## Step 5 — Run baseline evals

```sh
cd chio-developer-base
make kb-eval-outcomes  # runs both packs' outcome evals if registered
```

Both packs' outcome evals must run side-by-side. Your pack's targets are gated by your evals only; chio-pack's are gated by chio's. The retrieval eval is shared and must remain A overall.

## Step 6 — Iterate

The first 30 days will surface schema gaps, ranking biases, and stale notes. Plan for two ADRs in that window — one to refine your schema, one to document the staleness policy you converged on.

## What you owe the chio-developer-base maintainers

By adopting, you commit to:

- **Filing an ADR in your pack** before you change a plugin interface.
- **Reporting any retrieval-eval regression** caused by your pack to the chio-developer-base maintainer (so the engine isn't blamed for pack-level issues).
- **Showing up to the Phase 4 graduation review** (per [[../decisions/ADR-0001-repo-graduation|ADR-0001]]) with your two-repo coordination cost numbers and your outcome-eval trends.

Without these, your "second adopter" status is verbal and ADR-0001 will not credit it toward graduation.

## Anti-patterns

- **Forking the engine** instead of registering plugins. The boundary will rot in your fork; you'll merge-conflict forever; your pack will become a parallel project. Don't.
- **Adding `Chio*` nodes to your pack** because the concept feels similar. Add `<YourTeam>Capability` if you really need it; cross-pack relationships go in their own ADR.
- **Skipping outcome evals** because your team is small. Skipping them is how you discover, six months in, that you can't answer "is this helping?"
- **Putting raw source in your vault**. Same rule as chio-developer-base. Vault holds curated non-source knowledge only.

## References

- [[../PLAN.md|PLAN.md]] — engine/pack boundary contract
- [[../decisions/ADR-0000-charter|ADR-0000]] — original charter
- [[../decisions/ADR-0001-repo-graduation|ADR-0001]] — graduation criteria, where you fit in
- [[../chio-pack/eval/PHASE-0|chio-pack PHASE-0]] — template for your pack's outcome evals
