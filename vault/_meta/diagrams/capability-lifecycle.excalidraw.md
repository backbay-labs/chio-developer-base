---
excalidraw-plugin: parsed
tags: [excalidraw, diagram]
diagram_id: capability-lifecycle
status: placeholder
related-spec: spec.capability.lifecycle
---

# Capability lifecycle

> Placeholder Excalidraw file. Open in Obsidian with the Excalidraw plugin and draw the diagram. When committed with real content, remove `status: placeholder` and replace this prose with a short caption.

## Required content (per PLAN.md "Vault" section)

The diagram should show the capability state machine end-to-end:

1. **Mint.** Issuer creates a capability with scope, expiry, and signature.
2. **Delegate.** Holder delegates a *narrowed* capability to a sub-holder. Attenuation rules visible.
3. **Exercise.** Sub-holder presents the capability; the guard pipeline runs (see `guard-pipeline.excalidraw.md` if added later).
4. **Revoke.** Issuer publishes a revocation entry; the revocation list version increments.
5. **Audit.** Receipt chain records every state transition with signed evidence.

Annotations to include:

- The boundary between issuer trust domain and holder trust domain.
- Where the kernel validates vs. where the guard pipeline runs.
- The receipt(s) emitted at each transition.

==⚠ Empty diagram — open in Excalidraw view to draw. ⚠==

# Excalidraw Data

## Text Elements

## Drawing

```compressed-json
{}
```
%%
