---
excalidraw-plugin: parsed
tags: [excalidraw, diagram]
diagram_id: release-qualification-flow
status: placeholder
related-playbook: playbooks.release-qualification
---

# Release qualification flow

> Placeholder Excalidraw file. Open in Obsidian with the Excalidraw plugin and draw the diagram. When committed with real content, remove `status: placeholder` and replace this prose with a short caption.

## Required content (per PLAN.md "Vault" section)

The diagram should show how a Chio release candidate moves from `main` to a signed release, with every gate visible:

1. **Candidate cut.** A commit is tagged as `rc-N`. The release-truth-boundary applies (no Graphiti-derived facts in the release qualification record).
2. **Conformance suite.** All SDK peer suites (Python, JS, …) run; verdict matrix populates.
3. **Guard checks.** Production guard pipeline runs against the candidate kernel.
4. **Policy compiler validation.** Policy compiler accepts the candidate's policy schema with no fail-closed regressions.
5. **Audit pass.** Receipt-compliance evidence collected; checkpoints signed.
6. **Sign-off.** Named owners sign; release artifacts are published.

Annotations to include:

- Which gate produces which receipt.
- Where automated vs. human sign-off happens.
- The roll-back path if a gate fails after sign-off.
- The release-truth boundary line — what is and isn't authoritative for release qualification.

This is the diagram PMs will screenshot. Make the gate labels readable.

==⚠ Empty diagram — open in Excalidraw view to draw. ⚠==

# Excalidraw Data

## Text Elements

## Drawing

```compressed-json
{}
```
%%
