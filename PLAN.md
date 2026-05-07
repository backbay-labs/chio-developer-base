# Chio Developer Base — Plan

A standalone repo that carves out, expands, and **dogfoods** Chio's knowledge base. Origin: arc PR #599 (`codex/chio-kb-a-grade-dogfood`).

## TL;DR

Three layers, one canonical authoring surface, two ambitious bets, five phases.

- **`kb-engine/`** — generic retrieval / graph / MCP framework. Zero Chio knowledge.
- **`chio-pack/`** — Chio schema, the 10 `kb_*` tools, evals, episode seeds.
- **`vault/`** — git-versioned markdown that **is** the canonical store for episodes, ADRs, briefs, playbooks. Obsidian renders it; agents read it as files; Graphiti is derived from it, not the other way around.
- **PR-time `kb_impact` gate** — fail PRs that touch guards/policies/protocol contracts without acknowledging the downstream blast radius.
- **Self-evidencing retrieval** — every `kb_search_*` returns a signed mini-receipt. The KB becomes a Chio reference implementation.

Phase 0 is *evals*, not code. ~10 weeks total to a v1 we'd defend.

---

## Goals

1. Migrate the current PR #599 stack into `chio-developer-base` without regressing the A-grade retrieval eval (22/22, p@5 ≥ 0.99, MRR ≥ 0.97).
2. Make the vault a first-class authoring surface for humans and agents without duplicating source code.
3. Add evals that measure *outcomes* — time-to-fix, repeated-mistake rate, conformance recall, capability-error explanation quality — not just retrieval p@5.
4. Ship two Chio-specific features that earn their complexity: PR-time impact gate, signed retrieval.
5. Keep the engine/pack boundary enforceable so platform / opus / alpha can adopt without forking.

## Non-goals (v1)

- Cross-repo federation. One stack, one Postgres, one Neo4j, namespaced labels. Revisit when there's a second adopter.
- Auto-generated ADRs from agent runs. Decision text stays human-authored.
- A 3D crate-graph fly-through. The counterfactual query does the same cognitive work in 2D.
- A custom `chio-mcp-bridge` Obsidian plugin. Defer until Obsidian ships official MCP.
- A persistent "Cap" resident agent. Reconsider after signed retrieval ships.

---

## Architecture

```
                     vault/                          arc/  platform/  opus/
                  (markdown + frontmatter,           (raw source, indexed
                   human + agent authored,            read-only via path
                   git-versioned, IS canonical)       references)
                       │                                       │
            ┌──────────┴──────────┐                            │
            │  vault-sync daemon  │                            │
            │  (chokidar + git)   │                            │
            └──┬─────────┬────────┘                            │
               │         │                                     │
   ┌───────────▼──┐  ┌───▼──────────────┐  ┌──────────────────▼──────────┐
   │  Graphiti    │  │  Doc indexer     │  │  Code indexer                │
   │  (derived)   │  │  (pgvector)      │  │  (pgvector + tree-sitter →   │
   │              │  │                  │  │   Neo4j property graph)      │
   └───────┬──────┘  └────────┬─────────┘  └─────────────┬────────────────┘
           │                  │                           │
           └──────────────────┴────────────┬──────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │   chio-kb MCP gateway   │
                              │   :8111                 │
                              │                         │
                              │  kb_search_*            │
                              │  kb_neighbors           │
                              │  kb_context / kb_impact │
                              │  kb_brief_feature       │
                              │  kb_add_episode ───────►│ writes vault note,
                              │  kb_eval                │ daemon syncs to graphiti
                              │                         │
                              │  All responses wrapped  │
                              │  in signed receipt      │
                              │  (Phase 2 moonshot)     │
                              └─────────────────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │  Consumers              │
                              │  - CLI: chio-dev        │
                              │  - GitHub Action: PR    │
                              │    impact gate          │
                              │  - Obsidian (renders    │
                              │    vault + plugins)     │
                              │  - Cursor / Claude Code │
                              │    via MCP              │
                              └─────────────────────────┘
```

**Inversion that makes it tractable:** the vault is the only place curated knowledge is *authored*. `seeds/graphiti/*.json` from PR #599 is migrated to `vault/episodes/*.md` with YAML frontmatter. The vault-sync daemon is the only writer to Graphiti. Graphiti and Neo4j become derived indices that can always be rebuilt from `vault/` + the source repos.

---

## Repo layout

