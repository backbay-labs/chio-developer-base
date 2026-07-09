# Vector Bench

> Dual-index sidecar report. TurboVec is optional; pgvector remains the
> default primary backend (`KB_VECTOR=pgvector`). Real TurboVec rows
> appear only when `turbovec`+`numpy` are installed (`kb-engine[turbovec]`).
> This artifact does **not** promote TurboVec.

| Backend | Vectors | Dim | p95 ms | Mean ms | RSS MB | Note |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| exact-cosine-baseline | 1000 | 32 | 7.602 | 5.170 | 31.1 |  |
| turbovec-fake-sidecar | 1000 | 32 | 5.522 | 4.583 | 32.0 |  |
| turbovec-real-idmap | 1000 | 32 | 0.018 | 0.025 | 40.4 |  |
