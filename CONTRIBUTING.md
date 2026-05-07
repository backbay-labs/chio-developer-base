# Contributing to chio-developer-base

Thanks for your interest. This repo is public under [Apache-2.0](LICENSE) and external contributions are welcome — but the project has strong opinions about what belongs in it. **Read this before opening a PR.**

## What this project is

The dedicated knowledge base, vault, and developer-tooling stack for [Chio](https://github.com/backbay-labs) — Backbay's capability-based agent runtime. The full design lives in [PLAN.md](PLAN.md); the charter in [decisions/ADR-0000-charter.md](decisions/ADR-0000-charter.md). Read both first.

## Before you contribute

There are five hard rules (lifted verbatim from [AGENTS.md](AGENTS.md) — they apply to humans and agents alike):

1. **Never write to Graphiti directly.** The vault-sync daemon is the only writer to Graphiti. To add an episode, write `vault/episodes/<id>.md`.
2. **Never duplicate code into the vault.** Source code lives in arc / platform / opus / etc. and is referenced by stable path + symbol.
3. **`kb-engine/` cannot import `chio_*`.** The boundary is enforced by CI (Phase 1+).
4. **Vault frontmatter is a contract.** Every note has `id`, `type`, `status`. Bad frontmatter fails CI.
5. **The retrieval eval is the regression floor.** Overall A required across the 9 categories from [PR #599](https://github.com/bb-connor/arc/pull/599). If `make kb-eval` drops below A, revert; don't patch.

If your change conflicts with one of these rules, the rule wins. File an ADR if you genuinely think the rule is wrong — that's how it changes.

## What to contribute

**High-value contributions:**

- New playbooks (operational runbooks for Chio operations).
- Worked specs (one per Chio concept, mirroring [`vault/spec/capability-revocation.md`](vault/spec/capability-revocation.md)).
- Phase 0 outcome-eval fixtures and runners (see [Phase 0 milestone](https://github.com/backbay-labs/chio-developer-base/milestone/1)).
- Bug fixes to [`ops/scripts/`](ops/scripts/) and [`chio-pack/`](chio-pack/).
- Improvements to the four vault templates ([`vault/_meta/templates/`](vault/_meta/templates/)).
- New Dataview queries under [`vault/_meta/queries/`](vault/_meta/queries/).

**Lower-value contributions (please discuss before opening a PR):**

- New top-level vault folders. Requires an ADR per [PLAN.md](PLAN.md) "Vault layout".
- New Obsidian community plugins added to [`vault/.obsidian/community-plugins.json`](vault/.obsidian/community-plugins.json). Plugin choices are an ADR-level decision.
- Changes to the engine ↔ pack boundary. Always opens with an ADR.
- Adjustments to outcome-eval targets in [`chio-pack/eval/outcomes.yml`](chio-pack/eval/outcomes.yml). These are decisions about what "the carve-out works" means and need an ADR.

## How to contribute

### Reporting issues

- Search [existing issues](https://github.com/backbay-labs/chio-developer-base/issues) first.
- For Phase 0 work, check the [Phase 0 milestone](https://github.com/backbay-labs/chio-developer-base/milestone/1) — most outcome-eval work is already tracked there.
- For new feature ideas, open a discussion-style issue (no template required) before writing code.

### Pull requests

This repo enforces branch protection on `main`:

- Direct pushes to `main` are blocked for non-admins.
- PRs require **1 approving review** before merging.
- Force-pushes are blocked **universally** (including admins).

The flow:

1. **Fork** the repo (external contributors) or create a branch (internal Backbay contributors with write access).
2. **Open an issue first** for non-trivial changes. Briefly describe what you're proposing and why.
3. **Make your change** on a feature branch. One coherent change per PR.
4. **Run `make kb-eval-outcomes` locally** before pushing. The CI workflow ([eval.yml](.github/workflows/eval.yml)) runs this on every PR; you'll get a comment with the eval-outcomes table.
5. **Open the PR** with a description that:
   - Links the related issue.
   - States which (if any) ADR the change requires or modifies.
   - Reports the local `make kb-eval-outcomes` result.
6. **Address review feedback.** Maintainers may ask for an ADR if the change touches load-bearing infrastructure — that's not pushback, it's the contract.

### The eval-gate contract

[CI runs `make kb-eval-outcomes` on every PR](.github/workflows/eval.yml). Once Phase 0 is complete (per [ADR-0002](decisions/ADR-0002-phase-0-baselines.md) acceptance), the gate becomes blocking. Until then, it's informational — but PRs that visibly degrade an outcome eval will be asked to either revert or document the trade-off in an ADR.

The gate has an explicit escape hatch (Phase 2A+) for cases where a regression is intentional:

```
kb-gate: ack
> reason: revocation-window guard intentionally relaxed; ADR-NNNN
```

`kb-gate: ack` requires a reason. Reasons without a linking ADR are rejected.

### Where to ask questions

- **Workflow questions** ("how do I add an episode?"): start with [`vault/playbooks/onboard-a-chio-developer.md`](vault/playbooks/onboard-a-chio-developer.md).
- **Architecture questions** ("why does X exist?"): the ADRs in [`decisions/`](decisions/) and the seed episodes in [`vault/episodes/`](vault/episodes/) (post-migration) are the source of truth.
- **Spec questions** ("what does the protocol require?"): the worked specs in [`vault/spec/`](vault/spec/) — start with [`capability-revocation.md`](vault/spec/capability-revocation.md), [`receipt-commitment.md`](vault/spec/receipt-commitment.md), [`guard-pipeline.md`](vault/spec/guard-pipeline.md).
- **Anything else:** open an issue.

## Code style

- **Markdown:** match the conventions in existing files. Frontmatter must validate against [`chio_pack/frontmatter.py`](chio-pack/) (Phase 1+).
- **Python:** target Python 3.11+. The two scripts under [`ops/scripts/`](ops/scripts/) and the [`chio_pack/eval/runner.py`](chio-pack/chio_pack/eval/runner.py) skeleton are the style guides.
- **TypeScript** (Obsidian plugins): match [`episode-promoter/src/main.ts`](vault/.obsidian/plugins/episode-promoter/src/main.ts).
- **Comments:** lean toward "no comment" by default. Add a comment when the *why* is non-obvious — never to explain *what* well-named code already shows.

## License and contributor sign-off

This project is licensed under [Apache-2.0](LICENSE). By submitting a pull request, you agree your contribution is licensed under the same terms. We don't currently require a separate Contributor License Agreement (CLA) or DCO sign-off, but reserve the right to add one if the project grows.

## See also

- [PLAN.md](PLAN.md) — the design
- [AGENTS.md](AGENTS.md) — rules for humans and agents alike
- [README.md](README.md) — quickstart
- [decisions/](decisions/) — ADRs (start at [ADR-0000](decisions/ADR-0000-charter.md))
- [vault/playbooks/onboard-a-chio-developer.md](vault/playbooks/onboard-a-chio-developer.md) — Day-1 orientation
- [vault/playbooks/adopt-chio-developer-base.md](vault/playbooks/adopt-chio-developer-base.md) — for second-adopter teams (platform / opus / alpha)
