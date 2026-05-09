# Retrieval-eval fixture template

Pack-agnostic retrieval-eval format (p@k, MRR). Copy `example.yml` into
your pack at `eval/fixtures/<category>/<id>.yml` and fill the six fields.
The nine PR-#599 categories: `code-retrieval`, `docs-retrieval`,
`docs-spec-retrieval`, `feature-brief`, `graph-and-bridge`,
`graph-navigation-impact`, `graphiti-memory`, `operations`, `test-discovery`.

| Field      | Type     | Purpose                                                  |
| ---------- | -------- | -------------------------------------------------------- |
| `id`       | string   | Stable kebab-case identifier; used in run logs.          |
| `category` | string   | One of the nine categories above.                        |
| `query`    | string   | Free-text retrieval input the eval issues to the engine. |
| `expected` | string[] | Canonical doc ids/paths a correct top-k must surface.    |
| `metrics`  | string[] | Subset of `[p_at_k, mrr]`. `p_at_k` defaults to k=5.     |
| `notes`    | string   | Optional curator note explaining why the fixture exists. |

Scoring: `p_at_k = |expected ∩ top_k| / |expected|` (A floor: p@5 ≥ 0.99).
`mrr = mean(1 / rank_of_first_expected)` across fixtures (A floor: ≥ 0.97).
Files with `_example: true` are skipped by the runner.