```
chio-developer-base/
├── PLAN.md                          ← this file
├── README.md                        ← user-facing quickstart
├── AGENTS.md                        ← agent-facing: where to look, what's authoritative
├── CLAUDE.md                        ← Claude Code instructions
├── Makefile                         ← kb-up / kb-update / kb-eval / kb-dogfood / kb-bench
├── docker-compose.yml
├── .env.example
│
├── kb-engine/                       ← generic, zero Chio knowledge
│   ├── pyproject.toml
│   ├── kb_engine/
│   │   ├── __init__.py
│   │   ├── ingest/                  ← CocoIndex hooks, source watchers
│   │   │   ├── code.py
│   │   │   ├── docs.py
│   │   │   └── vault.py             ← parses frontmatter, emits both pgvector + graphiti episodes
│   │   ├── graph/                   ← Neo4j projector framework (schema-pack pluggable)
│   │   ├── search/                  ← ranker, filters, rank_components emission
│   │   ├── mcp/                     ← MCP server framework, tool registrar
│   │   ├── receipt/                 ← signed-retrieval envelope (Phase 2)
│   │   └── plugin.py                ← four hook types (see "Plugin seams" below)
│   └── tests/
│
├── chio-pack/                       ← all Chio-specific code
│   ├── pyproject.toml
│   ├── chio_pack/
│   │   ├── __init__.py
│   │   ├── schema.py                ← ChioCapability, ChioReceipt, ChioGuard, … node + edge defs
│   │   ├── projectors/              ← Rust tree-sitter → ChioSymbol/ChioCrate/CALLS edges
│   │   ├── tools/                   ← the 10 kb_* MCP tools, registered via plugin.py
│   │   │   ├── search_code.py
│   │   │   ├── search_docs.py
│   │   │   ├── neighbors.py
│   │   │   ├── context.py
│   │   │   ├── impact.py
│   │   │   ├── brief_feature.py
│   │   │   ├── eval_tool.py
│   │   │   └── add_episode.py
│   │   ├── eval/
│   │   │   ├── retrieval.yml        ← migrated from PR #599 eval/queries.yml
│   │   │   ├── outcomes.yml         ← NEW: time-to-fix, repeated-mistake, conformance-recall
│   │   │   └── runner.py
│   │   └── frontmatter.py           ← Chio-specific vault note types and validators
│   └── tests/
│
├── chio-pr-gate/                    ← Phase 2 moonshot #1
│   ├── action.yml                   ← GitHub Action entrypoint
│   ├── src/
│   │   └── gate.py                  ← runs kb_impact + kb_brief_feature on diff, posts PR comment
│   └── README.md
│
├── vault/                           ← canonical knowledge store
│   ├── _meta/
│   │   ├── templates/
│   │   │   ├── daily-note.md
│   │   │   ├── adr.md
│   │   │   ├── episode.md
│   │   │   └── spec.md
│   │   ├── queries/                 ← shipped Dataview queries
│   │   │   ├── stale-specs.md
│   │   │   ├── open-adrs.md
│   │   │   └── unowned-capabilities.md
│   │   └── plugin-config/           ← Obsidian community-plugin allowlist + settings
│   ├── spec/                        ← one file per Chio concept (capability, receipt, guard, …)
│   ├── crates/                      ← one MOC per Rust crate, auto-stubbed by ingest
│   ├── decisions/                   ← ADRs, numbered, immutable once Accepted
│   ├── episodes/                    ← Graphiti episode candidates + promoted episodes
│   ├── playbooks/                   ← runbooks: revoke a capability, ship a release, debug a guard
│   └── daily/                       ← YYYY-MM-DD daily notes
│
│   (per [ADR-0003](decisions/ADR-0003-vault-layout.md), `.obsidian/`
│    lives at the repo root, not under vault/. The vault root IS the
│    repo root. The folder named `vault/` is historical — it holds
│    curated knowledge but is no longer the Obsidian vault root.)
│
├── infra/
│   ├── postgres/init/001-vector.sql
│   ├── neo4j/                       ← seeded constraints + indexes for Chio* labels
│   └── graphiti/config.yaml
│
└── ops/
    ├── ci/                          ← engine-pack import boundary check, eval gate, smoke
    ├── bench/                       ← retrieval latency + memory benchmarks
    └── scripts/
        ├── migrate-seeds.py         ← seeds/graphiti/*.json → vault/episodes/*.md (one-shot)
        └── chio-dev                 ← single-binary CLI: up / ingest / query / eval
```

---

## Vault layout

Seven top-level folders. Adding an eighth requires an ADR.

