"""pgvector vs TurboVec dual-index benchmark.

Default mode is offline/synthetic so CI does not need Postgres or the optional
TurboVec package. When ``turbovec`` + ``numpy`` are installed, the report also
includes a real ``IdMapIndex`` row behind ``KB_VECTOR=turbovec``.

Postgres/pgvector remains the primary CI gate. This bench never promotes
TurboVec.
"""
from __future__ import annotations

import argparse
import os
import random
import resource
import statistics
import time
from pathlib import Path
from typing import Sequence

from kb_engine.store import FakeTurboVecStore, TurboVecStore, create_turbovec_store


def _vectors(n: int, dim: int) -> list[list[float]]:
    rng = random.Random(42)
    return [[rng.uniform(-1.0, 1.0) for _ in range(dim)] for _ in range(n)]


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))
    return ordered[idx]


def _bench_store(name: str, store, n: int, dim: int, queries: int) -> dict[str, float | str]:
    vectors = _vectors(n, dim)
    store.add_with_ids(list(range(1, n + 1)), vectors)
    latencies: list[float] = []
    for query in _vectors(queries, dim):
        started = time.perf_counter()
        store.search(query, k=8)
        latencies.append((time.perf_counter() - started) * 1000)
    return {
        "backend": name,
        "count": n,
        "dim": dim,
        "p95_ms": _p95(latencies),
        "mean_ms": statistics.fmean(latencies) if latencies else 0.0,
        "rss_mb": _rss_mb(),
    }


def run_bench(n: int = 1000, dim: int = 32, queries: int = 50) -> list[dict[str, float | str]]:
    # Align dim to TurboVec's multiple-of-8 constraint for the real path.
    real_dim = dim if dim % 8 == 0 else dim + (8 - dim % 8)
    rows: list[dict[str, float | str]] = [
        # Exact cosine baseline (in-memory Fake) — not live Postgres/pgvector ANN.
        _bench_store("exact-cosine-baseline", FakeTurboVecStore(dim=real_dim), n, real_dim, queries),
        _bench_store("turbovec-fake-sidecar", FakeTurboVecStore(dim=real_dim), n, real_dim, queries),
    ]
    # Optional real package path (install: uv pip install 'kb-engine[turbovec]')
    try:
        store = create_turbovec_store(dim=real_dim)
        if isinstance(store, TurboVecStore):
            rows.append(_bench_store("turbovec-real-idmap", store, n, real_dim, queries))
        else:
            rows.append({
                "backend": "turbovec-real-idmap",
                "count": n,
                "dim": real_dim,
                "p95_ms": 0.0,
                "mean_ms": 0.0,
                "rss_mb": _rss_mb(),
                "note": "skipped: turbovec not installed; Fake used",
            })
    except Exception as exc:  # pragma: no cover - environment-specific
        rows.append({
            "backend": "turbovec-real-idmap",
            "count": n,
            "dim": real_dim,
            "p95_ms": 0.0,
            "mean_ms": 0.0,
            "rss_mb": _rss_mb(),
            "note": f"skipped: {exc}",
        })
    return rows


def _rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes.
    return raw / (1024 * 1024) if raw > 10_000_000 else raw / 1024


def render_markdown(rows: list[dict[str, float | str]]) -> str:
    kb_vector = os.environ.get("KB_VECTOR", "pgvector")
    lines = [
        "# Vector Bench",
        "",
        "> Dual-index sidecar report. TurboVec is optional; pgvector remains the",
        f"> default primary backend (`KB_VECTOR={kb_vector}`). Real TurboVec rows",
        "> appear only when `turbovec`+`numpy` are installed (`kb-engine[turbovec]`).",
        "> This artifact does **not** promote TurboVec.",
        "",
        "| Backend | Vectors | Dim | p95 ms | Mean ms | RSS MB | Note |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        note = str(row.get("note", ""))
        lines.append(
            "| {backend} | {count} | {dim} | {p95_ms:.3f} | {mean_ms:.3f} | {rss_mb:.1f} | {note} |".format(
                backend=row["backend"],
                count=row["count"],
                dim=row["dim"],
                p95_ms=float(row["p95_ms"]),
                mean_ms=float(row["mean_ms"]),
                rss_mb=float(row["rss_mb"]),
                note=note,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--queries", type=int, default=50)
    parser.add_argument(
        "--out",
        default="../vault/_meta/dashboards/vector-bench.md",
        help="markdown report path",
    )
    args = parser.parse_args()

    rows = run_bench(n=args.n, dim=args.dim, queries=args.queries)
    report = render_markdown(rows)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
