# chio-developer-base — Make targets
#
# Phase 0 (works today):
#   help, kb-status, kb-migrate-seeds, kb-harvest-fixtures, kb-eval-outcomes-baseline,
#   check-boundary
# Phase 1+ (block until dependencies land — see PLAN.md):
#   kb-up, kb-down, kb-reset, kb-reseed, kb-update, kb-live, kb-smoke
#   kb-eval, kb-eval-retrieval, kb-eval-outcomes, kb-dogfood
# Phase 2+ (bigger blocks):
#   kb-bench, kb-verify, kb-gate-backtest

.PHONY: help check-boundary \
        kb-status kb-migrate-seeds kb-harvest-fixtures kb-eval-outcomes-baseline \
        kb-up kb-down kb-reset kb-reseed kb-update kb-live kb-seed-memory kb-smoke \
        kb-eval kb-eval-retrieval kb-eval-outcomes kb-dogfood \
        kb-bench kb-verify kb-gate-backtest

ARC_REPO     ?= ../arc
COMPOSE_FILE := infra/docker-compose.yml
ENV_FILE     := .env
PYTHON       := uv run python

# == Phase 0 — always available ==

help: ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN{FS=":.*?## "} {printf "  %-26s %s\n", $$1, $$2}'

check-boundary: ## Phase 0: AGENTS.md hard rule #3 — engine ↔ pack and pack ↔ pack
	@python3 ops/ci/check-imports.py

kb-status: ## Phase 0: report what exists vs what's expected
	@echo "== chio-developer-base status =="
	@echo "Phase 0 dependencies:"
	@printf "  ARC_REPO    "; test -d "$(ARC_REPO)" && echo "ok ($(ARC_REPO))" || echo "MISSING — set ARC_REPO=…"
	@printf "  vault/      "; test -d vault && echo "ok" || echo "MISSING — vault skeleton not seeded"
	@printf "  decisions/  "; test -f decisions/ADR-0000-charter.md && echo "ok" || echo "MISSING — ADR-0000 not filed"
	@printf "  PHASE-0     "; test -f chio-pack/eval/PHASE-0.md && echo "ok" || echo "MISSING — eval design absent"
	@echo "Phase 1+ dependencies:"
	@printf "  compose     "; test -f $(COMPOSE_FILE) && echo "ok" || echo "blocked: Phase 1.x — $(COMPOSE_FILE)"
	@printf "  chio-pack   "; test -f chio-pack/pyproject.toml && echo "ok" || echo "blocked: Phase 1.2 — chio-pack/pyproject.toml"
	@printf "  kb-engine   "; test -f kb-engine/pyproject.toml && echo "ok" || echo "blocked: Phase 1.2 — kb-engine/pyproject.toml"
	@if [ -f $(COMPOSE_FILE) ]; then docker compose -f $(COMPOSE_FILE) ps 2>/dev/null || true; fi

kb-migrate-seeds: ## Phase 0: convert PR #599 seeds/graphiti/*.json → vault/episodes/*.md
	@test -d "$(ARC_REPO)" || { echo "ERROR: ARC_REPO=$(ARC_REPO) missing"; exit 1; }
	@test -d "$(ARC_REPO)/ops/knowledge-base/seeds/graphiti" || { \
	  echo "ERROR: arc PR #599 seeds dir missing — try: cd $(ARC_REPO) && git checkout codex/chio-kb-a-grade-dogfood"; \
	  exit 1; }
	$(PYTHON) ops/scripts/migrate-seeds.py \
	  --seeds "$(ARC_REPO)/ops/knowledge-base/seeds/graphiti" \
	  --vault vault \
	  --branch codex/chio-kb-a-grade-dogfood

kb-harvest-fixtures: ## Phase 0: harvest conformance failure fixtures from arc git history
	@test -d "$(ARC_REPO)" || { echo "ERROR: ARC_REPO=$(ARC_REPO) missing"; exit 1; }
	$(PYTHON) ops/scripts/harvest-conformance-fixtures.py \
	  --arc-repo "$(ARC_REPO)" \
	  --out chio-pack/eval/fixtures/conformance-recall \
	  --target 20