| Folder         | Purpose                                                  | Authored by    |
| -------------- | -------------------------------------------------------- | -------------- |
| `_meta/`       | templates, Dataview queries, plugin config               | humans         |
| `spec/`        | normative protocol notes, one per concept                | humans         |
| `crates/`      | one MOC per Rust crate                                   | ingest stubs + humans |
| `decisions/`   | ADRs, numbered, immutable once Accepted                  | humans         |
| `episodes/`    | Graphiti episode candidates + promoted episodes          | humans + agents |
| `playbooks/`   | "how to ship X" runbooks                                 | humans         |
| `daily/`       | daily notes, mostly throwaway, source of episodes        | humans + agents |

### Frontmatter schema (canonical)

Every vault note carries frontmatter validated by `chio_pack/frontmatter.py`. The schema is the contract with Graphiti and Neo4j.

```yaml
---
id: spec.capability.revocation        # stable, becomes graph node key
type: spec                            # spec | adr | episode | playbook | crate-moc | daily
status: accepted                      # draft | proposed | accepted | superseded
chio-node: Capability                 # which Chio* label this maps to (if any)
crate: chio-core                      # which crate (if structural)
supersedes: []                        # list of ids
related-receipts: [receipt.revoke-v1]
related-guards: [guard.revocation-window]
graphiti-episode: ep-2026-03-12-revocation-semantics
owners: [@aria, @connor]
last-validated: 2026-04-30
---
```

**Frontmatter is the contract.** The vault-sync daemon parses it, derives the graphiti episode (if `type` warrants), upserts the Neo4j node by `id`, and links into `chio_pack/schema.py` types. Bad frontmatter fails CI.

### Example: `vault/spec/capability-revocation.md`

```markdown
---
id: spec.capability.revocation
type: spec
status: accepted
chio-node: Capability
crate: chio-core
supersedes: []
related-receipts: [receipt.revoke-v1]
related-guards: [guard.revocation-window]
graphiti-episode: ep-2026-03-12-revocation-semantics
owners: [@aria, @connor]
last-validated: 2026-04-30
---

# Capability Revocation

## Normative
A capability MUST be revocable by its issuer within the revocation window
defined in [[decisions/ADR-0042-revocation-window]].

## Implements
- `chio-core::cap::revoke` — see [[crates/chio-core#revoke]]
- Conformance: [[playbooks/conformance-revocation]]

## Open questions
- [ ] Cross-issuer revocation? See [[episodes/ep-2026-04-01-cross-issuer]]

## Graph context
%% kb_neighbors: spec.capability.revocation depth=2 %%
```

The `%% kb_neighbors %%` block is interpreted by the Obsidian plugin (Phase 3) as a live MCP call. Cursor/agents see it as a code comment and can resolve it via the same MCP gateway.

### Default plugins (Phase 3)

Pinned via `obsidian/community-plugins.json`. Anything not on this list is rejected by CI.

**Ship**: Dataview, Templater, Obsidian Git, Excalidraw, Tasks, Periodic Notes, Iconize, Style Settings (one theme, no bikeshedding).

**Skip and document why**: Smart Connections (collides with pgvector), Canvas (Excalidraw exports cleaner), Kanban (overlap with Tasks + issue tracker), Advanced Tables (fights Templater).

**Custom plugins to build (Phase 3)**: `episode-promoter` only. `chio-mcp-bridge` deferred until Obsidian's official MCP support lands.

---

## The kb-engine ↔ chio-pack boundary

The line that will rot first if uncontested. Enforced by:

1. **Import-rule CI check** (`ops/ci/check-imports.py`): fails if `kb_engine/` imports anything `chio_*`. Runs on every PR.
2. **Plugin seams** in `kb_engine/plugin.py`. A pack registers any subset of:
   - `SourceIngester(file_path) -> Optional[ParsedFile]`
   - `GraphProjector(parsed) -> Iterable[NodeOrEdge]`
   - `ToolRegistrar(server) -> None` (declares MCP tools)
   - `FrontmatterHandler(type, frontmatter) -> Iterable[DerivedRecord]`
3. **No domain leak in eval categories**. The 9 PR #599 eval categories move into `chio_pack/eval/retrieval.yml`. `kb_engine` ships only synthetic fixtures.
4. **Schema packs are config + Python module**. `chio_pack/schema.py` declares labels and edges as data; engine reads it at startup.

---

## The two moonshots

### Moonshot 1 — PR-time `kb_impact` gate

