# chio-pr-gate/

Advisory PR-impact gate for chio-developer-base (Wave 5). Policy lives behind
`ImpactPolicy`; default `ChioImpactPolicy` flags CANONICAL_DOC / GUARDS /
IMPLEMENTS path patterns and honors `kb-gate: ack`.

**Status:** advisory-only. Blocking mode is deferred until a real
follow-up-within-14d backtest meets P≥0.7 / R≥0.8.

## Layout

```
chio-pr-gate/
├── action.yml          composite GitHub Action (local-runnable)
├── pyproject.toml
├── src/chio_pr_gate/
│   ├── gate.py         CLI entry
│   ├── policy.py       ImpactPolicy + ChioImpactPolicy
│   ├── render.py       PR comment markdown
│   └── backtest.py     synthetic (+ optional arc gh) P/R harness
└── tests/
```

## Local run (composite-equivalent)

```bash
cd chio-pr-gate
uv sync --group dev
uv run --no-project pytest tests/ -q
uv run --no-project python -m chio_pr_gate.gate \
  --pr-body "" \
  --changed-paths-json <(echo '["vault/spec/receipt-commitment.md"]') \
  --advisory true

# Backtest (synthetic + arc gh heuristic when available)
uv run --no-project python -m chio_pr_gate.backtest \
  --arc-repo ../../arc \
  --limit 50 \
  --out ../vault/_meta/dashboards/pr-gate-backtest.json
# or: make kb-gate-backtest
```

## GitHub Action usage

```yaml
- uses: ./chio-pr-gate
  with:
    pr-body: ${{ github.event.pull_request.body }}
    advisory: "true"
    working-directory: chio-pr-gate
```

## Escape hatch

```
kb-gate: ack
> reason: …
```

## Eval

`pr-impact-gate-precision-recall` stays **deferred** in `outcomes.yml` until
ground-truth follow-up labels exist. Current backtest reports P/R honestly
with `mode` + `note` fields.