kb-eval-outcomes-baseline: ## Phase 0: print Phase 0 baseline checklist (no runner yet)
	@echo "Phase 0 outcome-eval baselines required (see chio-pack/eval/PHASE-0.md):"
	@echo "  [ ] time-to-first-correct-fix:  >= 8 fixtures harvested"
	@echo "  [ ] repeated-mistake-rate:      >= 20 sessions logged + classifier"
	@echo "  [ ] conformance-harness-recall: 20 fixtures via 'make kb-harvest-fixtures'"
	@echo "  [ ] capability-error-explanation: 10 scenarios + 3 raters"
	@echo ""
	@echo "Phase 0 ends when ADR-0002 confirms baselines committed in:"
	@echo "  vault/_meta/dashboards/eval-outcomes.md"

# == Phase 1 — stack lifecycle ==

kb-up: ## Phase 1: bring stack up (postgres + neo4j + graphiti + chio-kb-mcp)
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE) up -d
	@echo "  → waiting for chio-kb-mcp health…"
	@for i in $$(seq 1 60); do \
	  curl -fsS http://localhost:8111/health >/dev/null 2>&1 && echo "  ready" && exit 0; \
	  sleep 2; \
	done; echo "  TIMEOUT"; exit 1

kb-down: ## Phase 1: stop stack
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) down

kb-reset: ## Phase 1: drop tables, clear neo4j Chio nodes, clear cocoindex state
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	@if [ "$$KB_RESET_VOLUMES" = "1" ]; then \
	  docker compose -f $(COMPOSE_FILE) down -v; \
	fi
	docker compose -f $(COMPOSE_FILE) up -d kb-postgres kb-neo4j chio-kb-mcp
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp chio-kb-reset

kb-update: ## Phase 1: incremental cocoindex catch-up + vault re-derive
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp \
	  cocoindex -d /app update --force chio_kb.index
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp chio-kb-vault-derive

kb-live: ## Phase 1: cocoindex live mode + vault file watch
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) exec chio-kb-mcp \
	  cocoindex -d /app update --force --live chio_kb.index

kb-seed-memory: ## Phase 1: derive Graphiti episodes from vault/episodes/*.md
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) up -d kb-neo4j graphiti-mcp chio-kb-mcp
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp chio-kb-vault-derive --target graphiti

kb-reseed: kb-reset kb-update kb-seed-memory ## Phase 1: full clean rebuild

kb-smoke: ## Phase 1: health + tools/list smoke
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp chio-kb-smoke

# == Eval gates ==

kb-eval: kb-eval-retrieval kb-eval-outcomes ## Phase 1+: full eval gate

kb-eval-retrieval: ## Phase 1: retrieval eval (PR #599 fixtures, A floor)
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp \
	  chio-kb-eval --suite retrieval --fail-below-a

kb-eval-outcomes: ## Phase 0+: outcome evals (time-to-fix, repeated-mistake, …)
	@test -f chio-pack/pyproject.toml || { echo "blocked: Phase 1.2 — chio-pack/ package not built"; exit 1; }
	cd chio-pack && uv run chio-pack-eval --suite outcomes \
	  --config eval/outcomes.yml \
	  --report ../vault/_meta/dashboards/eval-outcomes.md

kb-dogfood: ## Phase 1: regenerate DOGFOOD-REVIEW.md
	@test -f $(COMPOSE_FILE) || { echo "blocked: Phase 1 — $(COMPOSE_FILE) missing"; exit 1; }
	docker compose -f $(COMPOSE_FILE) exec -T chio-kb-mcp \
	  chio-kb-eval --suite all --format markdown --fail-below-a > DOGFOOD-REVIEW.md

# == Phase 2+ moonshots ==

kb-bench: ## Phase 4: latency + memory + 200-file-PR gate benchmarks
	@echo "blocked: Phase 4 — bench harness not implemented"; exit 1

kb-verify: ## Phase 2B: verify a retrieval receipt
	@echo "blocked: Phase 2B — kb-engine/receipt/envelope.py not implemented"; exit 1

kb-gate-backtest: ## Phase 2A: backtest PR-impact gate against last N arc PRs
	@test -d "$(ARC_REPO)" || { echo "ERROR: ARC_REPO=$(ARC_REPO) missing"; exit 1; }
	@echo "blocked: Phase 2A — chio-pr-gate/ not implemented"; exit 1