**Pitch.** A GitHub Action that runs `kb_impact` and `kb_brief_feature` on every PR's diff and **fails the check** if downstream guards, conformance tests, or policy compilers depend on the changed contract without being acknowledged in the PR body.

**Why Chio-specific.** Chio's failure mode is contract drift across the protocol/standards split. The graph already encodes this. Not using it at PR time is malpractice.

**MVP shape.**
```
diff → changed files
     → kb_impact(file) for each high-risk file
     → kb_brief_feature(symbol_or_path) per impacted contract
     → render PR comment with: impacted suites, missing-test list, suggested ADRs
     → check run pass/fail based on:
         - any GUARDS/IMPLEMENTS edge crossed without test mention
         - any CANONICAL_DOC node touched without `last-validated` bump
```

**Eval.** Backtest against the last 50 merged Chio PRs. Did the gate fire on PRs that later required a follow-up fix? Target: precision ≥ 0.7, recall ≥ 0.8 on "PRs that needed a follow-up within 14 days."

### Moonshot 2 — Self-evidencing retrieval

**Pitch.** Every `kb_search_*` response is wrapped in a signed mini-receipt: which embeddings were consulted, which graph edges traversed, which temporal cutoff applied, signed by the gateway's Chio capability. Cursor/Obsidian show a verifiable green checkmark next to citations.

**Why Chio-specific.** This is literally the protocol applied to itself. The KB becomes a conformance test for Chio. If we can't sign our own retrievals, we can't ask anyone else to sign theirs.

**MVP shape.**
```python
# kb_engine/receipt/envelope.py
@dataclass
class RetrievalReceipt:
    query_hash: str
    tools_invoked: list[str]
    embeddings_index_version: str
    graph_snapshot_id: str
    temporal_cutoff: datetime
    rank_components: dict
    signed_at: datetime
    signature: bytes  # Chio capability signature

def wrap(response, gateway_capability) -> SignedResponse: ...
```

**Eval.** A new eval category `signed-retrieval` in `chio_pack/eval/outcomes.yml`. Every fixture must produce a verifiable receipt. Receipt verification uses Chio's own `chio-receipts` crate — if the format ever drifts, the eval breaks.

---

## Eval suite

### Retained from PR #599 (`chio_pack/eval/retrieval.yml`)

9 categories, 22 fixtures, target overall A. Hard regression gate — no new feature ships if this drops below A.

| Category                      | Target |
| ----------------------------- | ------ |
| code-retrieval                | A      |
| docs-retrieval                | A      |
| docs-spec-retrieval           | A      |
| feature-brief                 | A      |
| graph-and-bridge              | A      |
| graph-navigation-impact       | A      |
| graphiti-memory               | A      |
| operations                    | A      |
| test-discovery                | A      |

### New (`chio_pack/eval/outcomes.yml`)

These exist to gate the carve-out's value, not just retrieval quality.

| Category                          | Definition                                                                                       | Phase 0 baseline | Target |
| --------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------- | ------ |
| `time-to-first-correct-fix`       | Agent given a fixture Chio bug; wall-clock + tool-call count to a passing test.                  | TBD              | -30%   |
| `repeated-mistake-rate`           | Across rolling 50 sessions, fraction of mistakes the KB had documented.                          | TBD              | < 0.1  |
| `conformance-harness-recall`      | When a JS/Py SDK conformance test fails, does retrieval surface canonical fix in top-3?          | TBD              | ≥ 0.85 |
| `capability-error-explanation`    | Human-rated 1–5 on whether retrieval-augmented Chio capability errors reduce confusion.          | TBD              | ≥ 4.0  |
| `signed-retrieval`                | Every response carries a verifiable receipt. (Binary: 100% or fail.)                             | n/a              | 1.0    |
| `pr-impact-gate-precision-recall` | Gate fires on PRs that needed follow-up within 14 days.                                          | TBD              | P 0.7 / R 0.8 |

`make kb-eval` runs both files. CI gates on overall A on retrieval AND non-regression on outcomes.

---

## Phased delivery

### Phase 0 — Evals first (1 week)

**Premise:** if you can't measure the carve-out's value, you can't defend it. Build measurement before features.

