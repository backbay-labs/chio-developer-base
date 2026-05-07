---
excalidraw-plugin: parsed
tags: [excalidraw, diagram]
diagram_id: receipt-commitment-chain
status: placeholder
related-spec: spec.receipt.commitment
---

# Receipt commitment chain

> Placeholder Excalidraw file. Open in Obsidian with the Excalidraw plugin and draw the diagram. When committed with real content, remove `status: placeholder` and replace this prose with a short caption.

## Required content (per PLAN.md "Vault" section)

The diagram should show what gets signed, what gets hashed, what's in the Merkle tree, and how a checkpoint is verified:

1. A **decision event** (capability mint, guard verdict, policy eval, revocation, etc.) becomes a leaf.
2. Leaves are batched into a **block**; block root is signed by the kernel's signing key.
3. Block roots accumulate into a **checkpoint** at issuer-defined cadence; checkpoint root is published.
4. **Inclusion proof.** Given a leaf, traverse the Merkle path up to a published checkpoint root.
5. **Verifier flow.** External verifier resolves a receipt → block → checkpoint → root, then checks the kernel signature.

Annotations to include:

- Where the chain is append-only vs. where it's content-addressed.
- The relationship between the receipt schema (`spec/schemas/chio-wire/v1/receipt/`) and what's actually hashed.
- The boundary between offline verification (using only published roots) and online verification (querying the kernel).

==⚠ Empty diagram — open in Excalidraw view to draw. ⚠==

# Excalidraw Data

## Text Elements

## Drawing

```compressed-json
{}
```
%%
