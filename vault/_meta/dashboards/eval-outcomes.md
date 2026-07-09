<!-- chio-eval-outcomes -->
# Outcome eval dashboard

Last updated: 2026-07-08

| Eval | Status | Baseline | Notes |
| ---- | ------ | -------- | ----- |
| retrieval-A (9 categories) | **ok / grade A** | mean p@5=1.0, mean MRR=1.0 (38 fixtures) | Proven on THIS stack 2026-07-08 via live pgvector + OpenAI embeds; live `kb_search_*` and eval share `chio_pack.ranking` path prior (no fixture-id hardcodes) |
| time-to-first-correct-fix | blocked-input | TBD | Requires live agent runner (Wave 1+) |
| repeated-mistake-rate | blocked-input | TBD | Sessions dir + stub classifiers (ADR-0002 deltas) |
| conformance-harness-recall | blocked-input | TBD | Needs live kb_search_* against arc fixtures |
| capability-error-explanation | blocked-input | TBD | Run-0 rater-A (Connor) still required |

## Wave 0 / Wave 1 notes

- ADR-0002a accepted: continue carve-out; 20-working-day floor for Waves 1–2.
- Retrieval fixtures for this tree live under `kb-engine/eval/fixtures/` (38 fixtures, 9 categories).
- Live MCP gateway (`infra/chio-kb-mcp-server.py`) on `:8111` — non-stub `kb_search_code` / `kb_search_docs` / `kb_add_episode`.
- HNSW indexes confirmed on `chio_kb.code_chunks` and `chio_kb.doc_chunks`.
- Run-0 human calibration remains a manual checkpoint; do not invent baseline numbers; do not block later waves forever on it.

## ADR-0002 Run-0 checkpoint (Connor-manual)

| Field | Value |
| ----- | ----- |
| Checkpoint | Run-0 capability-error-explanation calibration |
| Owner | @connor (rater-A) |
| Status | **pending-human** |
| Rater-A scores | *not recorded — do not invent* |
| LLM raters B/C | blocked until rater-A session completes |
| ADR-0002 `date-accepted` | TBD until baselines land |

Harness is runnable on main; filling the ADR-0002 baseline table and
`capability-error-explanation` row above requires Connor sitting the 10
cap-error scenarios. No synthetic grades.

## Wave 1 / ADR-0002 Run-0 checkpoint

> Updated 2026-07-09 00:07 UTC by Execution Lead.

| Gate | Status | Evidence |
| --- | --- | --- |
| Retrieval-A on this stack | **MET** | `vault/_meta/dashboards/retrieval-a-wave1.json` — grade **A**, mean p@5 **1.0**, mean MRR **1.0**, all 9 categories A (38 fixtures). |
| Live MCP non-stub | **MET** | `http://localhost:8111/health` phase 1.3, 13 tools, OpenAIEmbedder; `kb_search_*` + `kb_add_episode` return non-stub. |
| Chunker + HNSW | **MET** | `kb_engine.chunker`; HNSW indexes `idx_code_chunks_embedding` / `idx_doc_chunks_embedding`. |
| ADR-0002 Run-0 rater-A | **PENDING — Connor manual** | Do **not** invent numbers. Harness is runnable; baselines in ADR-0002 remain TBD until Connor sits the 10 cap-error scenarios. |