| # | Task | Done when |
|---|------|-----------|
| 0.1 | Define `time-to-first-correct-fix` harness: fixture bugs, agent runner, scoring | `make kb-eval-outcomes` runs, prints baseline |
| 0.2 | Define `repeated-mistake-rate`: session log format, mistake classifier | Baseline measured against arc PR history |
| 0.3 | Define `conformance-harness-recall`: 20 historical conformance failures + canonical fixes | Top-3 recall measured |
| 0.4 | Define `capability-error-explanation`: 10 capability error scenarios + human rubric | Rubric documented in `chio_pack/eval/rubrics.md` |
| 0.5 | CI: `make kb-eval` gates the repo on retrieval-A AND outcomes-baseline-non-regression | `kb-eval` red on intentional regression in `make test-regression` |

**Acceptance:** every claim made in later phases is testable against this harness.

### Phase 1 — Carve-out + vault as canonical (2 weeks)

| # | Task | Done when |
|---|------|-----------|
| 1.1 | Move `arc/ops/knowledge-base/` → `chio-developer-base/{kb-engine,chio-pack,infra,ops}` per layout | `make kb-up && make kb-eval` green from fresh clone |
| 1.2 | Implement `kb_engine.plugin` hooks; refactor PR #599 code into pack registrations | Import-rule CI check green |
| 1.3 | Migrate `seeds/graphiti/*.json` → `vault/episodes/*.md` via `ops/scripts/migrate-seeds.py`, idempotent | `make kb-reseed` rebuilds Graphiti to byte-identical episode set |
| 1.4 | Build vault-sync daemon (chokidar + git + frontmatter parser); only writer to Graphiti | `kb_add_episode` round-trips through vault file |
| 1.5 | `chio-dev` CLI: `up`, `ingest`, `query`, `eval`, `dogfood` | One-binary install, 10-minute fresh-laptop onboarding |
| 1.6 | `arc/ops/knowledge-base/` deleted from arc, replaced by submodule or thin Make wrapper | arc CI still green; arc devs use `chio-dev` |

**Acceptance:** retrieval eval ≥ A. Outcomes evals at baseline (set in Phase 0). Fresh-clone-to-working ≤ 10 min.

### Phase 2 — The two moonshots (4 weeks, parallel)

#### 2A — PR-time `kb_impact` gate (3 weeks)

| # | Task | Done when |
|---|------|-----------|
| 2A.1 | `chio-pr-gate/` GitHub Action skeleton, runs on PR | Action posts a "hello" comment on a test PR |
| 2A.2 | Diff → impacted-contract resolver using `kb_impact` + `kb_brief_feature` | Comment lists impacted guards/policies/tests |
| 2A.3 | Pass/fail policy: GUARDS/IMPLEMENTS edges, CANONICAL_DOC freshness | Failing PR turns the check red |
| 2A.4 | Backtest against last 50 arc PRs | `pr-impact-gate-precision-recall` ≥ 0.7 / 0.8 |
| 2A.5 | Document escape-hatch: `kb-gate: ack` PR-body marker | Marker recognized; ack reasoning required |

#### 2B — Self-evidencing retrieval (3 weeks)

| # | Task | Done when |
|---|------|-----------|
| 2B.1 | `kb_engine/receipt/envelope.py`: `RetrievalReceipt` type + signing | Unit tests pass |
| 2B.2 | Wire into MCP gateway: every response wrapped | `signed-retrieval` eval = 1.0 |
| 2B.3 | Verifier in `chio_pack/tools/verify_retrieval.py` using `chio-receipts` crate (via PyO3 or shell) | `chio-dev verify <response>` returns ✓ |
| 2B.4 | Index/snapshot version emission: pgvector index version, Neo4j snapshot id | Receipts contain reproducible cursors |
| 2B.5 | Capability for the gateway: scoped grant `kb.read.*`, `episodes.write.dev_notes` | Capability minted; gateway boots only with it |

**Acceptance:** retrieval eval ≥ A. Both moonshot evals green. Gate runs on every chio-developer-base PR (dogfood).

### Phase 3 — Vault UX layer (2 weeks)

| # | Task | Done when |
|---|------|-----------|
| 3.1 | `.obsidian/community-plugins.json` pinned set: Dataview, Templater, Obsidian Git, Excalidraw, Tasks, Periodic Notes, Iconize, Style Settings | Allowlist enforced by CI |
| 3.2 | Templates: daily-note, ADR, episode, spec | `Cmd+P > Templater: insert` produces valid frontmatter |
| 3.3 | Dataview queries: stale-specs (`last-validated > 90d`), open-ADRs, unowned-capabilities | Each renders correctly on real vault content |
| 3.4 | Three Excalidraw diagrams, committed: capability lifecycle, receipt commitment chain, release qualification flow | Linked from `_meta/diagrams.md` |
| 3.5 | `episode-promoter` plugin (custom): daily-note → episode promotion with confirmation modal | Promotion writes `vault/episodes/<id>.md` and triggers daemon |
| 3.6 | `kb-gate: ack` writeable from Obsidian via `episode-promoter` | One-click ack from a daily note |

**Acceptance:** dev opens Obsidian on a fresh checkout and the daily-note flow works without manual setup.

### Phase 4 — Stabilize & decide on graduation (1 week)

| # | Task | Done when |
|---|------|-----------|
| 4.1 | Bench: retrieval p95 < 1.5s, gate latency < 30s on a 200-file PR | `make kb-bench` green |
| 4.2 | 30-day eval rolling history; alert on regression | Dashboard in `vault/_meta/dashboards/eval.md` |
| 4.3 | Decide: graduate to fully separate repo, or keep submodule wiring with arc | Decision recorded in `decisions/ADR-0001-repo-graduation.md` |
| 4.4 | Document second-adopter playbook (platform / opus / alpha) | `playbooks/adopt-chio-developer-base.md` |

**Acceptance:** the carve-out is defensible to a second adopter or rolled back to an arc submodule with no lost work.

---

## Make targets (final)

```
make kb-up            # docker compose up -d, wait for health
make kb-down
make kb-reset         # drop tables, clear neo4j chio* nodes, clear cocoindex state
make kb-reseed        # reset → ingest → derive graphiti from vault
make kb-update        # incremental cocoindex catch-up + vault re-derive
make kb-live          # cocoindex live mode + vault file watch
make kb-status
make kb-smoke
make kb-eval          # retrieval + outcomes
make kb-eval-outcomes # outcomes only (faster)
make kb-dogfood       # regenerate DOGFOOD-REVIEW.md
make kb-bench         # latency + memory + gate-on-pr-200-files
make kb-verify        # verify a retrieval receipt
make kb-gate-backtest # backtest PR gate on last N PRs
```

---

## Open decisions / risks

1. **Repo split timing.** This plan commits to standalone-repo from day one. The skeptic argument for incubating inside `arc/ops/knowledge-base/` until a second adopter exists is real and worth revisiting at Phase 4. Cost of two-repo coordination ≈ 4–8 hr/mo for a single maintainer; revisit if no second adopter signs up by week 10. Recorded as ADR-0001.
2. **Graphiti as derived store.** The inversion (vault → graphiti, not graphiti → vault) is the load-bearing decision. If the daemon's idempotency or ordering breaks under high-write conditions, fall back to dual-write with reconciliation. Mitigation: every episode has a content hash; daemon refuses to overwrite a hash mismatch without `--force`.
3. **Outcome-eval baselines are subjective.** Especially `capability-error-explanation`. Plan: 3 human raters, average; flag any rubric disagreement > 1 point. Re-evaluate rubric quarterly.
4. **Obsidian plugin breakage.** Pin Obsidian version in `obsidian/community-plugins.json` and CI on Obsidian-Headless; treat upgrade as an explicit ADR. Custom `episode-promoter` plugin is bus-factor 1; mitigate with thorough README + integration test.
5. **PR gate false positives.** A noisy gate gets ignored. Hard rule: if Phase 2A backtest falls below P 0.7 / R 0.8, the gate ships as advisory-only (warns, doesn't fail) until it earns its pass/fail authority.
6. **Capability for the gateway (signed retrieval).** Requires Chio capability infrastructure to be stable enough to issue a long-lived gateway capability. If not, Phase 2B falls back to a self-signed dev capability with explicit `chio-dev-only` scope.

---

## What we are explicitly *not* doing in v1

- Cross-repo federation (no platform/opus/alpha cross-queries).
- Persistent "Cap" resident agent.
- Voice-to-episode pipeline.
- 3D crate-graph fly-through.
- Auto-generated ADRs.
- Custom `chio-mcp-bridge` Obsidian plugin (deferred to Obsidian's upstream MCP).
- Receipt-tied screencasts.

Each is a real candidate for v2; none earns its complexity in v1.

---

## Phase 0 starts when

- A first ADR is filed (`decisions/ADR-0000-charter.md`) committing to this plan.
- The four Phase 0 outcome evals have a paper definition (no code yet) reviewed and signed off.
- A 2-week Phase 1 calendar window is identified.

Phase 0 should take ≤ 5 working days. If it slips past 7, that's signal that the carve-out is premature — fall back to incubating inside arc.
